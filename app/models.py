"""
models.py
=========
Modello dati dell'applicazione "Valigia" — v2.1.

Cambi principali rispetto alla v2.0:

  1. **Le "valigie" sono l'unico concetto di bagaglio.** Non esiste più
     un catalogo separato di "tipi di bagaglio" (BagType): ogni oggetto
     fisico che possiedi (`Luggage`) ha una `tipologia` fissa (cabina /
     stiva / zaino) e viene scelto direttamente, per nome, quando prepari
     un viaggio (`TripLuggage`).

  2. **La lista da mettere in valigia è personale.** Anche su un viaggio
     condiviso, ogni utente ha le PROPRIE righe `TripItem` (quantità,
     "conservato"): non condivide più lo stato di imballaggio con gli
     altri utenti che vedono lo stesso viaggio. Questo vale perché
     `TripItem.item_id` fa sempre riferimento a un Item del catalogo DI
     CHI LO STA COMPILANDO (`TripItem.user_id`), non del proprietario del
     viaggio — due utenti diversi hanno sempre righe Item distinte, anche
     con lo stesso nome, quindi la separazione è automatica.

  3. **Gli acquisti restano condivisi, ma assegnabili.** Il numero di
     unità mancanti (`TripItem.missing_qty`) resta sulla riga personale
     di chi l'ha segnalato, ma può essere assegnato a un altro
     collaboratore del viaggio (`assigned_buyer_id`) che se lo vedrà
     comparire nella propria sezione della lista della spesa condivisa
     (raggruppata per acquirente — vedi `app/utils.py::trip_shopping_summary`).

  4. Resta invariato che **le impostazioni del viaggio** (meta, date,
     note, condivisione, valigie attive) sono un'unica versione condivisa,
     modificabile solo dal proprietario per meta/date/note; la scelta di
     QUALI valigie proprie usare in un viaggio resta invece personale
     (una `TripLuggage` fa riferimento a una Luggage, la cui proprietà ne
     determina automaticamente l'utente).
"""

from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


# ---------------------------------------------------------------------------
# Utenti
# ---------------------------------------------------------------------------
class UserRole:
    ADMIN = "admin"
    MEMBER = "member"


