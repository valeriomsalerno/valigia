"""
tests/test_migration.py
========================
Verifica che `app/migrations.py` converta correttamente un database allo
schema "vecchio" (v2.0.x: tipi di bagaglio separati, lista condivisa
senza `user_id`) nel nuovo schema v2.1 (valigie tipizzate, liste
personali), SENZA PERDITE DI DATI. È il test più importante di questa
versione: una migrazione difettosa significherebbe dati reali persi per
chi aggiorna l'app.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


OLD_SCHEMA_SQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member', must_change_password BOOLEAN NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME
);
CREATE TABLE categories (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#8C6D46', icon TEXT NOT NULL DEFAULT 'shapes', sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE bag_types (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL,
    short_label TEXT NOT NULL DEFAULT 'Borsa', icon TEXT NOT NULL DEFAULT 'luggage',
    sort_order INTEGER NOT NULL DEFAULT 0, is_default_for_new_trip BOOLEAN NOT NULL DEFAULT 0
);
CREATE TABLE luggage (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, brand TEXT NOT NULL DEFAULT '', name TEXT NOT NULL,
    weight_kg REAL, capacity_liters REAL, notes TEXT NOT NULL DEFAULT '', created_at DATETIME
);
CREATE TABLE items (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, category_id INTEGER NOT NULL,
    quantity_rule TEXT NOT NULL DEFAULT 'manual', fixed_qty INTEGER NOT NULL DEFAULT 1,
    per_day_extra INTEGER NOT NULL DEFAULT 1, default_bag_type_id INTEGER, weight_grams REAL,
    notes TEXT NOT NULL DEFAULT '', archived BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME
);
CREATE TABLE trips (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, destination TEXT NOT NULL,
    start_date DATE NOT NULL, end_date DATE NOT NULL, notes TEXT NOT NULL DEFAULT '',
    cover_image_url TEXT, created_at DATETIME
);
CREATE TABLE trip_shares (id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at DATETIME);
CREATE TABLE trip_bags (
    id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, bag_type_id INTEGER NOT NULL,
    luggage_id INTEGER, sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE trip_items (
    id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
    conservato BOOLEAN NOT NULL DEFAULT 0, missing_qty INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', updated_at DATETIME
);
CREATE TABLE trip_item_qty (
    id INTEGER PRIMARY KEY, trip_item_id INTEGER NOT NULL, trip_bag_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0
);
"""

OLD_SCHEMA_DATA = """
INSERT INTO users (id, username, password_hash, role, must_change_password, active)
    VALUES (1, 'admin', 'x', 'admin', 0, 1);
INSERT INTO categories (id, owner_id, name, sort_order) VALUES (1, 1, 'Vestiti', 0);
INSERT INTO bag_types (id, owner_id, name, is_default_for_new_trip) VALUES (1, 1, 'Valigia da stiva', 1);
INSERT INTO bag_types (id, owner_id, name, is_default_for_new_trip) VALUES (2, 1, 'Bagaglio a mano', 1);
INSERT INTO items (id, owner_id, name, category_id, quantity_rule, per_day_extra, default_bag_type_id)
    VALUES (1, 1, 'Calzini', 1, 'per_day', 1, 1);
INSERT INTO trips (id, owner_id, destination, start_date, end_date)
    VALUES (1, 1, 'Roma', '2026-01-01', '2026-01-05');
INSERT INTO trip_bags (id, trip_id, bag_type_id, sort_order) VALUES (1, 1, 1, 0);
INSERT INTO trip_bags (id, trip_id, bag_type_id, sort_order) VALUES (2, 1, 2, 1);
INSERT INTO trip_items (id, trip_id, item_id, conservato, missing_qty) VALUES (1, 1, 1, 1, 0);
INSERT INTO trip_item_qty (id, trip_item_id, trip_bag_id, quantity) VALUES (1, 1, 1, 5);
INSERT INTO trip_item_qty (id, trip_item_id, trip_bag_id, quantity) VALUES (2, 1, 2, 1);
"""


@pytest.fixture()
def old_db_path():
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "valigia.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(OLD_SCHEMA_SQL)
    conn.executescript(OLD_SCHEMA_DATA)
    conn.commit()
    conn.close()
    return tmp_dir, db_path


