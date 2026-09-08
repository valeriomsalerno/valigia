"""
migrations.py
=============
Sistema di migrazioni leggere, senza Flask-Migrate/Alembic: ad ogni
avvio, DOPO che `db.create_all()` ha creato le tabelle mancanti, questo
modulo porta lo schema di un database GIÀ POPOLATO al passo più recente,
senza mai perdere i dati esistenti.

Come funziona:
  - la tabella `schema_meta` (una riga sola) ricorda l'ultima migrazione
    applicata con successo;
  - ogni migrazione è una funzione numerata, applicata UNA SOLA VOLTA;
  - le migrazioni usano SQL diretto (non i modelli SQLAlchemy, che
    riflettono già lo schema NUOVO) per leggere/scrivere lo schema VECCHIO
    con `ALTER TABLE ... ADD COLUMN` (mai `DROP`/`RENAME`: le colonne e le
    tabelle superate dalla versione precedente restano semplicemente
    inutilizzate, per non rischiare mai di perdere dati per un errore in
    una migrazione).

Per aggiungere una nuova migrazione in futuro: scrivi una nuova funzione
`_migrate_to_vN(conn)`, aggiungila in fondo a `_MIGRATIONS`, e basta —
verrà applicata automaticamente al prossimo avvio sui database che sono
ancora alla versione N-1. Vedi CONTEXT.md, sezione 8, per una guida più
estesa con esempi.
"""

from sqlalchemy import text


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}
    ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _add_column(conn, table: str, column: str, coldef: str) -> None:
    """ALTER TABLE ... ADD COLUMN, ma solo se la colonna non esiste già (idempotente)."""
    if not _column_exists(conn, table, column):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}"))


def _guess_luggage_type(name: str) -> str:
    """Deduce la tipologia (cabina/stiva/zaino) dal nome di un vecchio 'tipo di bagaglio'."""
    n = (name or "").lower()
    if "stiva" in n:
        return "stiva"
    if "mano" in n or "cabina" in n:
        return "cabina"
    if "zaino" in n:
        return "zaino"
    return "stiva"