class User(UserMixin, db.Model):
    """Un utente della piattaforma. Username = nickname di accesso, separato dal nome completo."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(150), default="", nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default=UserRole.MEMBER, nullable=False)

    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Preferenze di visualizzazione del catalogo (colonne Regola
    # quantità/Valigia predefinita/Peso come icona o testo) — personali,
    # non condivise tra utenti. "auto" = icone su mobile, testo su
    # desktop (deciso via CSS, nessun controllo lato server sul
    # dispositivo). Vedi DEFAULT_QUANTITY_RULE_ICONS/
    # DEFAULT_LUGGAGE_TYPE_ICONS più sotto per le icone di default.
    catalog_column_style = db.Column(db.String(10), default="auto", nullable=False)
    catalog_icon_prefs_json = db.Column(db.Text, nullable=True)
    # Larghezze di colonna scelte A MANO dall'utente (trascinando il
    # bordo di un'intestazione), per tabella — es. {"catalog-items": [30,19,15,12,24]}.
    # Si applicano SOLO quando la vista è "testo" (mai con le icone, dove
    # non ha senso: le colonne sono già strette per definizione). Una
    # tabella non presente qui usa semplicemente le percentuali di
    # default del CSS.
    table_column_widths_json = db.Column(db.Text, nullable=True)

    def get_column_widths(self, table_key: str) -> list | None:
        import json
        try:
            data = json.loads(self.table_column_widths_json) if self.table_column_widths_json else {}
        except (TypeError, ValueError):
            return None
        widths = data.get(table_key)
        return widths if isinstance(widths, list) and widths else None

    def set_column_widths(self, table_key: str, widths: list) -> None:
        import json
        try:
            data = json.loads(self.table_column_widths_json) if self.table_column_widths_json else {}
        except (TypeError, ValueError):
            data = {}
        data[table_key] = widths
        self.table_column_widths_json = json.dumps(data)

    DEFAULT_QUANTITY_RULE_ICONS = {"fixed": "hash", "per_day": "repeat", "manual": "hand"}
    DEFAULT_LUGGAGE_TYPE_ICONS = {"cabina": "briefcase", "stiva": "package", "zaino": "backpack"}

    def _icon_prefs(self) -> dict:
        import json
        try:
            return json.loads(self.catalog_icon_prefs_json) if self.catalog_icon_prefs_json else {}
        except (TypeError, ValueError):
            return {}

    def quantity_rule_icon(self, rule: str) -> str:
        prefs = self._icon_prefs().get("quantity_rule", {})
        return prefs.get(rule) or self.DEFAULT_QUANTITY_RULE_ICONS.get(rule, "circle")

    def luggage_type_icon(self, tipologia: str) -> str:
        prefs = self._icon_prefs().get("luggage_type", {})
        return prefs.get(tipologia) or self.DEFAULT_LUGGAGE_TYPE_ICONS.get(tipologia, "briefcase")

    def set_icon_prefs(self, quantity_rule_icons: dict, luggage_type_icons: dict) -> None:
        import json
        self.catalog_icon_prefs_json = json.dumps({
            "quantity_rule": quantity_rule_icons,
            "luggage_type": luggage_type_icons,
        })

    # Ordine PERSONALE delle voci del menu in alto e del sottomenu
    # Catalogo — puramente visivo, non cambia nessun comportamento,
    # solo l'ordine di comparsa. Le chiavi non presenti nel valore
    # salvato (es. una voce aggiunta in una versione successiva)
    # vengono semplicemente accodate alla fine, non perse.
    nav_order_json = db.Column(db.Text, nullable=True)

    DEFAULT_NAV_ORDER = ["home", "catalogo", "viaggi", "spesa"]
    DEFAULT_CATALOG_SUBMENU_ORDER = ["oggetti", "categorie", "valigie"]

    def _ordered(self, key: str, default: list) -> list:
        import json
        try:
            saved = json.loads(self.nav_order_json) if self.nav_order_json else {}
        except (TypeError, ValueError):
            saved = {}
        order = saved.get(key) or []
        # Solo chiavi valide, poi quelle mancanti in coda nell'ordine di default.
        order = [k for k in order if k in default]
        order += [k for k in default if k not in order]
        return order

    @property
    def nav_order(self) -> list:
        return self._ordered("top", self.DEFAULT_NAV_ORDER)

    @property
    def catalog_submenu_order(self) -> list:
        return self._ordered("catalogo_submenu", self.DEFAULT_CATALOG_SUBMENU_ORDER)

    def set_nav_order(self, top: list, catalogo_submenu: list) -> None:
        import json
        self.nav_order_json = json.dumps({"top": top, "catalogo_submenu": catalogo_submenu})

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_active(self) -> bool:  # noqa: A003 (nome richiesto da Flask-Login)
        return self.active

    @property
    def display_name(self) -> str:
        """Nome mostrato nell'interfaccia: nome completo se impostato, altrimenti il nickname."""
        return self.full_name.strip() if self.full_name and self.full_name.strip() else self.username

    def __repr__(self):
        return f"<User {self.username}>"