def test_migration_preserves_data_and_upgrades_schema(old_db_path, monkeypatch):
    tmp_dir, db_path = old_db_path
    monkeypatch.setenv("SECRET_KEY", "test-migration-secret")
    monkeypatch.setenv("VALIGIA_DATABASE_URI_OVERRIDE", f"sqlite:///{db_path}")

    from app import create_app
    app = create_app("development")

    with app.app_context():
        from app.models import Item, Trip, TripLuggage, TripItem, TripItemQty, Luggage, LuggageType

        # --- Le valigie sono state create dai vecchi tipi di bagaglio -------
        stiva = Luggage.query.filter_by(owner_id=1, name="Valigia da stiva").first()
        cabina = Luggage.query.filter_by(owner_id=1, name="Bagaglio a mano").first()
        assert stiva is not None and cabina is not None
        assert stiva.tipologia == LuggageType.STIVA
        assert cabina.tipologia == LuggageType.CABINA
        assert stiva.is_default_for_new_trip is True

        # --- Le TripLuggage sono state create per il viaggio esistente -------
        trip = Trip.query.get(1)
        trip_luggages = TripLuggage.query.filter_by(trip_id=trip.id).all()
        assert len(trip_luggages) == 2
        luggage_ids = {tl.luggage_id for tl in trip_luggages}
        assert luggage_ids == {stiva.id, cabina.id}
        assert all(tl.user_id == 1 for tl in trip_luggages)

        # --- Le quantità sono state trasferite senza perdite -----------------
        trip_item = TripItem.query.get(1)
        assert trip_item.user_id == 1  # attribuito al proprietario del viaggio
        assert trip_item.conservato is True
        assert trip_item.target_qty == 6  # 5 + 1, backfillato dalla somma esistente

        qty_rows = TripItemQty.query.filter_by(trip_item_id=trip_item.id).all()
        assert len(qty_rows) == 2
        by_luggage = {q.trip_luggage.luggage_id: q.quantity for q in qty_rows}
        assert by_luggage[stiva.id] == 5
        assert by_luggage[cabina.id] == 1

        # --- L'automazione dell'oggetto punta ora alla tipologia giusta ------
        item = Item.query.get(1)
        assert item.default_luggage_type == LuggageType.STIVA

        # --- LA VERIFICA DECISIVA: dopo la migrazione si può inserire una
        # nuova riga (esattamente quello che sync_trip_items/api/quantita
        # fanno per un oggetto nuovo). Bug reale: la vecchia colonna
        # trip_bag_id restava NOT NULL anche dopo l'aggiunta di
        # trip_luggage_id, bloccando OGNI nuovo inserimento con
        # "NOT NULL constraint failed: trip_item_qty.trip_bag_id" —
        # impediva di aprire un viaggio o crearne uno nuovo.
        new_qty = TripItemQty(trip_item_id=trip_item.id, trip_luggage_id=trip_luggages[0].id, quantity=0)
        from app.extensions import db
        db.session.add(new_qty)
        db.session.commit()  # non deve sollevare IntegrityError
        assert new_qty.id is not None

        # --- La migrazione è idempotente: rilanciarla non duplica nulla -------
        from app.migrations import run_migrations
        run_migrations(app)
        assert TripLuggage.query.filter_by(trip_id=trip.id).count() == 2
        assert Luggage.query.filter_by(owner_id=1).count() == 2
        # ...e non ha ricreato la vecchia colonna né perso la riga appena inserita.
        assert TripItemQty.query.get(new_qty.id) is not None