def _migrate_to_v1(conn) -> None:
    """
    v2.0.x -> v2.1: le valigie diventano l'unico concetto di bagaglio
    (prima esisteva un catalogo separato "tipi di bagaglio"), e la lista
    da mettere in valigia diventa personale per ogni utente invece che
    condivisa su un viaggio condiviso.
    """
    # --- Colonne nuove sulle tabelle già esistenti ---------------------------
    _add_column(conn, "users", "full_name", "TEXT DEFAULT ''")
    _add_column(conn, "luggage", "tipologia", "TEXT DEFAULT 'stiva'")
    _add_column(conn, "luggage", "is_default_for_new_trip", "BOOLEAN DEFAULT 0")
    _add_column(conn, "items", "default_luggage_type", "TEXT")
    _add_column(conn, "trip_items", "user_id", "INTEGER")
    _add_column(conn, "trip_items", "assigned_buyer_id", "INTEGER")
    _add_column(conn, "trip_items", "target_qty", "INTEGER")
    _add_column(conn, "trip_item_qty", "trip_luggage_id", "INTEGER")

    # --- Migrazione dei vecchi "tipi di bagaglio" verso Luggage reali --------
    bagtype_to_luggage: dict[int, int] = {}
    if _table_exists(conn, "bag_types"):
        bag_types = conn.execute(text("SELECT id, owner_id, name, is_default_for_new_trip FROM bag_types")).fetchall()
        for bt_id, owner_id, name, is_default in bag_types:
            tipologia = _guess_luggage_type(name)
            result = conn.execute(
                text(
                    "INSERT INTO luggage (owner_id, brand, name, tipologia, "
                    "is_default_for_new_trip, notes, created_at) "
                    "VALUES (:owner_id, '', :name, :tipologia, :is_default, "
                    "'Migrata automaticamente da un vecchio tipo di bagaglio: verificane la tipologia.', "
                    "CURRENT_TIMESTAMP)"
                ),
                {"owner_id": owner_id, "name": name, "tipologia": tipologia, "is_default": bool(is_default)},
            )
            bagtype_to_luggage[bt_id] = result.lastrowid

    # --- Migrazione delle vecchie TripBag verso TripLuggage ------------------
    tripbag_to_tripluggage: dict[int, int] = {}
    if _table_exists(conn, "trip_bags"):
        has_luggage_col = _column_exists(conn, "trip_bags", "luggage_id")
        cols = "id, trip_id, bag_type_id, sort_order" + (", luggage_id" if has_luggage_col else "")
        trip_bags = conn.execute(text(f"SELECT {cols} FROM trip_bags")).fetchall()
        for row in trip_bags:
            tb_id, trip_id, bag_type_id, sort_order = row[0], row[1], row[2], row[3]
            existing_luggage_id = row[4] if has_luggage_col else None

            effective_luggage_id = existing_luggage_id or bagtype_to_luggage.get(bag_type_id)
            if effective_luggage_id is None:
                continue  # nessun modo di sapere quale valigia usare: la riga viene saltata

            owner_row = conn.execute(
                text("SELECT owner_id FROM luggage WHERE id = :lid"), {"lid": effective_luggage_id}
            ).fetchone()
            if owner_row is None:
                continue
            luggage_owner_id = owner_row[0]

            already = conn.execute(
                text("SELECT id FROM trip_luggage WHERE trip_id=:t AND luggage_id=:l"),
                {"t": trip_id, "l": effective_luggage_id},
            ).fetchone()
            if already:
                tripbag_to_tripluggage[tb_id] = already[0]
                continue

            result = conn.execute(
                text(
                    "INSERT INTO trip_luggage (trip_id, luggage_id, user_id, sort_order) "
                    "VALUES (:trip_id, :luggage_id, :user_id, :sort_order)"
                ),
                {"trip_id": trip_id, "luggage_id": effective_luggage_id,
                 "user_id": luggage_owner_id, "sort_order": sort_order},
            )
            tripbag_to_tripluggage[tb_id] = result.lastrowid

    # --- Migrazione delle quantità (trip_item_qty.trip_bag_id -> trip_luggage_id) ---
    if _column_exists(conn, "trip_item_qty", "trip_bag_id"):
        qty_rows = conn.execute(text("SELECT id, trip_bag_id FROM trip_item_qty")).fetchall()
        for qty_id, old_bag_id in qty_rows:
            new_luggage_id = tripbag_to_tripluggage.get(old_bag_id)
            if new_luggage_id is not None:
                conn.execute(
                    text("UPDATE trip_item_qty SET trip_luggage_id = :nl WHERE id = :id"),
                    {"nl": new_luggage_id, "id": qty_id},
                )

    # --- trip_items: attribuisce le righe esistenti al proprietario del viaggio ---
    # (prima della v2.1 la lista era unica e condivisa: al proprietario è
    # l'attribuzione più sensata per non perdere lo stato già inserito).
    conn.execute(
        text(
            "UPDATE trip_items SET user_id = (SELECT owner_id FROM trips WHERE trips.id = trip_items.trip_id) "
            "WHERE user_id IS NULL"
        )
    )
    conn.execute(
        text(
            "UPDATE trip_items SET target_qty = "
            "(SELECT COALESCE(SUM(quantity), 0) FROM trip_item_qty WHERE trip_item_qty.trip_item_id = trip_items.id) "
            "WHERE target_qty IS NULL"
        )
    )

    # --- items.default_luggage_type dal vecchio default_bag_type_id ----------
    if _column_exists(conn, "items", "default_bag_type_id") and _table_exists(conn, "bag_types"):
        items_with_default = conn.execute(
            text("SELECT id, default_bag_type_id FROM items WHERE default_bag_type_id IS NOT NULL")
        ).fetchall()
        for item_id, bag_type_id in items_with_default:
            bt = conn.execute(text("SELECT name FROM bag_types WHERE id = :id"), {"id": bag_type_id}).fetchone()
            if bt:
                conn.execute(
                    text("UPDATE items SET default_luggage_type = :t WHERE id = :id"),
                    {"t": _guess_luggage_type(bt[0]), "id": item_id},
                )