# ---------------------------------------------------------------------------
# Catalogo: Categorie (per utente)
# ---------------------------------------------------------------------------
class Category(db.Model):
    """Categoria di oggetti, di proprietà di un singolo utente."""

    __tablename__ = "categories"
    __table_args__ = (
        db.UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    color = db.Column(db.String(7), default="#8C6D46", nullable=False)
    icon = db.Column(db.String(40), default="shapes", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    # Spuntata dall'utente per includere questa categoria nel catalogo
    # PUBBLICO esportabile (vedi settings/routes.py::export_public_catalog)
    # — di default tutto è privato, va scelto esplicitamente cosa rendere
    # pubblico. Non ha alcun effetto sull'uso normale dell'app.
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    owner = db.relationship("User")
    items = db.relationship(
        "Item", back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Category {self.name} (utente {self.owner_id})>"


# ---------------------------------------------------------------------------
# Valigie fisiche — l'unico concetto di "bagaglio" della v2.1
# ---------------------------------------------------------------------------
class LuggageType:
    """
    Le tre tipologie di valigia riconosciute dall'app. L'ordine di questa
    lista è anche l'ordine di visualizzazione richiesto nella schermata
    di viaggio (cabina, poi stiva, poi zaino).
    """

    CABINA = "cabina"
    STIVA = "stiva"
    ZAINO = "zaino"

    CHOICES = [(CABINA, "Cabina"), (STIVA, "Stiva"), (ZAINO, "Zaino")]
    ORDER = [CABINA, STIVA, ZAINO]
    LABELS = {CABINA: "Cabina", STIVA: "Stiva", ZAINO: "Zaino"}

    @classmethod
    def sort_key(cls, tipologia: str) -> int:
        try:
            return cls.ORDER.index(tipologia)
        except ValueError:
            return len(cls.ORDER)


class Luggage(db.Model):
    """
    Una valigia/borsa reale che possiedi: marca, nome, tipologia (cabina/
    stiva/zaino), peso a vuoto e capacità. È il catalogo da cui scegli,
    viaggio per viaggio, quali borse porti con te (`TripLuggage`).
    """

    __tablename__ = "luggage"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    brand = db.Column(db.String(120), default="", nullable=False)
    name = db.Column(db.String(150), nullable=False)
    tipologia = db.Column(db.String(20), default=LuggageType.STIVA, nullable=False)

    weight_kg = db.Column(db.Float, nullable=True)          # peso a vuoto
    capacity_liters = db.Column(db.Float, nullable=True)

    # Se vera, questa valigia viene proposta automaticamente come attiva
    # su ogni nuovo viaggio (l'utente può comunque toglierla/aggiungerne altre).
    is_default_for_new_trip = db.Column(db.Boolean, default=False, nullable=False)

    notes = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    owner = db.relationship("User")

    # cascade="all, delete-orphan": se elimini questa valigia, vengono
    # eliminate automaticamente anche le righe TripLuggage che la usano
    # in qualunque viaggio (e, a cascata, le relative quantità — vedi
    # TripLuggage.quantities). Prima di questa correzione, eliminare una
    # valigia ancora attiva in un viaggio lasciava un riferimento
    # "orfano" che mandava in errore Home/Viaggi (bug reale, vedi
    # CHANGELOG e app/utils.py::user_trip_luggages).
    trip_luggages = db.relationship(
        "TripLuggage", back_populates="luggage", cascade="all, delete-orphan"
    )

    @property
    def display_name(self) -> str:
        return f"{self.brand} {self.name}".strip() if self.brand else self.name

    @property
    def tipologia_label(self) -> str:
        return LuggageType.LABELS.get(self.tipologia, self.tipologia)

    def __repr__(self):
        return f"<Luggage {self.display_name} ({self.tipologia})>"


# ---------------------------------------------------------------------------
# Catalogo: Oggetti (per utente)
# ---------------------------------------------------------------------------
class QuantityRule:
    MANUAL = "manual"
    FIXED = "fixed"
    PER_DAY = "per_day"

    CHOICES = [
        (MANUAL, "Manuale — la imposto io ogni volta"),
        (FIXED, "Fissa — sempre lo stesso numero"),
        (PER_DAY, "Per giorno — giorni di viaggio + extra"),
    ]


class Item(db.Model):
    """Oggetto "di catalogo", di proprietà di un utente."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category = db.relationship("Category", back_populates="items")

    quantity_rule = db.Column(db.String(20), default=QuantityRule.MANUAL, nullable=False)
    fixed_qty = db.Column(db.Integer, default=1, nullable=False)
    per_day_extra = db.Column(db.Integer, default=1, nullable=False)

    # Tipologia di valigia in cui proporre di default la quantità
    # calcolata automaticamente (non una valigia specifica: quella si
    # sceglie per ogni viaggio). Es. "mutande" -> stiva.
    default_luggage_type = db.Column(db.String(20), nullable=True)

    @property
    def default_luggage_type_label(self) -> str:
        return LuggageType.LABELS.get(self.default_luggage_type, self.default_luggage_type or "")

    weight_grams = db.Column(db.Float, nullable=True)

    # Ordine manuale (trascinamento) all'interno della propria categoria,
    # nella schermata di un viaggio. Spostare un oggetto in un'ALTRA
    # categoria resta possibile solo dal Catalogo (cambiando il campo
    # category_id), non trascinandolo: qui si riordina solo all'interno.
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    notes = db.Column(db.Text, default="", nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User")
    trip_items = db.relationship(
        "TripItem", back_populates="item", cascade="all, delete-orphan"
    )
    variants = db.relationship(
        "ItemVariant", back_populates="item", cascade="all, delete-orphan",
        order_by="ItemVariant.sort_order",
    )

    @property
    def has_variants(self) -> bool:
        return len(self.variants) > 0

    def __repr__(self):
        return f"<Item {self.name} (utente {self.owner_id})>"


class ItemVariant(db.Model):
    """
    Un "modello" specifico di un oggetto che ne ha più d'uno diverso tra
    loro (es. l'oggetto "Camicie" può avere più modelli — "Camicia
    bianca elegante", "Camicia casual azzurra" — ciascuno col proprio
    peso e la propria quantità posseduta). Del tutto facoltativo: un
    oggetto senza modelli si comporta esattamente come sempre (uno
    stepper generico per valigia). Se un oggetto HA modelli, la
    preparazione per un viaggio chiede quanti di CIASCUN modello si
    portano (vedi TripItemVariantQty), invece del generico stepper per
    valigia — così si sa sempre quale modello specifico si sta
    mettendo in valigia, non solo "quante camicie in totale".
    """

    __tablename__ = "item_variants"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    weight_grams = db.Column(db.Float, nullable=True)
    # Quanti ne possiedo di QUESTO modello specifico (non quanti ne porto
    # in un dato viaggio: quello è TripItemVariantQty.quantity).
    owned_qty = db.Column(db.Integer, default=1, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    item = db.relationship("Item", back_populates="variants")
    trip_quantities = db.relationship(
        "TripItemVariantQty", back_populates="item_variant", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ItemVariant {self.description} (oggetto {self.item_id})>"


# ---------------------------------------------------------------------------
# Viaggi
# ---------------------------------------------------------------------------
class Trip(db.Model):
    """Un viaggio: meta, periodo, note. Impostazioni condivise, di proprietà di un utente."""

    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, default="", nullable=False)
    cover_image_url = db.Column(db.String(500), nullable=True)
    # Facoltativi: termini di ricerca personalizzati per l'immagine
    # automatica (invece della sola destinazione) e posizione della
    # copertina nel riquadro (stile "sposta per inquadrare" di Facebook),
    # formato CSS background-position, es. "50% 30%".
    cover_search_terms = db.Column(db.String(200), nullable=True)
    cover_image_position = db.Column(db.String(20), default="50% 50%", nullable=False)
    # Vero se cover_image_url punta a un file caricato dall'utente
    # (servito da trips.cover_image_file) invece che a un'immagine
    # trovata automaticamente su Wikipedia.
    cover_image_is_upload = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User")
    trip_luggages = db.relationship(
        "TripLuggage", back_populates="trip", cascade="all, delete-orphan",
        order_by="TripLuggage.sort_order",
    )
    trip_items = db.relationship(
        "TripItem", back_populates="trip", cascade="all, delete-orphan"
    )
    shares = db.relationship(
        "TripShare", back_populates="trip", cascade="all, delete-orphan"
    )

    @property
    def days(self) -> int:
        delta = (self.end_date - self.start_date).days
        return max(delta + 1, 1)

    @property
    def is_past(self) -> bool:
        return self.end_date < date.today()

    @property
    def is_ongoing(self) -> bool:
        return self.start_date <= date.today() <= self.end_date

    @property
    def is_upcoming(self) -> bool:
        return self.start_date > date.today()

    @property
    def days_to_departure(self) -> int:
        return (self.start_date - date.today()).days

    def is_accessible_by(self, user: "User") -> bool:
        if user.id == self.owner_id:
            return True
        return any(s.user_id == user.id for s in self.shares)

    def collaborators(self) -> list["User"]:
        """Proprietario + tutti gli utenti con cui il viaggio è condiviso."""
        users = [self.owner] + [s.user for s in self.shares]
        seen, out = set(), []
        for u in users:
            if u.id not in seen:
                seen.add(u.id)
                out.append(u)
        return out

    def __repr__(self):
        return f"<Trip {self.destination}>"


class TripShare(db.Model):
    """Concede a un utente l'accesso a un viaggio (impostazioni condivise + lista spesa condivisa)."""

    __tablename__ = "trip_shares"
    __table_args__ = (
        db.UniqueConstraint("trip_id", "user_id", name="uq_tripshare_trip_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trip = db.relationship("Trip", back_populates="shares")
    user = db.relationship("User")


class TripLuggage(db.Model):
    """
    Una valigia attiva per un dato viaggio. `luggage_id` determina anche
    il proprietario (`Luggage.owner_id`): ogni collaboratore di un
    viaggio condiviso sceglie le PROPRIE valigie, indipendentemente dagli
    altri (`user_id` qui è denormalizzato dalla valigia, per query più
    semplici, ma resta sempre coerente con `luggage.owner_id`).
    """

    __tablename__ = "trip_luggage"
    __table_args__ = (
        db.UniqueConstraint("trip_id", "luggage_id", name="uq_trip_luggage"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    luggage_id = db.Column(db.Integer, db.ForeignKey("luggage.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    trip = db.relationship("Trip", back_populates="trip_luggages")
    luggage = db.relationship("Luggage", back_populates="trip_luggages")

    quantities = db.relationship(
        "TripItemQty", back_populates="trip_luggage", cascade="all, delete-orphan"
    )
    variant_quantities = db.relationship(
        "TripItemVariantQty", back_populates="trip_luggage", cascade="all, delete-orphan"
    )
    shares = db.relationship(
        "TripLuggageShare", back_populates="trip_luggage", cascade="all, delete-orphan"
    )

    @property
    def is_shared(self) -> bool:
        return len(self.shares) > 0

    def shared_with_user_ids(self) -> set[int]:
        return {s.shared_with_user_id for s in self.shares}

    def is_usable_by(self, user_id: int) -> bool:
        """Vero se `user_id` può mettere quantità in questa valigia: il proprietario, o chi se l'è vista condividere."""
        return self.user_id == user_id or user_id in self.shared_with_user_ids()

    def __repr__(self):
        return f"<TripLuggage trip={self.trip_id} luggage={self.luggage_id}>"


class TripLuggageShare(db.Model):
    """
    Una valigia (TripLuggage) condivisa dal proprietario con un altro
    collaboratore dello STESSO viaggio: quel collaboratore può mettere
    quantità delle SUE cose (anche oggetti che il proprietario della
    valigia non ha nel proprio catalogo) dentro questa valigia. Il peso
    e il conteggio "in valigia" per questa valigia sommano il contributo
    di TUTTI gli utenti con cui è condivisa, non solo il proprietario.
    """

    __tablename__ = "trip_luggage_shares"
    __table_args__ = (
        db.UniqueConstraint("trip_luggage_id", "shared_with_user_id", name="uq_trip_luggage_share"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_luggage_id = db.Column(db.Integer, db.ForeignKey("trip_luggage.id"), nullable=False)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trip_luggage = db.relationship("TripLuggage", back_populates="shares")
    shared_with = db.relationship("User")


class TripItem(db.Model):
    """
    Riga PERSONALE di imballaggio: lega un Item (del catalogo di
    `user_id`) a un Trip. Due collaboratori dello stesso viaggio hanno
    sempre TripItem distinti (uno per ciascuno), perché fanno riferimento
    a Item diversi (ognuno il proprio) — non esiste possibilità di
    sovrascrittura incrociata.
    """

    __tablename__ = "trip_items"
    __table_args__ = (
        db.UniqueConstraint("trip_id", "item_id", name="uq_trip_item"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    conservato = db.Column(db.Boolean, default=False, nullable=False)  # non più usato per lo stato (ora automatico), conservato solo per compatibilità dati storici

    # Ordine SOLO per questo viaggio: all'inizio eredita l'ordine del
    # catalogo (vedi sync_trip_items), ma da lì in poi è indipendente —
    # trascinare un oggetto in QUESTO viaggio non cambia l'ordine nel
    # catalogo né negli altri viaggi (prima lo faceva per errore,
    # perché non esisteva ancora questo campo separato).
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    # Quante unità di questo oggetto, per questo viaggio, si indossano
    # direttamente invece di metterle in valigia (es. una giacca pesante):
    # contano come "pronte" allo stesso modo di quelle nelle valigie, ma
    # non hanno un peso/ingombro associato a una valigia specifica.
    indossato_qty = db.Column(db.Integer, default=0, nullable=False)
    missing_qty = db.Column(db.Integer, default=0, nullable=False)

    # A chi è assegnato l'acquisto delle unità mancanti (None = se stesso).
    # Permette di dividere gli acquisti tra i collaboratori di un viaggio
    # condiviso pur restando ognuno responsabile della propria lista.
    assigned_buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Quantità "obiettivo" per questo viaggio (di norma pre-compilata
    # dall'automazione, ma modificabile): la somma delle quantità nelle
    # singole valigie non deve necessariamente coinciderci, è solo un
    # riferimento comodo mentre si distribuisce tra più borse.
    target_qty = db.Column(db.Integer, nullable=True)

    note = db.Column(db.Text, default="", nullable=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trip = db.relationship("Trip", back_populates="trip_items")
    item = db.relationship("Item", back_populates="trip_items")
    user = db.relationship("User", foreign_keys=[user_id])
    assigned_buyer = db.relationship("User", foreign_keys=[assigned_buyer_id])

    quantities = db.relationship(
        "TripItemQty", back_populates="trip_item", cascade="all, delete-orphan"
    )
    variant_quantities = db.relationship(
        "TripItemVariantQty", back_populates="trip_item", cascade="all, delete-orphan"
    )

    @property
    def total_qty(self) -> int:
        """Somma nelle valigie (NON include le unità indossate direttamente, né i modelli — vedi variants_total_qty)."""
        return sum(q.quantity for q in self.quantities)

    @property
    def variants_total_qty(self) -> int:
        """Somma di tutti i modelli, in TUTTE le valigie, portati in questo viaggio (solo per oggetti con Item.has_variants)."""
        return sum(vq.quantity for vq in self.variant_quantities)

    def qty_for_variant(self, item_variant_id: int) -> int:
        """Quante unità di questo modello, in TUTTE le valigie insieme (usato per il limite rispetto al posseduto)."""
        return sum(vq.quantity for vq in self.variant_quantities if vq.item_variant_id == item_variant_id)

    def qty_for_variant_in_luggage(self, item_variant_id: int, trip_luggage_id: int) -> int:
        for vq in self.variant_quantities:
            if vq.item_variant_id == item_variant_id and vq.trip_luggage_id == trip_luggage_id:
                return vq.quantity
        return 0

    def variant_breakdown_for_luggage(self, trip_luggage_id: int) -> list:
        """Elenco (ItemVariant, quantità) SOLO dei modelli con quantità > 0 in QUESTA valigia — usato nella finestra di scelta del modello."""
        return [
            (vq.item_variant, vq.quantity)
            for vq in self.variant_quantities
            if vq.trip_luggage_id == trip_luggage_id and vq.quantity > 0
        ]

    @property
    def total_ready_qty(self) -> int:
        """Totale 'pronto' per il viaggio: nelle valigie + indossato direttamente + modelli specificati."""
        return self.total_qty + self.indossato_qty + self.variants_total_qty

    @property
    def owned_qty(self) -> int:
        return max(self.total_ready_qty - self.missing_qty, 0)

    def qty_for_luggage(self, trip_luggage_id: int) -> int:
        """
        Quantità mostrata nello stepper di QUESTA valigia. Per un
        oggetto con modelli, è la somma di TUTTI i modelli in questa
        valigia (TripItemVariantQty) — lo stepper resta identico a
        quello di un oggetto normale nell'aspetto, ma +/- aprono la
        finestra di scelta del modello invece di incrementare
        direttamente (vedi static/js/dashboard.js::initVariantModal).
        """
        if self.item.has_variants:
            return sum(
                vq.quantity for vq in self.variant_quantities if vq.trip_luggage_id == trip_luggage_id
            )
        for q in self.quantities:
            if q.trip_luggage_id == trip_luggage_id:
                return q.quantity
        return 0

    def has_luggage_mismatch(self, trip_luggage_id: int) -> bool:
        """
        Vero se questa valigia ha una tipologia diversa da quella
        predefinita per l'oggetto (Item.default_luggage_type) E contiene
        già una quantità > 0: usato per mostrare un avviso, MAI per
        bloccare o correggere automaticamente la scelta dell'utente.
        """
        if not self.item.default_luggage_type:
            return False
        for q in self.quantities:
            if q.trip_luggage_id == trip_luggage_id and q.quantity > 0:
                return q.trip_luggage.luggage.tipologia != self.item.default_luggage_type
        return False

    @property
    def is_overflowing(self) -> bool:
        """Vero se valigie + indossato superano l'obiettivo impostato (consentito, ma segnalato in UI)."""
        return bool(self.target_qty) and self.total_ready_qty > self.target_qty

    @property
    def status(self) -> str:
        """
        Stato visivo, usato per la colorazione nella dashboard. Interamente
        automatico, basato su obiettivo, quantità nelle valigie e quantità
        indossate direttamente (non più su un check manuale): priorità, in
        quest'ordine:

            "da_comprare"    -> rosso  (missing_qty > 0: manca qualcosa da acquistare)
            "non_necessario" -> grigio (nessun obiettivo impostato per questo viaggio)
            "conservato"     -> verde  (valigie + indossato raggiungono già
                                        l'obiettivo, o di più — vedi status_label
                                        per distinguere "in valigia"/"da indossare")
            "da_preparare"   -> giallo (obiettivo impostato, ma non ancora raggiunto)
        """
        if self.missing_qty > 0:
            return "da_comprare"
        target = self.target_qty or 0
        if target <= 0:
            return "non_necessario"
        if self.total_ready_qty >= target:
            return "conservato"
        return "da_preparare"

    @property
    def status_label(self) -> str:
        """
        Etichetta testuale dello stato. Per il verde ("conservato"),
        distingue se il "pronto" viene da unità in valigia, indossate, o
        entrambe — utile per sapere a colpo d'occhio se serve ancora
        infilare qualcosa in borsa o se è già tutto sistemato/indossato.
        """
        from app.utils import STATUS_LABELS

        if self.status == "conservato" and self.indossato_qty > 0:
            if self.total_qty > 0:
                return "In valigia / da indossare"
            return "Da indossare"
        return STATUS_LABELS[self.status]

    def __repr__(self):
        return f"<TripItem trip={self.trip_id} item={self.item_id} user={self.user_id}>"


class TripItemQty(db.Model):
    """Quantità di un TripItem all'interno di una specifica TripLuggage."""

    __tablename__ = "trip_item_qty"
    __table_args__ = (
        db.UniqueConstraint("trip_item_id", "trip_luggage_id", name="uq_tripitem_luggage"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_item_id = db.Column(db.Integer, db.ForeignKey("trip_items.id"), nullable=False)
    trip_luggage_id = db.Column(db.Integer, db.ForeignKey("trip_luggage.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    trip_item = db.relationship("TripItem", back_populates="quantities")
    trip_luggage = db.relationship("TripLuggage", back_populates="quantities")

    def __repr__(self):
        return f"<TripItemQty item={self.trip_item_id} luggage={self.trip_luggage_id} qty={self.quantity}>"


class TripItemVariantQty(db.Model):
    """
    Quante unità di un MODELLO specifico (ItemVariant) si portano in una
    data VALIGIA, per il TripItem del proprietario. Per gli oggetti con
    modelli definiti, la ripartizione per valigia funziona esattamente
    come TripItemQty (stesso stepper Cabina/Stiva/Zaino) — solo che
    aggiungere un'unità qui chiede QUALE modello si sta aggiungendo
    (tramite una finestra dedicata), invece di un generico +1. Questo è
    ciò che rende visibile il peso reale nella carta d'imbarco: prima
    (senza trip_luggage_id) il peso dei modelli non finiva MAI nel
    conteggio per valigia (bug reale segnalato), perché trip_stats
    calcola il peso SOLO da quantità legate a una valigia specifica.
    """

    __tablename__ = "trip_item_variant_qty"
    __table_args__ = (
        db.UniqueConstraint("trip_item_id", "item_variant_id", "trip_luggage_id", name="uq_tripitem_variant_luggage"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_item_id = db.Column(db.Integer, db.ForeignKey("trip_items.id"), nullable=False)
    item_variant_id = db.Column(db.Integer, db.ForeignKey("item_variants.id"), nullable=False)
    trip_luggage_id = db.Column(db.Integer, db.ForeignKey("trip_luggage.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    trip_item = db.relationship("TripItem", back_populates="variant_quantities")
    trip_luggage = db.relationship("TripLuggage", back_populates="variant_quantities")
    item_variant = db.relationship("ItemVariant", back_populates="trip_quantities")

    def __repr__(self):
        return f"<TripItemVariantQty item={self.trip_item_id} variant={self.item_variant_id} qty={self.quantity}>"


class SchemaMeta(db.Model):
    """
    Tabella a riga singola usata dal sistema di migrazioni leggere (vedi
    app/migrations.py) per ricordare quali migrazioni sono già state
    applicate a questo database, così da renderle sicure da rilanciare
    (idempotenti) e da non riapplicarle ad ogni avvio.
    """

    __tablename__ = "schema_meta"

    id = db.Column(db.Integer, primary_key=True)
    schema_version = db.Column(db.Integer, default=0, nullable=False)