def test_migration_v2_removes_orphaned_trip_luggage(monkeypatch):
    """
    Bug reale segnalato dall'utente: eliminare una valigia ancora attiva
    in un viaggio lasciava un riferimento "orfano" in `trip_luggage`
    (SQLite non applica i vincoli di integrità referenziale di default),
    mandando in errore Home/Viaggi con
    "AttributeError: 'NoneType' object has no attribute 'tipologia'".

    Simula esattamente questo stato (già presente in un database v2.1.1
    reale) e verifica che la migrazione lo ripari senza intervento manuale.
    """
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "valigia.db"

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT DEFAULT '',
            password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
            must_change_password BOOLEAN NOT NULL DEFAULT 1, active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#8C6D46', icon TEXT NOT NULL DEFAULT 'shapes',
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE luggage (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, brand TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL, tipologia TEXT DEFAULT 'stiva', weight_kg REAL, capacity_liters REAL,
            is_default_for_new_trip BOOLEAN DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at DATETIME
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, category_id INTEGER NOT NULL,
            quantity_rule TEXT NOT NULL DEFAULT 'manual', fixed_qty INTEGER NOT NULL DEFAULT 1,
            per_day_extra INTEGER NOT NULL DEFAULT 1, default_luggage_type TEXT, weight_grams REAL,
            notes TEXT NOT NULL DEFAULT '', archived BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME
        );
        CREATE TABLE trips (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, destination TEXT NOT NULL,
            start_date DATE NOT NULL, end_date DATE NOT NULL, notes TEXT NOT NULL DEFAULT '',
            cover_image_url TEXT, created_at DATETIME
        );
        CREATE TABLE trip_shares (id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at DATETIME);
        CREATE TABLE trip_luggage (
            id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, luggage_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE trip_items (
            id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, item_id INTEGER NOT NULL, user_id INTEGER,
            conservato BOOLEAN NOT NULL DEFAULT 0, missing_qty INTEGER NOT NULL DEFAULT 0,
            assigned_buyer_id INTEGER, target_qty INTEGER, note TEXT NOT NULL DEFAULT '', updated_at DATETIME
        );
        CREATE TABLE trip_item_qty (
            id INTEGER PRIMARY KEY, trip_item_id INTEGER NOT NULL, trip_luggage_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE schema_meta (id INTEGER PRIMARY KEY, schema_version INTEGER DEFAULT 0);

        INSERT INTO users (id, username, password_hash, role, must_change_password) VALUES (1, 'admin', 'x', 'admin', 0);
        INSERT INTO categories (id, owner_id, name) VALUES (1, 1, 'Vestiti');
        INSERT INTO luggage (id, owner_id, name, tipologia) VALUES (1, 1, 'Valigia da stiva', 'stiva');
        -- NB: la valigia id=2 ("Bagaglio a mano") NON esiste più: è stata eliminata
        -- mentre era ancora attiva sul viaggio, lasciando trip_luggage id=2 orfana.
        INSERT INTO items (id, owner_id, name, category_id) VALUES (1, 1, 'Calzini', 1);
        INSERT INTO trips (id, owner_id, destination, start_date, end_date) VALUES (1, 1, 'Roma', '2026-01-01', '2026-01-05');
        INSERT INTO trip_luggage (id, trip_id, luggage_id, user_id, sort_order) VALUES (1, 1, 1, 1, 0);
        INSERT INTO trip_luggage (id, trip_id, luggage_id, user_id, sort_order) VALUES (2, 1, 2, 1, 1);
        INSERT INTO trip_items (id, trip_id, item_id, user_id, conservato) VALUES (1, 1, 1, 1, 0);
        INSERT INTO trip_item_qty (id, trip_item_id, trip_luggage_id, quantity) VALUES (1, 1, 1, 3);
        INSERT INTO trip_item_qty (id, trip_item_id, trip_luggage_id, quantity) VALUES (2, 1, 2, 2);
        INSERT INTO schema_meta (id, schema_version) VALUES (1, 1);
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("VALIGIA_DATABASE_URI_OVERRIDE", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-migration-v2-secret")

    from app import create_app
    app = create_app("development")

    with app.app_context():
        from app.models import TripLuggage, TripItemQty, Trip, User

        # La riga orfana (valigia 2, eliminata) è stata ripulita...
        assert TripLuggage.query.get(2) is None
        assert TripItemQty.query.filter_by(trip_luggage_id=2).count() == 0

        # ...ma quella valida (valigia 1) resta intatta.
        assert TripLuggage.query.get(1) is not None
        assert TripItemQty.query.filter_by(trip_luggage_id=1).first().quantity == 3

        # La pagina Home/Viaggi (che prima andava in errore) ora funziona.
        admin = User.query.first()
        from app.utils import user_trip_luggages, trip_stats
        trip = Trip.query.first()
        assert len(user_trip_luggages(trip, admin)) == 1
        stats = trip_stats(trip, admin)  # non deve sollevare AttributeError
        assert len(stats["luggages"]) == 1


def test_migration_v13_v14_fixes_variant_unique_constraint(monkeypatch):
    """
    Bug reale in produzione: `trip_item_variant_qty` veniva creata (v9)
    con un vincolo di unicità su (trip_item_id, item_variant_id) — da
    quando un modello è diventato legato a una valigia specifica (v13),
    quel vecchio vincolo impediva di salvare LO STESSO modello in DUE
    valigie diverse, fallendo con "UNIQUE constraint failed" (500
    dell'endpoint /api/variante, percepito come "un errore di
    comunicazione senza un motivo chiaro"). Simula esattamente lo
    schema v9-senza-v14 (colonna trip_luggage_id già presente, ma
    ancora col vecchio vincolo a 2 colonne) e verifica che la
    migrazione lo ripari senza perdita di dati.
    """
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "valigia.db"

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT DEFAULT '',
            password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
            must_change_password BOOLEAN NOT NULL DEFAULT 1, active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME, catalog_column_style TEXT DEFAULT 'auto',
            catalog_icon_prefs_json TEXT, nav_order_json TEXT
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#8C6D46', icon TEXT NOT NULL DEFAULT 'shapes',
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE luggage (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, brand TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL, tipologia TEXT DEFAULT 'stiva', weight_kg REAL, capacity_liters REAL,
            is_default_for_new_trip BOOLEAN DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at DATETIME
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, category_id INTEGER NOT NULL,
            quantity_rule TEXT NOT NULL DEFAULT 'manual', fixed_qty INTEGER NOT NULL DEFAULT 1,
            per_day_extra INTEGER NOT NULL DEFAULT 1, default_luggage_type TEXT, weight_grams REAL,
            notes TEXT NOT NULL DEFAULT '', archived BOOLEAN NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME
        );
        CREATE TABLE item_variants (
            id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, description TEXT NOT NULL,
            weight_grams REAL, owned_qty INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE trips (
            id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, destination TEXT NOT NULL,
            start_date DATE NOT NULL, end_date DATE NOT NULL, notes TEXT NOT NULL DEFAULT '',
            cover_image_url TEXT, created_at DATETIME
        );
        CREATE TABLE trip_luggage (
            id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, luggage_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE trip_items (
            id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL, item_id INTEGER NOT NULL, user_id INTEGER,
            conservato BOOLEAN NOT NULL DEFAULT 0, missing_qty INTEGER NOT NULL DEFAULT 0,
            assigned_buyer_id INTEGER, target_qty INTEGER, note TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0, updated_at DATETIME
        );
        CREATE TABLE trip_item_qty (
            id INTEGER PRIMARY KEY, trip_item_id INTEGER NOT NULL, trip_luggage_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0
        );
        -- Esattamente lo schema dopo v13: la colonna trip_luggage_id è già
        -- stata aggiunta, ma il vincolo di unicità è ancora quello VECCHIO
        -- a 2 colonne (v9), perché ALTER TABLE non può rimuoverlo da solo.
        CREATE TABLE trip_item_variant_qty (
            id INTEGER PRIMARY KEY, trip_item_id INTEGER NOT NULL, item_variant_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0, trip_luggage_id INTEGER,
            UNIQUE(trip_item_id, item_variant_id)
        );
        CREATE TABLE schema_meta (id INTEGER PRIMARY KEY, schema_version INTEGER DEFAULT 0);

        INSERT INTO users (id, username, password_hash, role, must_change_password) VALUES (1, 'admin', 'x', 'admin', 0);
        INSERT INTO categories (id, owner_id, name) VALUES (1, 1, 'Vestiti');
        INSERT INTO luggage (id, owner_id, name, tipologia) VALUES (1, 1, 'Zaino cabina', 'cabina');
        INSERT INTO luggage (id, owner_id, name, tipologia) VALUES (2, 1, 'Trolley stiva', 'stiva');
        INSERT INTO items (id, owner_id, name, category_id) VALUES (1, 1, 'Camicie', 1);
        INSERT INTO item_variants (id, item_id, description, weight_grams, owned_qty) VALUES (1, 1, 'Bianca elegante', 200, 3);
        INSERT INTO trips (id, owner_id, destination, start_date, end_date) VALUES (1, 1, 'Kyoto', '2026-01-01', '2026-01-10');
        INSERT INTO trip_luggage (id, trip_id, luggage_id, user_id, sort_order) VALUES (1, 1, 1, 1, 0);
        INSERT INTO trip_luggage (id, trip_id, luggage_id, user_id, sort_order) VALUES (2, 1, 2, 1, 1);
        INSERT INTO trip_items (id, trip_id, item_id, user_id) VALUES (1, 1, 1, 1);
        -- Un modello già presente in UNA valigia (stato reale prima del bug).
        INSERT INTO trip_item_variant_qty (id, trip_item_id, item_variant_id, quantity, trip_luggage_id) VALUES (1, 1, 1, 1, 1);
        INSERT INTO schema_meta (id, schema_version) VALUES (1, 13);
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("VALIGIA_DATABASE_URI_OVERRIDE", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-migration-v14-secret")

    from app import create_app
    app = create_app("development")

    with app.app_context():
        from app.extensions import db
        from app.models import TripItemVariantQty

        # Il dato esistente non è andato perso.
        existing = TripItemVariantQty.query.get(1)
        assert existing is not None
        assert existing.trip_luggage_id == 1
        assert existing.quantity == 1

        # LA VERIFICA DECISIVA: si può ora salvare lo STESSO modello in
        # un'ALTRA valigia dello stesso oggetto — prima falliva con
        # "UNIQUE constraint failed" (bug reale in produzione).
        second = TripItemVariantQty(trip_item_id=1, item_variant_id=1, trip_luggage_id=2, quantity=1)
        db.session.add(second)
        db.session.commit()  # non deve sollevare IntegrityError
        assert second.id is not None

        # Ma il vincolo corretto (stessa valigia, stesso modello, due
        # righe) resta comunque attivo — non deve diventare "senza
        # vincoli del tutto".
        with pytest.raises(Exception):
            dup = TripItemVariantQty(trip_item_id=1, item_variant_id=1, trip_luggage_id=1, quantity=5)
            db.session.add(dup)
            db.session.commit()
        db.session.rollback()