def _migrate_to_v2(conn) -> None:
    """
    Pulizia dati: rimuove eventuali righe `trip_luggage` "orfane" (il cui
    `luggage_id` punta a una valigia ormai eliminata) e le relative
    `trip_item_qty` collegate. Erano un residuo possibile prima della
    correzione del cascade in models.py (eliminare una valigia ancora
    attiva in un viaggio lasciava un riferimento a nulla, mandando in
    errore Home/Viaggi con "AttributeError: 'NoneType' object has no
    attribute 'tipologia'" — bug reale, vedi CHANGELOG). Questa
    migrazione ripara i database già in questo stato; il cascade in
    models.py impedisce che il problema si ripresenti in futuro.
    """
    orphaned = conn.execute(
        text(
            "SELECT id FROM trip_luggage "
            "WHERE luggage_id NOT IN (SELECT id FROM luggage)"
        )
    ).fetchall()
    orphaned_ids = [row[0] for row in orphaned]

    if not orphaned_ids:
        return

    placeholders = ", ".join(f":id{i}" for i in range(len(orphaned_ids)))
    params = {f"id{i}": tl_id for i, tl_id in enumerate(orphaned_ids)}

    conn.execute(
        text(f"DELETE FROM trip_item_qty WHERE trip_luggage_id IN ({placeholders})"),
        params,
    )
    conn.execute(
        text(f"DELETE FROM trip_luggage WHERE id IN ({placeholders})"),
        params,
    )


def _migrate_to_v3(conn) -> None:
    """
    Aggiunge `items.sort_order` (riordino manuale trascinabile all'interno
    di ogni categoria) e lo precompila con l'ordine alfabetico attuale,
    così l'ordine visivo non cambia di colpo al primo avvio di questa
    versione: da qui in poi l'utente può riordinare a mano.
    """
    _add_column(conn, "items", "sort_order", "INTEGER DEFAULT 0")

    rows = conn.execute(
        text("SELECT id, owner_id, category_id FROM items ORDER BY owner_id, category_id, name")
    ).fetchall()

    current_key = None
    order = 0
    for item_id, owner_id, category_id in rows:
        key = (owner_id, category_id)
        order = 0 if key != current_key else order + 1
        current_key = key
        conn.execute(text("UPDATE items SET sort_order = :o WHERE id = :id"), {"o": order, "id": item_id})


def _migrate_to_v4(conn) -> None:
    """
    Ricostruisce `trip_item_qty` se contiene ancora la vecchia colonna
    `trip_bag_id` (schema v1.0/v2.0, con vincolo NOT NULL). `_migrate_to_v1`
    aveva AGGIUNTO `trip_luggage_id` accanto ad essa senza mai rimuovere
    la vecchia colonna — corretto per la filosofia "mai perdere dati",
    ma SQLite non permette di rilassare un vincolo NOT NULL con
    `ALTER TABLE`, quindi quella colonna ormai inutilizzata bloccava
    OGNI NUOVO inserimento con "NOT NULL constraint failed:
    trip_item_qty.trip_bag_id" — impediva letteralmente di aprire un
    viaggio o crearne uno nuovo (bug reale, vedi CHANGELOG). Qui la
    tabella viene ricostruita da zero con lo schema corretto,
    preservando tutte le quantità già collegate a una valigia valida.
    """
    if not _table_exists(conn, "trip_item_qty"):
        return
    if not _column_exists(conn, "trip_item_qty", "trip_bag_id"):
        return  # schema già pulito, niente da fare

    conn.execute(text("ALTER TABLE trip_item_qty RENAME TO trip_item_qty_old_v3"))
    conn.execute(
        text(
            "CREATE TABLE trip_item_qty ("
            "id INTEGER PRIMARY KEY, "
            "trip_item_id INTEGER NOT NULL, "
            "trip_luggage_id INTEGER NOT NULL, "
            "quantity INTEGER NOT NULL DEFAULT 0"
            ")"
        )
    )
    conn.execute(
        text(
            "INSERT INTO trip_item_qty (id, trip_item_id, trip_luggage_id, quantity) "
            "SELECT id, trip_item_id, trip_luggage_id, quantity FROM trip_item_qty_old_v3 "
            "WHERE trip_luggage_id IS NOT NULL"
        )
    )
    conn.execute(text("DROP TABLE trip_item_qty_old_v3"))


def _migrate_to_v5(conn) -> None:
    """Aggiunge trip_items.indossato (per gli oggetti indossati direttamente, non messi in valigia)."""
    _add_column(conn, "trip_items", "indossato", "BOOLEAN DEFAULT 0")


