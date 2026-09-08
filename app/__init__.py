"""
app/__init__.py
================
Application factory: costruisce e configura l'istanza Flask.

Perché una "application factory" (funzione create_app) invece di un
oggetto Flask globale? Perché rende l'app testabile (si può creare
un'istanza con configurazione diversa nei test) e disaccoppia
l'inizializzazione dal semplice import del pacchetto.
"""

import os
from datetime import date, datetime

from flask import Flask

from app.config import config_by_name
from app.extensions import db, login_manager, csrf


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    config_name = config_name or os.environ.get("VALIGIA_ENV", "production")
    app.config.from_object(config_by_name[config_name])

    # Permette ai test di puntare il database a un percorso temporaneo
    # SENZA dover ricaricare il modulo app.config (fragile: i moduli già
    # importati altrove, come questo stesso file, non vedrebbero comunque
    # il reload). Non usato in produzione.
    if os.environ.get("VALIGIA_DATABASE_URI_OVERRIDE"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["VALIGIA_DATABASE_URI_OVERRIDE"]

    # --- Inizializzazione estensioni ------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # SQLite di default blocca i LETTORI quando c'è una scrittura in corso
    # (modalità "rollback journal"). Con gunicorn a più worker, questo può
    # causare errori intermittenti "database is locked" — ad es. aprire
    # la Home mentre un altro worker sta ancora salvando la modifica di
    # una valigia. La modalità WAL (Write-Ahead Logging) permette letture
    # concorrenti durante una scrittura, eliminando quasi del tutto questo
    # problema; `busy_timeout` fa aspettare (invece di fallire subito) nei
    # rari casi in cui una vera contesa capiti comunque.
    _configure_sqlite_for_concurrency(app)

    # --- Registrazione blueprint -----------------------------------------
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.catalog.routes import catalog_bp
    from app.trips.routes import trips_bp
    from app.api.routes import api_bp
    from app.users.routes import users_bp
    from app.luggage.routes import luggage_bp
    from app.backup.routes import backup_bp
    from app.settings.routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(users_bp)
    app.register_blueprint(luggage_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(settings_bp)

    _register_service_worker(app)

    # --- Comandi CLI personalizzati -----------------------------------------
    from app.cli import register_cli
    register_cli(app)

    # --- User loader per Flask-Login --------------------------------------
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blocco globale: obbliga il cambio password prima di usare l'app ---
    _register_password_change_guard(app)

    # --- Filtri e variabili disponibili in tutti i template ----------------
    _register_template_helpers(app)

    # --- Gestori di errore personalizzati -----------------------------------
    _register_error_handlers(app)

    # --- Creazione tabelle + migrazioni + dati iniziali (idempotente) --------
    # Protetta da un lock di file: gunicorn avvia più worker (processi
    # separati) che importano ed eseguono create_app() in parallelo. Senza
    # questo lock, due worker possono provare a creare le stesse tabelle
    # nello stesso istante e uno dei due fallisce con "table already
    # exists" (visto succedere davvero con --workers 2, vedi CONTEXT.md).
    with app.app_context():
        _init_database_with_lock(app)

    return app


def _register_service_worker(app: Flask) -> None:
    """
    Service worker per la consultazione offline: cache "man mano che si
    naviga" (nessuna lista di file da mantenere aggiornata a mano) delle
    pagine e risorse statiche già visitate, così restano consultabili
    anche senza connessione. Le SCRITTURE (POST) non vengono mai
    intercettate qui: quelle passano da apiFetch + la coda offline (vedi
    static/js/offline.js).

    Va servito dalla RADICE del sito (`/sw.js`), non da `/static/sw.js`:
    lo "scope" di un service worker è, di default, la cartella da cui
    viene servito — da `/static/` non potrebbe mai controllare il resto
    dell'app (`/viaggi/`, `/catalogo/`, ecc.).

    IMPORTANTE — limite intrinseco di questa strategia (bug segnalato,
    capito ma non completamente risolvibile): si può consultare offline
    SOLO ciò che è già stato aperto almeno una volta online. Una pagina
    MAI visitata non può comparire dal nulla. Due mitigazioni:
    1. Se manca in cache una pagina di NAVIGAZIONE (un link cliccato,
       non un file statico), mostriamo una pagina di spiegazione chiara
       invece di sostituire silenziosamente con la Home (che prima
       sembrava un link "rotto": l'indirizzo cambiava ma il contenuto
       restava quello della Home, molto confuso).
    2. Un pulsante esplicito "Prepara per l'uso offline" (mai
       automatico: un precaricamento silenzioso consumerebbe dati e
       batteria anche quando non serve) precarica tutte le pagine
       principali in un colpo solo — vedi `prepareOfflineCache` in
       static/js/app.js e l'endpoint `/api/pagine-offline`.
    """
    from flask import Response

    OFFLINE_FALLBACK_URL = "/offline-non-disponibile"

    @app.route(OFFLINE_FALLBACK_URL)
    def offline_fallback():
        from flask import render_template
        return render_template("offline_fallback.html")

    @app.route("/sw.js")
    def service_worker():
        cache_name = f"valigia-v{app.config.get('APP_VERSION', '0')}"
        content = f"""
const CACHE_NAME = "{cache_name}";
const OFFLINE_URL = "{OFFLINE_FALLBACK_URL}";

self.addEventListener("install", (event) => {{
  self.skipWaiting();
  // La pagina di spiegazione offline va messa in cache SUBITO
  // all'installazione: deve essere disponibile anche se il resto non
  // è ancora stato visitato da nessuno.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL)).catch(() => {{}})
  );
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      )
    ).then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (event) => {{
  const req = event.request;
  // Mai intercettare le scritture: quelle passano da apiFetch (vedi
  // static/js/offline.js), non da qui.
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(req)
      .then((res) => {{
        if (res && res.status === 200) {{
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }}
        return res;
      }})
      .catch(() =>
        caches.match(req).then((cached) => {{
          if (cached) return cached;
          if (req.mode === "navigate") return caches.match(OFFLINE_URL);
          return Response.error();
        }})
      )
  );
}});
""".strip()
        return Response(content, mimetype="application/javascript")


def _init_database_with_lock(app: Flask) -> None:
    """
    Esegue create_all() + migrazioni + seed sotto un lock esclusivo a
    livello di file, così che con più worker gunicorn solo uno alla
    volta tocchi lo schema: gli altri aspettano il proprio turno e, a
    quel punto, trovano tutto già pronto (le operazioni sono idempotenti).
    """
    import fcntl
    from app.config import DATA_DIR

    lock_path = DATA_DIR / ".init.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            db.create_all()

            from app.migrations import run_migrations
            run_migrations(app)

            _ensure_seed_data(app)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _configure_sqlite_for_concurrency(app: Flask) -> None:
    """
    Attiva la modalità WAL e un busy_timeout ragionevole su OGNI nuova
    connessione SQLite aperta dal pool di SQLAlchemy. Va registrato prima
    di qualunque query (idealmente subito dopo db.init_app). Non ha
    effetto su database non-SQLite (es. se in futuro si passa a Postgres
    tramite DATABASE_URL).
    """
    if not app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite:"):
        return

    from sqlalchemy import event

    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()


def _register_password_change_guard(app: Flask) -> None:
    """
    Finché un utente non ha cambiato la password iniziale, ogni pagina
    diversa da "cambia password" / "logout" / file statici viene rediretta
    lì. Impedisce di girare per l'app lasciando credenziali temporanee attive.
    """
    from flask import redirect, url_for, request
    from flask_login import current_user

    ALLOWED_ENDPOINTS = {"auth.change_password", "auth.logout", "static"}

    @app.before_request
    def _force_password_change():
        if not current_user.is_authenticated:
            return None
        if not current_user.must_change_password:
            return None
        if request.endpoint in ALLOWED_ENDPOINTS:
            return None
        return redirect(url_for("auth.change_password"))


def _register_template_helpers(app: Flask) -> None:
    """Filtri Jinja e variabili globali (date/numeri in stile italiano, ecc.)."""

    MESI_IT = [
        "", "gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic",
    ]

    @app.template_filter("data_it")
    def data_it(value):
        """Formatta una data come '12 ott 2026'."""
        if value is None:
            return ""
        return f"{value.day} {MESI_IT[value.month]} {value.year}"

    @app.template_filter("data_it_estesa")
    def data_it_estesa(value):
        """Formatta una data come 'Lunedì 12 Ottobre 2026' (usata in intestazioni)."""
        GIORNI_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        MESI_ESTESI = [
            "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
        ]
        if value is None:
            return ""
        return f"{GIORNI_IT[value.weekday()]} {value.day} {MESI_ESTESI[value.month]} {value.year}"

    @app.template_filter("numero_it")
    def numero_it(value, decimali=1):
        """
        Formatta un numero secondo la convenzione italiana: punto per le
        migliaia, virgola per i decimali (es. 1500.2 -> "1.500,2"). Usato
        per pesi e capacità. Se il valore è None restituisce una lineetta.
        """
        if value is None:
            return "—"
        from app.utils import format_number_it
        return format_number_it(value, decimals=decimali)

    @app.template_filter("get_variant_modal_data")
    def get_variant_modal_data(variant, trip_item, trip_luggage_id):
        """
        Un dizionario con tutto il necessario alla finestra di scelta del
        modello (vedi static/js/dashboard.js::initVariantModal) per UN
        modello, IN UNA valigia specifica — calcolato una volta sola al
        render della pagina, così aprire la finestra non richiede
        nessuna richiesta al server.
        """
        return {
            "id": variant.id,
            "description": variant.description,
            "weight_grams": variant.weight_grams,
            "owned_qty": variant.owned_qty,
            "qty_here": trip_item.qty_for_variant_in_luggage(variant.id, trip_luggage_id),
            "qty_elsewhere": trip_item.qty_for_variant(variant.id) - trip_item.qty_for_variant_in_luggage(variant.id, trip_luggage_id),
        }

    @app.context_processor
    def inject_globals():
        return {
            "app_name": app.config.get("APP_NAME", "Valigia"),
            "app_version": app.config.get("APP_VERSION", "?"),
            "oggi": date.today(),
            "anno_corrente": datetime.utcnow().year,
        }

    @app.context_processor
    def inject_nav_context():
        """
        Rende disponibile in TUTTI i template il numero totale di oggetti
        "da comprare" su tutti i viaggi accessibili all'utente corrente,
        per il pallino rosso sul link "Lista della spesa" nella barra di
        navigazione (che ora porta all'elenco aggregato di tutti i viaggi,
        non più a un singolo "viaggio corrente" in sessione).
        """
        from flask_login import current_user

        if not current_user.is_authenticated:
            return {}

        from app.models import TripItem
        from app.utils import accessible_trips_query

        trips = accessible_trips_query(current_user).all()
        trip_ids = [t.id for t in trips]
        if not trip_ids:
            return {"nav_shopping_count": 0, "nav_nearest_trip": None}

        count = TripItem.query.filter(
            TripItem.trip_id.in_(trip_ids), TripItem.missing_qty > 0
        ).count()

        # Il viaggio più vicino alla partenza (non ancora concluso), per
        # il collegamento diretto nel menu in alto.
        upcoming = sorted((t for t in trips if not t.is_past), key=lambda t: t.start_date)
        nearest_trip = upcoming[0] if upcoming else None

        return {"nav_shopping_count": count, "nav_nearest_trip": nearest_trip}


def _register_error_handlers(app: Flask) -> None:
    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def _ensure_seed_data(app: Flask) -> None:
    """
    Popola il database al primissimo avvio con l'utente amministratore di
    default (credenziali da config/.env) e il suo catalogo personale
    (valigie di partenza + import del catalogo di base). L'operazione è
    idempotente: se esiste già almeno un utente non fa nulla.
    """
    from app.models import User, UserRole
    from app.utils import provision_new_user_defaults

    if User.query.count() == 0:
        admin = User(
            username=app.config["ADMIN_USERNAME"],
            role=UserRole.ADMIN,
            must_change_password=True,
        )
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()

        provision_new_user_defaults(admin)