def _migrate_to_v6(conn) -> None:
    """
    Rinomina trip_items.indossato (booleano sì/no) in indossato_qty
    (quantità intera): ora si può specificare QUANTE unità di un
    oggetto si indossano direttamente (es. non posso indossare 13 paia
    di boxer contemporaneamente). SQLite tratta i booleani come interi
    0/1, quindi i valori esistenti restano validi dopo la rinomina.
    """
    if _column_exists(conn, "trip_items", "indossato_qty"):
        return
    if _column_exists(conn, "trip_items", "indossato"):
        conn.execute(text("ALTER TABLE trip_items RENAME COLUMN indossato TO indossato_qty"))
    else:
        _add_column(conn, "trip_items", "indossato_qty", "INTEGER DEFAULT 0")


def _migrate_to_v7(conn) -> None:
    """Crea trip_luggage_shares (condivisione di una valigia con un altro collaboratore dello stesso viaggio)."""
    if _table_exists(conn, "trip_luggage_shares"):
        return
    conn.execute(text(
        "CREATE TABLE trip_luggage_shares ("
        "id INTEGER PRIMARY KEY, "
        "trip_luggage_id INTEGER NOT NULL, "
        "shared_with_user_id INTEGER NOT NULL, "
        "created_at DATETIME, "
        "UNIQUE(trip_luggage_id, shared_with_user_id)"
        ")"
    ))


def _migrate_to_v8(conn) -> None:
    """Aggiunge i campi per termini di ricerca personalizzati, posizione e origine (upload/automatica) della copertina del viaggio."""
    _add_column(conn, "trips", "cover_search_terms", "TEXT")
    _add_column(conn, "trips", "cover_image_position", "TEXT DEFAULT '50% 50%'")
    _add_column(conn, "trips", "cover_image_is_upload", "BOOLEAN DEFAULT 0")


def _migrate_to_v9(conn) -> None:
    """Crea item_variants e trip_item_variant_qty (modelli di un oggetto, es. camicie/pantaloni di taglio diverso, con peso e quantità posseduta propri)."""
    if not _table_exists(conn, "item_variants"):
        conn.execute(text(
            "CREATE TABLE item_variants ("
            "id INTEGER PRIMARY KEY, "
            "item_id INTEGER NOT NULL, "
            "description TEXT NOT NULL, "
            "weight_grams REAL, "
            "owned_qty INTEGER NOT NULL DEFAULT 1, "
            "sort_order INTEGER NOT NULL DEFAULT 0"
            ")"
        ))
    if not _table_exists(conn, "trip_item_variant_qty"):
        conn.execute(text(
            "CREATE TABLE trip_item_variant_qty ("
            "id INTEGER PRIMARY KEY, "
            "trip_item_id INTEGER NOT NULL, "
            "item_variant_id INTEGER NOT NULL, "
            "quantity INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(trip_item_id, item_variant_id)"
            ")"
        ))


def _migrate_to_v10(conn) -> None:
    """Aggiunge le preferenze di visualizzazione del catalogo (icone o testo per regola quantità/tipologia valigia)."""
    _add_column(conn, "users", "catalog_column_style", "TEXT DEFAULT 'auto'")
    _add_column(conn, "users", "catalog_icon_prefs_json", "TEXT")


def _migrate_to_v11(conn) -> None:
    """
    Aggiunge un ordine PER VIAGGIO (trip_items.sort_order), separato da
    quello del catalogo (items.sort_order): prima trascinare un oggetto
    in un viaggio cambiava l'ordine anche nel catalogo e in tutti gli
    altri viaggi (un unico campo condiviso). Le righe già esistenti
    ereditano l'ordine attuale del catalogo come punto di partenza (poi
    restano libere di essere cambiate indipendentemente).
    """
    _add_column(conn, "trip_items", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(text(
        "UPDATE trip_items SET sort_order = ("
        "SELECT items.sort_order FROM items WHERE items.id = trip_items.item_id"
        ") WHERE EXISTS (SELECT 1 FROM items WHERE items.id = trip_items.item_id)"
    ))


def _migrate_to_v12(conn) -> None:
    """Aggiunge l'ordine personale (puramente visivo) delle voci del menu in alto e del sottomenu Catalogo."""
    _add_column(conn, "users", "nav_order_json", "TEXT")


def _migrate_to_v13(conn) -> None:
    """
    Aggiunge trip_luggage_id a trip_item_variant_qty: prima un modello
    (ItemVariant) portato in un viaggio non era legato a NESSUNA
    valigia specifica, quindi il suo peso non finiva mai nel calcolo
    del peso per valigia nella carta d'imbarco (bug reale segnalato,
    "il peso della valigia non cambia aggiungendo oggetti con
    modelli"). Le righe già esistenti vengono assegnate alla PRIMA
    valigia dello stesso proprietario in quel viaggio (la scelta più
    ragionevole senza poter chiedere all'utente); se non ne esiste
    nessuna, la riga viene scartata (nessuna valigia a cui assegnarla —
    andrà semplicemente reinserita dall'utente, dato che senza una
    valigia non aveva comunque alcun effetto sul peso).
    """
    _add_column(conn, "trip_item_variant_qty", "trip_luggage_id", "INTEGER")
    conn.execute(text(
        "UPDATE trip_item_variant_qty "
        "SET trip_luggage_id = ("
        "  SELECT tl.id FROM trip_luggage tl "
        "  JOIN trip_items ti ON ti.trip_id = tl.trip_id AND ti.user_id = tl.user_id "
        "  WHERE ti.id = trip_item_variant_qty.trip_item_id "
        "  ORDER BY tl.id LIMIT 1"
        ") "
        "WHERE trip_luggage_id IS NULL"
    ))
    conn.execute(text("DELETE FROM trip_item_variant_qty WHERE trip_luggage_id IS NULL"))


def _migrate_to_v14(conn) -> None:
    """
    Ricostruisce trip_item_variant_qty per rimuovere il VECCHIO vincolo
    di unicità (trip_item_id, item_variant_id) — creato quando un
    modello non era ancora legato a una valigia specifica. _migrate_to_v13
    ha aggiunto la colonna trip_luggage_id, ma SQLite non permette di
    rimuovere un vincolo di unicità con ALTER TABLE: quel vecchio
    vincolo restava attivo, e impediva di salvare lo STESSO modello in
    DUE valigie diverse dello stesso oggetto — fallendo con
    "UNIQUE constraint failed: trip_item_variant_qty.trip_item_id,
    trip_item_variant_qty.item_variant_id" (bug reale in produzione:
    l'endpoint /api/variante rispondeva con un errore del server invece
    di salvare, percepito come "un errore di comunicazione senza un
    motivo chiaro"). Qui la tabella viene ricostruita da zero con SOLO
    il vincolo corretto su (trip_item_id, item_variant_id, trip_luggage_id).
    """
    if not _table_exists(conn, "trip_item_variant_qty"):
        return

    conn.execute(text("ALTER TABLE trip_item_variant_qty RENAME TO trip_item_variant_qty_old_v13"))
    conn.execute(text(
        "CREATE TABLE trip_item_variant_qty ("
        "id INTEGER PRIMARY KEY, "
        "trip_item_id INTEGER NOT NULL, "
        "item_variant_id INTEGER NOT NULL, "
        "trip_luggage_id INTEGER NOT NULL, "
        "quantity INTEGER NOT NULL DEFAULT 0, "
        "UNIQUE(trip_item_id, item_variant_id, trip_luggage_id)"
        ")"
    ))
    conn.execute(text(
        "INSERT OR IGNORE INTO trip_item_variant_qty "
        "(id, trip_item_id, item_variant_id, trip_luggage_id, quantity) "
        "SELECT id, trip_item_id, item_variant_id, trip_luggage_id, quantity "
        "FROM trip_item_variant_qty_old_v13 "
        "WHERE trip_luggage_id IS NOT NULL"
    ))
    conn.execute(text("DROP TABLE trip_item_variant_qty_old_v13"))


def _migrate_to_v15(conn) -> None:
    """
    Ripulisce righe ORFANE in trip_item_variant_qty: puntavano a una
    valigia (trip_luggage_id) ormai eliminata. Causa: la relazione
    TripLuggage -> TripItemVariantQty non aveva un cascade di
    eliminazione (a differenza di TripLuggage -> TripItemQty, che ce
    l'ha sempre avuto) — eliminare una valigia lasciava le quantità dei
    suoi modelli "appese" nel database, invisibili in qualunque stepper
    (che elenca solo le valigie ancora esistenti) ma CONTATE UGUALMENTE
    nel totale (TripItem.variants_total_qty somma OGNI riga, senza
    verificare se la sua valigia esiste ancora) — gonfiando lo stato
    dell'oggetto (es. mostrato "in valigia" nonostante gli stepper
    visibili sommassero molto meno del necessario: bug reale segnalato,
    "c'è un errore sull'obiettivo che non ha senso").
    """
    if not _table_exists(conn, "trip_item_variant_qty"):
        return
    conn.execute(text(
        "DELETE FROM trip_item_variant_qty "
        "WHERE trip_luggage_id NOT IN (SELECT id FROM trip_luggage)"
    ))


def _migrate_to_v16(conn) -> None:
    """
    Ripulisce righe ORFANE in trip_item_variant_qty: puntavano a un
    MODELLO (item_variant_id) ormai eliminato o modificato. Stessa causa
    di _migrate_to_v15, ma sull'altro lato della riga: la relazione
    ItemVariant -> TripItemVariantQty non aveva un cascade di
    eliminazione — eliminare (o, in casi più rari, sostituire) un
    modello dal catalogo lasciava le quantità già portate in viaggio
    "appese" nel database: invisibili in QUALUNQUE finestra di scelta
    modello (che elenca solo i modelli ancora esistenti dell'oggetto),
    ma CONTATE UGUALMENTE nel totale — causando esattamente il bug
    segnalato: uno stepper mostrava un numero (es. 5) mentre aprendo la
    finestra OGNI modello elencato risultava a 0, e l'obiettivo
    risultava "superato" anche quando la somma visibile era ben al di
    sotto del limite.
    """
    if not _table_exists(conn, "trip_item_variant_qty"):
        return
    conn.execute(text(
        "DELETE FROM trip_item_variant_qty "
        "WHERE item_variant_id NOT IN (SELECT id FROM item_variants)"
    ))


def _migrate_to_v17(conn) -> None:
    """Aggiunge le larghezze di colonna scelte a mano dall'utente, per tabella (solo per la vista testo)."""
    _add_column(conn, "users", "table_column_widths_json", "TEXT")


def _migrate_to_v18(conn) -> None:
    """
    Aggiunge is_public a categories/items/luggage: per scegliere, con
    una spunta, quali oggetti del proprio catalogo personale finiscono
    nel catalogo PUBBLICO esportabile (vedi
    settings/routes.py::export_public_catalog) — tutto parte privato
    per default, va scelto esplicitamente cosa condividere.
    """
    _add_column(conn, "categories", "is_public", "BOOLEAN DEFAULT 0")
    _add_column(conn, "items", "is_public", "BOOLEAN DEFAULT 0")
    _add_column(conn, "luggage", "is_public", "BOOLEAN DEFAULT 0")


# Elenco ordinato delle migrazioni: indice 0 porta alla versione 1, ecc.
_MIGRATIONS = [
    _migrate_to_v1,
    _migrate_to_v2,
    _migrate_to_v3,
    _migrate_to_v4,
    _migrate_to_v5,
    _migrate_to_v6,
    _migrate_to_v7,
    _migrate_to_v8,
    _migrate_to_v9,
    _migrate_to_v10,
    _migrate_to_v11,
    _migrate_to_v12,
    _migrate_to_v13,
    _migrate_to_v14,
    _migrate_to_v15,
    _migrate_to_v16,
    _migrate_to_v17,
    _migrate_to_v18,
]


def run_migrations(app) -> None:
    """Applica tutte le migrazioni non ancora eseguite su questo database. Va chiamata DOPO db.create_all()."""
    from app.extensions import db

    with app.app_context():
        with db.engine.begin() as conn:
            if not _table_exists(conn, "schema_meta"):
                # db.create_all() dovrebbe averla già creata; per sicurezza
                # (es. modelli importati fuori ordine) la creiamo anche qui.
                conn.execute(
                    text("CREATE TABLE IF NOT EXISTS schema_meta (id INTEGER PRIMARY KEY, schema_version INTEGER DEFAULT 0)")
                )

            row = conn.execute(text("SELECT schema_version FROM schema_meta LIMIT 1")).fetchone()
            if row is None:
                conn.execute(text("INSERT INTO schema_meta (schema_version) VALUES (0)"))
                current_version = 0
            else:
                current_version = row[0]

            target_version = len(_MIGRATIONS)
            for version in range(current_version, target_version):
                migration_fn = _MIGRATIONS[version]
                app.logger.info(f"Applico la migrazione #{version + 1} ({migration_fn.__name__})...")
                migration_fn(conn)
                conn.execute(text("UPDATE schema_meta SET schema_version = :v"), {"v": version + 1})
