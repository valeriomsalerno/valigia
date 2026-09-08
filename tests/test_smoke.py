"""
tests/test_smoke.py
====================
Test unitari mirati sulle parti più delicate della v2.1: automazioni
quantità, sincronizzazione PERSONALE del catalogo con un viaggio, e
soprattutto l'isolamento tra le liste di due collaboratori sullo stesso
viaggio condiviso (il bug esplicitamente segnalato e corretto in questa
versione: prima un utente modificava e l'altro si ritrovava la stessa
modifica).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Category, Item, Trip, TripShare, User, UserRole, QuantityRule,
    Luggage, LuggageType, TripLuggage, TripItemQty, TripLuggageShare, TripItem,
    ItemVariant, TripItemVariantQty,
)
from app.utils import (
    compute_auto_quantity, sync_trip_items, ensure_default_trip_luggages,
    recompute_automatic_quantities, trip_stats, provision_new_user_defaults,
    accessible_trips_query, trip_shopping_summary, user_trip_luggages,
    luggage_display_labels,
)


@pytest.fixture()
def app():
    return create_app("testing")


def _make_second_user(app, username="familiare") -> User:
    with app.app_context():
        u = User(username=username, role=UserRole.MEMBER, must_change_password=False)
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        provision_new_user_defaults(u)
        return User.query.filter_by(username=username).first()


def _make_trip(owner: User, days: int) -> Trip:
    trip = Trip(
        owner_id=owner.id,
        destination="Kyoto",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=days - 1),
    )
    db.session.add(trip)
    db.session.commit()
    ensure_default_trip_luggages(trip, owner)
    return trip


def test_admin_created_with_luggage_and_base_catalog(app):
    with app.app_context():
        admin = User.query.first()
        assert admin.is_admin
        assert Item.query.filter_by(owner_id=admin.id).count() > 30
        luggages = Luggage.query.filter_by(owner_id=admin.id).all()
        assert len(luggages) == 2
        assert {l.tipologia for l in luggages} == {LuggageType.STIVA, LuggageType.CABINA}


def test_per_day_and_fixed_quantity_rules(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        calzini = Item(owner_id=admin.id, name="Calzini test", category_id=cat.id,
                        quantity_rule=QuantityRule.PER_DAY, per_day_extra=1)
        iphone = Item(owner_id=admin.id, name="iPhone test", category_id=cat.id,
                       quantity_rule=QuantityRule.FIXED, fixed_qty=1)
        db.session.add_all([calzini, iphone])
        db.session.commit()

        trip = _make_trip(admin, days=10)
        assert trip.days == 10
        assert compute_auto_quantity(calzini, trip) == 11
        assert compute_auto_quantity(iphone, trip) == 1


def test_sync_creates_personal_trip_items_with_target_qty(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Mutande test", category_id=cat.id,
                    quantity_rule=QuantityRule.PER_DAY, per_day_extra=1,
                    default_luggage_type=LuggageType.STIVA)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=5)
        sync_trip_items(trip, admin)

        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        assert ti.user_id == admin.id
        assert ti.target_qty == 6  # 5 + 1
        # La distribuzione nelle valigie resta SEMPRE a zero: mai
        # pre-compilata dall'automazione, va scelta a mano dall'utente
        # (bug reale corretto: prima finiva tutta nella valigia della
        # tipologia predefinita anche se l'utente non l'aveva scelto).
        assert ti.total_qty == 0


def test_missing_qty_drives_status_and_owned_qty(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Oggetto test", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)

        assert ti.status == "non_necessario"

        ti.missing_qty = 2
        db.session.commit()
        assert ti.status == "da_comprare"
        assert ti.owned_qty == 0  # total_qty è 0, quindi owned = max(0-2, 0)


# ---------------------------------------------------------------------------
# IL TEST CHE CONTA DI PIÙ: isolamento tra collaboratori di un viaggio condiviso
# ---------------------------------------------------------------------------
def test_shared_trip_gives_each_collaborator_an_independent_packing_list(app):
    with app.app_context():
        admin = User.query.first()
        second = _make_second_user(app)

        trip = _make_trip(admin, days=4)
        db.session.add(TripShare(trip_id=trip.id, user_id=second.id))
        db.session.commit()

        # Entrambi sincronizzano la LORO lista personale sullo stesso viaggio.
        sync_trip_items(trip, admin)
        ensure_default_trip_luggages(trip, second)
        sync_trip_items(trip, second)

        admin_items = {ti.item_id for ti in trip.trip_items if ti.user_id == admin.id}
        second_items = {ti.item_id for ti in trip.trip_items if ti.user_id == second.id}

        # Le liste sono fatte di Item DIVERSI (ognuno il proprio catalogo):
        # nessuna sovrapposizione possibile per costruzione.
        assert admin_items.isdisjoint(second_items)
        assert len(admin_items) > 30
        assert len(second_items) > 30

        # L'admin spunta "conservato" su un suo oggetto...
        admin_ti = next(ti for ti in trip.trip_items if ti.user_id == admin.id)
        admin_ti.conservato = True
        admin_ti.missing_qty = 3
        db.session.commit()

        # ...e questo NON deve influenzare in alcun modo la riga corrispondente
        # (stesso nome oggetto) dell'altro collaboratore.
        second_ti_same_name = next(
            (ti for ti in trip.trip_items if ti.user_id == second.id and ti.item.name == admin_ti.item.name),
            None,
        )
        assert second_ti_same_name is not None
        assert second_ti_same_name.id != admin_ti.id
        assert second_ti_same_name.conservato is False
        assert second_ti_same_name.missing_qty == 0

        # Anche le valigie attive sono indipendenti: rimuoverne una all'admin
        # non deve toccare quelle del collaboratore.
        admin_luggages = [tl for tl in trip.trip_luggages if tl.user_id == admin.id]
        second_luggages = [tl for tl in trip.trip_luggages if tl.user_id == second.id]
        assert len(admin_luggages) == 2
        assert len(second_luggages) == 2
        assert {tl.id for tl in admin_luggages}.isdisjoint({tl.id for tl in second_luggages})


def test_trip_share_grants_access_but_not_ownership(app):
    with app.app_context():
        admin = User.query.first()
        second = _make_second_user(app)
        trip = _make_trip(admin, days=5)

        assert trip.is_accessible_by(second) is False
        db.session.add(TripShare(trip_id=trip.id, user_id=second.id))
        db.session.commit()

        assert trip.is_accessible_by(second) is True
        assert trip.owner_id == admin.id  # la proprietà non cambia
        ids = {t.id for t in accessible_trips_query(second).all()}
        assert trip.id in ids


def test_shopping_summary_groups_by_assigned_buyer(app):
    with app.app_context():
        admin = User.query.first()
        second = _make_second_user(app)
        trip = _make_trip(admin, days=4)
        db.session.add(TripShare(trip_id=trip.id, user_id=second.id))
        db.session.commit()
        sync_trip_items(trip, admin)

        ti = trip.trip_items[0]
        ti.missing_qty = 2
        db.session.commit()

        summary = trip_shopping_summary(trip)
        buyers = {g["user"].id: len(g["missing_items"]) for g in summary}
        assert buyers[admin.id] == 1  # non riassegnato: resta a chi l'ha segnalato
        assert buyers[second.id] == 0

        # Riassegna l'acquisto al secondo utente.
        ti.assigned_buyer_id = second.id
        db.session.commit()
        summary2 = trip_shopping_summary(trip)
        buyers2 = {g["user"].id: len(g["missing_items"]) for g in summary2}
        assert buyers2[admin.id] == 0
        assert buyers2[second.id] == 1


def test_recompute_updates_target_only_never_luggage_quantity(app):
    """recompute_automatic_quantities aggiorna SOLO target_qty: la distribuzione
    nelle valigie resta quella scelta a mano dall'utente, mai toccata."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Calze test", category_id=cat.id,
                    quantity_rule=QuantityRule.PER_DAY, per_day_extra=1,
                    default_luggage_type=LuggageType.STIVA)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=5)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        assert ti.target_qty == 6
        assert ti.total_qty == 0

        # L'utente mette a mano 2 calze in una valigia (scelta sua, non
        # legata alla tipologia predefinita dell'oggetto).
        tl = trip.trip_luggages[0]
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == tl.id)
        qty_row.quantity = 2
        db.session.commit()

        trip.end_date = trip.end_date + timedelta(days=5)  # ora 10 giorni
        db.session.commit()
        updated = recompute_automatic_quantities(trip, admin)

        db.session.refresh(ti)
        assert updated >= 1
        assert ti.target_qty == 11  # ricalcolato
        assert ti.total_qty == 2    # INVARIATO: mai toccato dal ricalcolo


def test_trip_stats_includes_weight_per_luggage(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Libro test", category_id=cat.id, weight_grams=400)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        stiva_tl = next(tl for tl in trip.trip_luggages if tl.luggage.tipologia == LuggageType.STIVA)
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == stiva_tl.id)
        qty_row.quantity = 3
        db.session.commit()

        stats = trip_stats(trip, admin)
        stiva_stats = next(l for l in stats["luggages"] if l["trip_luggage_id"] == stiva_tl.id)
        assert stiva_stats["content_weight_grams"] == 1200  # 400g * 3


def test_decimal_comma_float_field_follows_italian_convention(app):
    """
    Bug reale segnalato dall'utente: modificare una valigia (es. rinominare
    "Bagaglio a mano") falliva SENZA alcun errore visibile se il campo
    peso/capacità veniva scritto con la virgola come separatore decimale
    (abitudine naturale in italiano), perché WTForms si aspettava il
    punto. Il salvataggio dell'intero form falliva silenziosamente, dando
    l'impressione che "non si salvi il nome".

    La correzione segue la convenzione italiana/internazionale ESATTA
    (non una semplice tolleranza punto-o-virgola): il PUNTO è SEMPRE il
    separatore delle migliaia, la VIRGOLA è SEMPRE quello decimale.
    Vedi app/forms.py::DecimalCommaFloatField e app/utils.py::parse_number_it.
    """
    from app.forms import LuggageForm

    # Virgola come decimale: il caso del bug originale.
    with app.test_request_context(
        method="POST",
        data={
            "name": "Bagaglio a mano RINOMINATO", "brand": "", "tipologia": "cabina",
            "weight_kg": "2,5", "capacity_liters": "40,0", "notes": "",
        },
    ):
        form = LuggageForm(meta={"csrf": False})
        assert form.validate() is True, form.errors
        assert form.weight_kg.data == 2.5
        assert form.capacity_liters.data == 40.0

    # Punto come separatore delle MIGLIAIA (non decimale!): "1.500" -> 1500,
    # non 1.5 (usiamo il peso in grammi di un oggetto, dove 1500 è plausibile;
    # il peso di una valigia in kg ha un massimo di 200, quindi non si presta).
    from app.forms import ItemForm
    with app.app_context():
        from app.models import Category, User
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
    with app.test_request_context(
        method="POST",
        data={
            "name": "Laptop", "category_id": str(cat.id), "quantity_rule": "manual",
            "fixed_qty": "1", "per_day_extra": "1", "default_luggage_type": "",
            "weight_grams": "1.500", "notes": "",
        },
    ):
        item_form = ItemForm(meta={"csrf": False})
        item_form.category_id.choices = [(cat.id, cat.name)]
        item_form.default_luggage_type.choices = [("", "—")]
        assert item_form.validate() is True, item_form.errors
        assert item_form.weight_grams.data == 1500.0

    # Punto E virgola insieme: "1.500,25" -> 1500.25 (caso non ambiguo).
    with app.test_request_context(
        method="POST",
        data={
            "name": "Baule", "brand": "", "tipologia": "stiva",
            "weight_kg": "150,25", "capacity_liters": "", "notes": "",
        },
    ):
        form = LuggageForm(meta={"csrf": False})
        assert form.validate() is True, form.errors
        assert form.weight_kg.data == 150.25


def test_decimal_comma_float_field_round_trips_existing_values(app):
    """
    Un valore già salvato (es. 2.5) deve ripresentarsi nel campo in
    formato italiano ("2,5") e, se ripresentato SENZA modifiche, deve
    tornare a salvarsi come lo stesso identico numero — non deve MAI
    corrompersi in un valore diverso solo perché si riapre il modulo e
    si preme "Salva" senza toccare quel campo.
    """
    from app.forms import DecimalCommaFloatField
    from wtforms import Form as BaseForm

    class _F(BaseForm):
        peso = DecimalCommaFloatField()

    # Valore piccolo, sotto le migliaia.
    f = _F(data={"peso": 2.5})
    assert f.peso._value() == "2,5"

    # Valore sopra le migliaia: deve ripresentarsi con il punto raggruppante.
    f2 = _F(data={"peso": 1500.0})
    assert f2.peso._value() == "1.500"


def test_deleting_luggage_cascades_to_trip_luggage(app):
    """
    Bug reale segnalato dall'utente: eliminare una valigia ancora attiva
    in un viaggio lasciava un riferimento "orfano" in TripLuggage
    (SQLite non applica di default i vincoli di integrità referenziale),
    causando un crash su Home/Viaggi ("AttributeError: 'NoneType' object
    has no attribute 'tipologia'"). Ora l'eliminazione di una Luggage
    deve rimuovere automaticamente anche le TripLuggage (e le relative
    TripItemQty) che la usano — vedi models.py, cascade su Luggage.trip_luggages.
    """
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=5)

        extra = Luggage(owner_id=admin.id, name="Zaino da eliminare", tipologia=LuggageType.ZAINO)
        db.session.add(extra)
        db.session.commit()

        tl = TripLuggage(trip_id=trip.id, luggage_id=extra.id, user_id=admin.id, sort_order=99)
        db.session.add(tl)
        db.session.commit()
        tl_id = tl.id

        sync_trip_items(trip, admin)
        # Aggiunge una quantità su questa valigia, per verificare che anche
        # TripItemQty venga ripulita a cascata (sync_trip_items ha già
        # creato la riga per ogni valigia attiva: la aggiorniamo).
        ti = trip.trip_items[0]
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == tl_id)
        qty_row.quantity = 2
        db.session.commit()

        db.session.delete(extra)
        db.session.commit()

        assert TripLuggage.query.get(tl_id) is None
        assert TripItemQty.query.filter_by(trip_luggage_id=tl_id).count() == 0

        # E soprattutto: la pagina che prima andava in errore ora funziona.
        stats = trip_stats(trip, admin)
        assert all(lug["trip_luggage_id"] != tl_id for lug in stats["luggages"])


def test_status_is_fully_automatic_from_target_vs_quantities(app):
    """
    Nuova logica di stato (v2.2): niente più check manuale "conservato".
    - obiettivo 0/non impostato -> non_necessario (grigio)
    - obiettivo > 0 ma somma nelle valigie < obiettivo -> da_preparare (giallo)
    - somma nelle valigie >= obiettivo -> conservato (verde)
    - missing_qty > 0 ha sempre la priorità più alta -> da_comprare (rosso)
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Test stato", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        tl = trip.trip_luggages[0]

        # Nessun obiettivo impostato -> grigio, anche a costo zero.
        assert ti.target_qty in (None, 0)
        assert ti.status == "non_necessario"

        # Obiettivo impostato, ancora nulla nelle valigie -> giallo.
        ti.target_qty = 5
        db.session.commit()
        assert ti.status == "da_preparare"

        # Parzialmente riempito, sotto l'obiettivo -> ancora giallo.
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == tl.id)
        qty_row.quantity = 3
        db.session.commit()
        assert ti.total_qty == 3
        assert ti.status == "da_preparare"
        assert ti.is_overflowing is False

        # Raggiunto l'obiettivo esatto -> verde.
        qty_row.quantity = 5
        db.session.commit()
        assert ti.status == "conservato"
        assert ti.is_overflowing is False

        # Superato l'obiettivo -> resta verde, ma segnalato come "in eccesso".
        qty_row.quantity = 7
        db.session.commit()
        assert ti.status == "conservato"
        assert ti.is_overflowing is True

        # Qualcosa da comprare ha SEMPRE la priorità, anche se l'obiettivo è già raggiunto.
        ti.missing_qty = 1
        db.session.commit()
        assert ti.status == "da_comprare"


def test_reorder_items_persists_within_category(app):
    """Il riordino manuale (trascinamento) aggiorna sort_order e non tocca la categoria."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        i1 = Item(owner_id=admin.id, name="Uno", category_id=cat.id, sort_order=0)
        i2 = Item(owner_id=admin.id, name="Due", category_id=cat.id, sort_order=1)
        i3 = Item(owner_id=admin.id, name="Tre", category_id=cat.id, sort_order=2)
        db.session.add_all([i1, i2, i3])
        db.session.commit()

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.post("/api/riordina-oggetti", json={"item_ids": [i3.id, i1.id, i2.id]})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        db.session.refresh(i1)
        db.session.refresh(i2)
        db.session.refresh(i3)
        assert i3.sort_order == 0
        assert i1.sort_order == 1
        assert i2.sort_order == 2


def test_reorder_items_rejects_mixed_categories(app):
    """Non si può riordinare mischiando oggetti di categorie diverse (si sposta solo dal Catalogo)."""
    with app.app_context():
        admin = User.query.first()
        cats = Category.query.filter_by(owner_id=admin.id).all()[:2]
        i1 = Item(owner_id=admin.id, name="Uno", category_id=cats[0].id)
        i2 = Item(owner_id=admin.id, name="Due", category_id=cats[1].id)
        db.session.add_all([i1, i2])
        db.session.commit()

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.post("/api/riordina-oggetti", json={"item_ids": [i1.id, i2.id]})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False


def test_shopping_panel_fragment_reflects_live_state(app):
    """La route del frammento lista spesa riflette subito lo stato (per l'aggiornamento senza reload)."""
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = trip.trip_items[0]

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.get(f"/viaggi/{trip.id}/spesa-frammento")
        assert resp.status_code == 200
        assert "Niente da comprare" in resp.data.decode("utf-8")

        # missing_qty è limitato al totale nelle valigie (0, qui): impostiamo
        # prima una quantità in una valigia per poter segnare "ne mancano 3"
        # (sync_trip_items ha già creato la riga per ogni valigia attiva).
        tl = trip.trip_luggages[0]
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == tl.id)
        qty_row.quantity = 3
        db.session.commit()

        client.post("/api/mancante", json={"trip_item_id": ti.id, "missing_qty": 3})
        resp = client.get(f"/viaggi/{trip.id}/spesa-frammento")
        assert "manca 3" in resp.data.decode("utf-8")
        assert f'data-mark-purchased="{ti.id}"' in resp.data.decode("utf-8")


def test_worn_item_counts_toward_target_with_correct_label(app):
    """
    Nuova funzione: "indossato" è una QUANTITÀ (non un semplice sì/no) e
    conta insieme alle quantità nelle valigie per raggiungere l'obiettivo.
    L'etichetta distingue se il "pronto" viene da valigia, da indossato, o
    da entrambi. "Da comprare" mantiene comunque la priorità più alta.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Giacca pesante", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)

        # Senza obiettivo impostato, indossato da solo non basta: resta grigio
        # (l'obiettivo è sempre ciò che decide se l'oggetto serve o no).
        ti.indossato_qty = 1
        db.session.commit()
        assert ti.status == "non_necessario"

        # Obiettivo 1, tutto indossato, niente in valigia -> "Da indossare".
        ti.target_qty = 1
        db.session.commit()
        assert ti.status == "conservato"
        assert ti.status_label == "Da indossare"
        assert ti.is_overflowing is False

        # Obiettivo 2: 1 indossato + 1 in valigia -> "In valigia / da indossare".
        ti.target_qty = 2
        tl = trip.trip_luggages[0]
        qty_row = next(q for q in ti.quantities if q.trip_luggage_id == tl.id)
        qty_row.quantity = 1
        db.session.commit()
        assert ti.status == "conservato"
        assert ti.status_label == "In valigia / da indossare"

        # Solo in valigia, niente indossato -> l'etichetta torna quella normale.
        ti.indossato_qty = 0
        db.session.commit()
        assert ti.status == "da_preparare"  # 1 in valigia < obiettivo 2
        assert ti.status_label == "Da preparare"

        # "Da comprare" mantiene comunque la priorità più alta.
        ti.missing_qty = 1
        db.session.commit()
        assert ti.status == "da_comprare"


def test_set_indossato_qty_via_api(app):
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = trip.trip_items[0]
        ti.target_qty = 2
        db.session.commit()

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.post("/api/indossato", json={"trip_item_id": ti.id, "quantity": 2})
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["indossato_qty"] == 2
        assert payload["status"] == "conservato"

        resp = client.post("/api/indossato", json={"trip_item_id": ti.id, "quantity": 0})
        assert resp.get_json()["indossato_qty"] == 0


def test_luggage_display_labels_disambiguates_same_tipologia(app):
    """
    Bug reale: con due valigie della stessa tipologia (es. due da cabina)
    lo stepper mostrava la stessa etichetta breve per entrambe, senza modo
    di distinguerle. Ora, solo quando serve, si aggiunge un riferimento
    alla valigia specifica.
    """
    with app.app_context():
        admin = User.query.first()
        cabina1 = Luggage(owner_id=admin.id, brand="Rimowa", name="Classic Cabin", tipologia=LuggageType.CABINA)
        cabina2 = Luggage(owner_id=admin.id, brand="Samsonite", name="Cosmolite Cabin", tipologia=LuggageType.CABINA)
        zaino = Luggage(owner_id=admin.id, brand="Osprey", name="Farpoint", tipologia=LuggageType.ZAINO)
        db.session.add_all([cabina1, cabina2, zaino])
        db.session.commit()

        # Viaggio costruito SENZA le valigie di default (niente
        # ensure_default_trip_luggages), per avere il pieno controllo su
        # quali valigie sono attive in questo test.
        trip = Trip(owner_id=admin.id, destination="Kyoto", start_date=date.today(), end_date=date.today() + timedelta(days=2))
        db.session.add(trip)
        db.session.commit()
        db.session.add_all([
            TripLuggage(trip_id=trip.id, luggage_id=cabina1.id, user_id=admin.id, sort_order=0),
            TripLuggage(trip_id=trip.id, luggage_id=cabina2.id, user_id=admin.id, sort_order=1),
            TripLuggage(trip_id=trip.id, luggage_id=zaino.id, user_id=admin.id, sort_order=2),
        ])
        db.session.commit()

        my_luggages = user_trip_luggages(trip, admin)
        labels = luggage_display_labels(my_luggages)

        tl_cabina1 = next(tl for tl in my_luggages if tl.luggage_id == cabina1.id)
        tl_cabina2 = next(tl for tl in my_luggages if tl.luggage_id == cabina2.id)
        tl_zaino = next(tl for tl in my_luggages if tl.luggage_id == zaino.id)

        # Le due "Cabina" sono distinguibili...
        assert labels[tl_cabina1.id] != labels[tl_cabina2.id]
        assert "Rimowa" in labels[tl_cabina1.id]
        assert "Samsonite" in labels[tl_cabina2.id]
        # ...ma lo Zaino, unico del suo tipo, resta semplice.
        assert labels[tl_zaino.id] == "Zaino"


def test_mismatch_info_included_in_quantity_payload(app):
    """
    Bug reale: l'avviso "valigia sbagliata" era calcolato solo lato
    server nel template, quindi compariva solo dopo un ricaricamento
    completo della pagina, mai dopo una modifica dal vivo dello stepper.
    Ora la risposta di /api/quantita include l'informazione, così il
    JS può mostrarlo/nasconderlo all'istante.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Cappello", category_id=cat.id, default_luggage_type=LuggageType.STIVA)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        cabina_tl = next(tl for tl in trip.trip_luggages if tl.luggage.tipologia == LuggageType.CABINA)

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.post("/api/quantita", json={
            "trip_item_id": ti.id, "trip_luggage_id": cabina_tl.id, "quantity": 1,
        })
        payload = resp.get_json()
        assert payload["mismatches"][str(cabina_tl.id)] is True
        assert "stiva" in payload["mismatch_message"].lower()


def test_shared_luggage_lets_other_collaborator_add_own_items_and_sums_weight(app):
    """
    Nuova funzione: il proprietario di una valigia la condivide con un
    altro collaboratore del viaggio, che può metterci dentro le PROPRIE
    cose (anche oggetti che il proprietario non ha nel suo catalogo). Il
    peso della valigia condivisa somma il contributo di entrambi.
    """
    with app.app_context():
        admin = User.query.first()
        anna = User(username="anna", full_name="Anna", must_change_password=False)
        anna.set_password("password123")
        db.session.add(anna)
        db.session.commit()
        provision_new_user_defaults(anna)

        trip = _make_trip(admin, days=3)
        db.session.add(TripShare(trip_id=trip.id, user_id=anna.id))
        db.session.commit()

        admin_cabina = next(tl for tl in trip.trip_luggages if tl.luggage.tipologia == LuggageType.CABINA)

        # Prima di condividere: Anna non può usare la valigia di admin.
        sync_trip_items(trip, anna)
        assert admin_cabina.id not in {tl.id for tl in user_trip_luggages(trip, anna)}

        # L'admin condivide la valigia con Anna.
        db.session.add(TripLuggageShare(trip_luggage_id=admin_cabina.id, shared_with_user_id=anna.id))
        db.session.commit()

        # Ora Anna la vede tra le proprie valigie utilizzabili...
        assert admin_cabina.id in {tl.id for tl in user_trip_luggages(trip, anna)}

        # ...e ci può mettere un SUO oggetto (che admin non ha nel catalogo).
        cat_anna = Category.query.filter_by(owner_id=anna.id).first()
        anna_item = Item(owner_id=anna.id, name="Solo di Anna", category_id=cat_anna.id, weight_grams=500)
        db.session.add(anna_item)
        db.session.commit()
        sync_trip_items(trip, anna)
        anna_ti = next(t for t in trip.trip_items if t.item_id == anna_item.id and t.user_id == anna.id)

        client = app.test_client()
        client.post("/login", data={"username": "anna", "password": "password123"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "password123", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )
        resp = client.post("/api/quantita", json={
            "trip_item_id": anna_ti.id, "trip_luggage_id": admin_cabina.id, "quantity": 2,
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Il peso nella valigia condivisa somma il contributo di Anna
        # (vista dal PROPRIETARIO admin, non solo da Anna stessa).
        stats = trip_stats(trip, admin)
        lug_stats = next(l for l in stats["luggages"] if l["trip_luggage_id"] == admin_cabina.id)
        assert lug_stats["is_shared"] is True
        assert lug_stats["content_weight_grams"] == 1000  # 500g * 2


def test_cover_upload_and_position(app, tmp_path):
    """Caricamento manuale della copertina + posizionamento trascinabile salvato."""
    import io

    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        trip_id = trip.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    fake_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 100)  # intestazione JPEG minima, basta per il test
    resp = client.post(
        f"/viaggi/{trip_id}/copertina/carica",
        data={"cover_file": (fake_jpeg, "cover.jpg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Immagine caricata" in resp.data.decode("utf-8")

    with app.app_context():
        refreshed = Trip.query.get(trip_id)
        assert refreshed.cover_image_is_upload is True
        assert refreshed.cover_image_url == f"/viaggi/{trip_id}/copertina/file"

    resp = client.get(f"/viaggi/{trip_id}/copertina/file")
    assert resp.status_code == 200

    resp = client.post(f"/viaggi/{trip_id}/copertina/posizione", json={"x": 20, "y": 80})
    assert resp.status_code == 200
    assert resp.get_json()["position"] == "20.0% 80.0%"

    with app.app_context():
        refreshed = Trip.query.get(trip_id)
        assert refreshed.cover_image_position == "20.0% 80.0%"


def test_cover_search_uses_custom_terms(app, monkeypatch):
    """I termini di ricerca personalizzati, se impostati, sostituiscono la destinazione nella ricerca."""
    captured = {}

    def fake_search_title(candidate, lang):
        captured["candidate"] = candidate
        return None  # non serve trovare nulla, solo verificare COSA viene cercato

    monkeypatch.setattr("app.utils._wiki_search_title", fake_search_title)

    from app.utils import fetch_trip_cover_image
    fetch_trip_cover_image("Parigi", search_terms="Torre Eiffel")
    assert captured["candidate"] == "Torre Eiffel"

    captured.clear()
    fetch_trip_cover_image("Parigi", search_terms=None)
    assert captured["candidate"] != "Torre Eiffel"


def test_item_edit_prev_next_navigation(app):
    """Precedente/successivo naviga tra oggetti della STESSA categoria, nascosti agli estremi; Salva resta sulla pagina di modifica."""
    with app.app_context():
        admin = User.query.first()
        cat = Category(owner_id=admin.id, name="Categoria di prova", sort_order=999)
        db.session.add(cat)
        db.session.commit()
        a = Item(owner_id=admin.id, name="Alfa", category_id=cat.id, sort_order=0)
        b = Item(owner_id=admin.id, name="Beta", category_id=cat.id, sort_order=1)
        c = Item(owner_id=admin.id, name="Gamma", category_id=cat.id, sort_order=2)
        db.session.add_all([a, b, c])
        db.session.commit()
        a_id, b_id, c_id, cat_id = a.id, b.id, c.id, cat.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    # Il primo non ha "precedente", ha "successivo".
    resp = client.get(f"/catalogo/oggetti/{a_id}/modifica")
    html = resp.data.decode("utf-8")
    assert f"/catalogo/oggetti/{b_id}/modifica" in html
    assert "Precedente" not in html

    # Quello di mezzo ha entrambi.
    resp = client.get(f"/catalogo/oggetti/{b_id}/modifica")
    html = resp.data.decode("utf-8")
    assert f"/catalogo/oggetti/{a_id}/modifica" in html
    assert f"/catalogo/oggetti/{c_id}/modifica" in html

    # L'ultimo ha "precedente" ma non "successivo".
    resp = client.get(f"/catalogo/oggetti/{c_id}/modifica")
    html = resp.data.decode("utf-8")
    assert f"/catalogo/oggetti/{b_id}/modifica" in html
    assert "Successivo" not in html

    # Salvare resta sulla pagina di modifica (non porta al dettaglio).
    resp = client.post(
        f"/catalogo/oggetti/{b_id}/modifica",
        data={"name": "Beta modificato", "category_id": str(cat_id), "quantity_rule": "manual",
              "fixed_qty": "1", "per_day_extra": "1", "default_luggage_type": "", "weight_grams": "", "notes": ""},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/catalogo/oggetti/{b_id}/modifica")


def test_item_detail_shows_back_to_trip_button_only_with_valid_param(app):
    """Il pulsante 'torna al viaggio' compare solo se si arriva da un viaggio realmente accessibile."""
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        trip_id = trip.id
        item = Item.query.filter_by(owner_id=admin.id).first()
        item_id = item.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get(f"/catalogo/oggetti/{item_id}")
    assert "Torna al viaggio" not in resp.data.decode("utf-8")

    resp = client.get(f"/catalogo/oggetti/{item_id}?da_viaggio={trip_id}")
    assert "Torna al viaggio" in resp.data.decode("utf-8")

    resp = client.get(f"/catalogo/oggetti/{item_id}?da_viaggio=999999")
    assert "Torna al viaggio" not in resp.data.decode("utf-8")


def test_shopping_badge_always_in_dom_for_live_update(app):
    """
    Bug reale: il badge del numero da comprare esisteva nell'HTML SOLO
    se il conteggio era già > 0 al caricamento della pagina — se all'
    apertura non c'era nulla da comprare, il JS non trovava alcun
    elemento da aggiornare quando si aggiungeva il primo oggetto, e il
    badge non appariva mai senza ricaricare. Ora l'elemento esiste
    sempre nel DOM (nascosto via display:none quando il conteggio è 0).
    """
    with app.app_context():
        admin = User.query.first()

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert 'data-nav-shopping-badge' in html
    assert 'display:none;' in html  # nessun oggetto da comprare ancora


def test_stats_live_endpoint_reflects_shared_luggage_from_other_user(app):
    """
    L'endpoint di polling (/stats-live) permette al browser del
    proprietario di una valigia condivisa di scoprire, senza ricaricare
    la pagina, che un altro collaboratore ci ha aggiunto qualcosa.
    """
    with app.app_context():
        admin = User.query.first()
        anna = User(username="anna2", full_name="Anna Due", must_change_password=False)
        anna.set_password("password123")
        db.session.add(anna)
        db.session.commit()
        provision_new_user_defaults(anna)

        trip = _make_trip(admin, days=3)
        db.session.add(TripShare(trip_id=trip.id, user_id=anna.id))
        db.session.commit()
        trip_id = trip.id

        cabina = next(tl for tl in trip.trip_luggages if tl.luggage.tipologia == LuggageType.CABINA)
        cabina_id = cabina.id
        db.session.add(TripLuggageShare(trip_luggage_id=cabina.id, shared_with_user_id=anna.id))
        db.session.commit()

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get(f"/viaggi/{trip_id}/stats-live")
    lug = next(l for l in resp.get_json()["stats"]["luggages"] if l["trip_luggage_id"] == cabina_id)
    assert lug["packed_qty"] == 0

    # Anna (un'altra sessione) aggiunge qualcosa alla valigia condivisa.
    with app.app_context():
        anna_client_id = User.query.filter_by(username="anna2").first().id
        sync_trip_items(Trip.query.get(trip_id), User.query.get(anna_client_id))
        anna_ti = TripItem.query.filter_by(trip_id=trip_id, user_id=anna_client_id).first()
        qty_row = next(q for q in anna_ti.quantities if q.trip_luggage_id == cabina_id)
        qty_row.quantity = 3
        db.session.commit()

    # L'admin, SENZA fare nulla lui stesso, la vede tramite il polling.
    resp = client.get(f"/viaggi/{trip_id}/stats-live")
    lug = next(l for l in resp.get_json()["stats"]["luggages"] if l["trip_luggage_id"] == cabina_id)
    assert lug["packed_qty"] == 3


def test_workspace_shopping_tab_badge_always_in_dom(app):
    """
    Bug reale (stesso già corretto per il pallino nel menu in alto, ma
    non applicato qui): il pallino sulla scheda "Lista della spesa"
    dentro il viaggio esisteva nell'HTML SOLO se il conteggio era già
    > 0 al caricamento — altrimenti il JS non aveva nulla da aggiornare
    quando si aggiungeva il primo oggetto, e restava invisibile senza
    ricaricare la pagina a mano.
    """
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        trip_id = trip.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get(f"/viaggi/{trip_id}")
    html = resp.data.decode("utf-8")
    assert 'data-main-tab-shopping-badge' in html
    assert 'display:none;' in html  # nessun oggetto da comprare ancora


def test_export_and_reset_custom_base_catalog(app, tmp_path, monkeypatch):
    """
    L'admin può promuovere gli oggetti/categorie/valigie SPUNTATI COME
    PUBBLICI (Item/Category/Luggage.is_public) a nuovo catalogo di base
    (con tutte le impostazioni, non solo nome/categoria, e ora anche
    modelli e valigie) — usato da quel momento per i nuovi utenti e per
    "Importa catalogo di base". Ciò che NON è spuntato resta privato: non
    deve MAI comparire nel file esportato, nemmeno se è nel catalogo
    attivo dell'admin. Isolato in una cartella temporanea per non
    scrivere nella vera cartella dati del progetto durante il test.
    """
    monkeypatch.setattr("app.config.DATA_DIR", tmp_path)

    with app.app_context():
        from app.importer import (
            export_catalog_as_base, has_custom_base_catalog,
            reset_base_catalog_to_default, import_base_catalog_for_user,
        )

        assert has_custom_base_catalog() is False

        admin = User.query.first()
        cat = Category(owner_id=admin.id, name="CategoriaPersonalizzata", sort_order=999, is_public=True)
        db.session.add(cat)
        db.session.commit()
        item = Item(
            owner_id=admin.id, name="OggettoSuMisura", category_id=cat.id,
            quantity_rule=QuantityRule.PER_DAY, per_day_extra=2, weight_grams=250.0,
            default_luggage_type=LuggageType.ZAINO, is_public=True,
        )
        db.session.add(item)
        db.session.commit()
        db.session.add(ItemVariant(item_id=item.id, description="Modello pubblico", weight_grams=100, owned_qty=2))
        db.session.commit()
        lug = Luggage(owner_id=admin.id, name="Valigia pubblica test", tipologia=LuggageType.CABINA, is_public=True)
        db.session.add(lug)
        db.session.commit()

        # Un oggetto NON spuntato come pubblico: non deve mai comparire nell'export.
        item_privato = Item(owner_id=admin.id, name="OggettoPrivatoDaNonEsportare", category_id=cat.id, is_public=False)
        db.session.add(item_privato)
        db.session.commit()

        count = export_catalog_as_base(admin)
        assert count == 1  # solo l'oggetto pubblico, non quello privato
        assert has_custom_base_catalog() is True
        assert (tmp_path / "catalogo_base.json").exists()

        import json
        exported = json.loads((tmp_path / "catalogo_base.json").read_text(encoding="utf-8"))
        exported_names = {i["name"] for i in exported["items"]}
        assert "OggettoSuMisura" in exported_names
        assert "OggettoPrivatoDaNonEsportare" not in exported_names
        assert exported["items"][0]["variants"][0]["description"] == "Modello pubblico"
        assert exported["luggage"][0]["name"] == "Valigia pubblica test"

        # Un nuovo utente importa il catalogo PERSONALIZZATO, con tutte le
        # impostazioni preservate (non solo nome/categoria) — inclusi
        # modelli e valigie, ma SOLO quanto era pubblico.
        nuovo = User(username="nuovoutente", full_name="Nuovo Utente", must_change_password=False)
        nuovo.set_password("password123")
        db.session.add(nuovo)
        db.session.commit()

        summary = import_base_catalog_for_user(nuovo)
        assert summary.items_created > 0

        imported_item = Item.query.filter_by(owner_id=nuovo.id, name="OggettoSuMisura").first()
        assert imported_item is not None
        assert imported_item.quantity_rule == QuantityRule.PER_DAY
        assert imported_item.per_day_extra == 2
        assert imported_item.weight_grams == 250.0
        assert imported_item.default_luggage_type == LuggageType.ZAINO
        assert len(imported_item.variants) == 1
        assert imported_item.variants[0].description == "Modello pubblico"
        assert Item.query.filter_by(owner_id=nuovo.id, name="OggettoPrivatoDaNonEsportare").first() is None
        assert Luggage.query.filter_by(owner_id=nuovo.id, name="Valigia pubblica test").first() is not None

        reset_base_catalog_to_default()
        assert has_custom_base_catalog() is False


def test_service_worker_served_from_root_with_version(app):
    """
    Il service worker per la consultazione offline dev'essere servito
    dalla RADICE del sito (non da /static/), altrimenti il suo controllo
    ("scope") non coprirebbe il resto dell'app — e la sua cache dev'essere
    legata alla versione dell'app, per invalidarsi da sola ad ogni
    aggiornamento.
    """
    client = app.test_client()
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.content_type
    body = resp.data.decode("utf-8")
    assert app.config["APP_VERSION"] in body
    assert "caches.open" in body
    # Non deve MAI intercettare le scritture: solo apiFetch + la coda
    # offline gestiscono quelle (vedi static/js/offline.js).
    assert 'req.method !== "GET"' in body
    # Bug reale corretto: una pagina mai visitata offline mostrava
    # silenziosamente la Home (sembrava un link "rotto") invece di una
    # spiegazione chiara.
    assert "/offline-non-disponibile" in body
    assert "caches.match(OFFLINE_URL)" in body


def test_offline_fallback_page_accessible_without_login(app):
    """La pagina di spiegazione offline dev'essere raggiungibile SEMPRE (viene messa in cache all'installazione del service worker, prima di qualunque login)."""
    client = app.test_client()
    resp = client.get("/offline-non-disponibile")
    assert resp.status_code == 200
    assert "non è ancora disponibile offline" in resp.data.decode("utf-8")


def test_item_variants_weight_and_status(app):
    """
    Nuova funzione: un oggetto con "modelli" (es. camicie di taglio
    diverso) traccia quante unità di CIASCUN modello si portano in un
    viaggio, con peso specifico per modello, invece del generico
    conteggio per valigia.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Camicie eleganti", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

        bianca = ItemVariant(item_id=item.id, description="Bianca elegante", weight_grams=200, owned_qty=2)
        blu = ItemVariant(item_id=item.id, description="Blu a righe", weight_grams=220, owned_qty=1)
        db.session.add_all([bianca, blu])
        db.session.commit()

        assert item.has_variants is True

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti.target_qty = 3
        db.session.commit()
        trip_luggage_id = trip.trip_luggages[0].id

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/account/password",
            data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
            follow_redirects=True,
        )

        resp = client.post("/api/variante", json={
            "trip_item_id": ti.id, "item_variant_id": bianca.id, "trip_luggage_id": trip_luggage_id, "quantity": 2,
        })
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["variants_total_qty"] == 2

        resp = client.post("/api/variante", json={
            "trip_item_id": ti.id, "item_variant_id": blu.id, "trip_luggage_id": trip_luggage_id, "quantity": 1,
        })
        payload = resp.get_json()
        assert payload["variants_total_qty"] == 3
        assert payload["status"] == "conservato"  # 2+1 = 3 = obiettivo
        # Il peso finisce nel conteggio per QUELLA valigia (bug reale
        # corretto: prima non c'era alcuna valigia collegata).
        luggage_stats = next(l for l in payload["stats"]["luggages"] if l["trip_luggage_id"] == trip_luggage_id)
        assert luggage_stats["content_weight_grams"] == 2 * 200 + 1 * 220

        db.session.refresh(ti)
        assert ti.qty_for_variant(bianca.id) == 2
        assert ti.qty_for_variant(blu.id) == 1
        assert ti.qty_for_variant_in_luggage(bianca.id, trip_luggage_id) == 2
        assert ti.qty_for_luggage(trip_luggage_id) == 3
        assert ti.total_ready_qty == 3


def test_add_edit_delete_item_variant(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Pantaloni", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.post(
        f"/catalogo/oggetti/{item_id}/modelli",
        data={"description": "Jeans blu scuro", "weight_grams": "450", "owned_qty": "3"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Jeans blu scuro" in resp.data.decode("utf-8")

    with app.app_context():
        item = Item.query.get(item_id)
        assert item.has_variants is True
        variant = item.variants[0]
        variant_id = variant.id
        assert variant.weight_grams == 450
        assert variant.owned_qty == 3

    resp = client.post(
        f"/catalogo/oggetti/{item_id}/modelli/{variant_id}/modifica",
        data={"description": "Jeans blu scurissimo", "weight_grams": "460", "owned_qty": "2"},
        follow_redirects=True,
    )
    assert "Jeans blu scurissimo" in resp.data.decode("utf-8")

    resp = client.post(f"/catalogo/oggetti/{item_id}/modelli/{variant_id}/elimina", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert ItemVariant.query.get(variant_id) is None
        assert Item.query.get(item_id).has_variants is False


def test_variant_quantity_cannot_exceed_owned(app):
    """
    Bug reale corretto: non si può segnare di portare più unità di un
    modello di quante se ne possiedono (impostato nella pagina
    dell'oggetto) — sia lato server sia nel limite dello stepper.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Pantaloni test", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Jeans slim", weight_grams=400, owned_qty=2)
        db.session.add(variant)
        db.session.commit()
        variant_id = variant.id

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti_id = ti.id
        luggage_ids = [tl.id for tl in trip.trip_luggages]

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    # Entro nel limite: consentito.
    resp = client.post("/api/variante", json={
        "trip_item_id": ti_id, "item_variant_id": variant_id, "trip_luggage_id": luggage_ids[0], "quantity": 2,
    })
    assert resp.get_json()["ok"] is True

    # Oltre il posseduto, nella STESSA valigia: rifiutato con un messaggio chiaro.
    resp = client.post("/api/variante", json={
        "trip_item_id": ti_id, "item_variant_id": variant_id, "trip_luggage_id": luggage_ids[0], "quantity": 3,
    })
    payload = resp.get_json()
    assert resp.status_code == 400
    assert payload["ok"] is False
    assert "Jeans slim" in payload["error"]

    # Oltre il posseduto SOMMANDO più valigie: rifiutato anche se la
    # singola valigia, presa da sola, sarebbe entro il limite.
    if len(luggage_ids) > 1:
        resp = client.post("/api/variante", json={
            "trip_item_id": ti_id, "item_variant_id": variant_id, "trip_luggage_id": luggage_ids[1], "quantity": 1,
        })
        payload = resp.get_json()
        assert resp.status_code == 400
        assert payload["ok"] is False


def test_catalog_prefs_page_and_icon_helpers(app):
    """Le preferenze icone/testo del catalogo si salvano e si applicano correttamente."""
    with app.app_context():
        admin = User.query.first()
        # Di default, le icone predefinite.
        assert admin.quantity_rule_icon("fixed") == "hash"
        assert admin.luggage_type_icon("cabina") == "briefcase"

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get("/impostazioni/catalogo")
    assert resp.status_code == 200

    resp = client.post("/impostazioni/catalogo", data={
        "column_style": "icons",
        "icon_fixed": "target", "icon_per_day": "repeat", "icon_manual": "hand",
        "icon_cabina": "luggage", "icon_stiva": "box", "icon_zaino": "backpack",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Preferenze del catalogo salvate" in resp.data.decode("utf-8")

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        assert admin.catalog_column_style == "icons"
        assert admin.quantity_rule_icon("fixed") == "target"
        assert admin.luggage_type_icon("cabina") == "luggage"

    # La pagina del catalogo usa ora lo stile scelto e l'icona personalizzata.
    resp = client.get("/catalogo/oggetti")
    html = resp.data.decode("utf-8")
    assert 'data-column-style="icons"' in html
    assert 'data-lucide="target"' in html


def test_offline_pages_endpoint_lists_trips(app):
    """L'endpoint usato dal pulsante 'Prepara per l'uso offline' elenca Home, pagine principali e tutti i viaggi accessibili."""
    with app.app_context():
        admin = User.query.first()
        trip = _make_trip(admin, days=3)
        trip_id = trip.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.get("/api/pagine-offline")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert "/" in payload["urls"]
    assert f"/viaggi/{trip_id}" in payload["urls"]


def test_trip_item_order_independent_from_catalog_order(app):
    """
    Bug reale corretto: riordinare gli oggetti DENTRO un viaggio cambiava
    prima l'ordine anche nel catalogo e in TUTTI gli altri viaggi (un
    unico campo condiviso). Ora un nuovo viaggio eredita l'ordine
    attuale del catalogo come punto di partenza, ma riordinare
    ULTERIORMENTE dentro quel viaggio resta isolato — non tocca né il
    catalogo né altri viaggi.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        a = Item(owner_id=admin.id, name="Oggetto A", category_id=cat.id, sort_order=0)
        b = Item(owner_id=admin.id, name="Oggetto B", category_id=cat.id, sort_order=1)
        db.session.add_all([a, b])
        db.session.commit()

        trip1 = _make_trip(admin, days=2)
        sync_trip_items(trip1, admin)
        ti1_a = TripItem.query.filter_by(trip_id=trip1.id, item_id=a.id).first()
        ti1_b = TripItem.query.filter_by(trip_id=trip1.id, item_id=b.id).first()
        # Il nuovo viaggio eredita l'ordine del catalogo.
        assert ti1_a.sort_order == 0
        assert ti1_b.sort_order == 1
        ti1_a_id, ti1_b_id = ti1_a.id, ti1_b.id
        trip1_id = trip1.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    # Inverto l'ordine SOLO dentro trip1.
    resp = client.post("/api/riordina-oggetti-viaggio", json={"trip_item_ids": [ti1_b_id, ti1_a_id]})
    assert resp.get_json()["ok"] is True

    with app.app_context():
        # Il catalogo NON è cambiato.
        a2 = Item.query.filter_by(name="Oggetto A").first()
        b2 = Item.query.filter_by(name="Oggetto B").first()
        assert a2.sort_order == 0
        assert b2.sort_order == 1

        # Un SECONDO viaggio, creato dopo, eredita ancora l'ordine
        # ORIGINALE del catalogo (non quello modificato in trip1).
        admin2 = User.query.filter_by(username="admin").first()
        trip2 = _make_trip(admin2, days=2)
        sync_trip_items(trip2, admin2)
        ti2_a = TripItem.query.filter_by(trip_id=trip2.id, item_id=a2.id).first()
        ti2_b = TripItem.query.filter_by(trip_id=trip2.id, item_id=b2.id).first()
        assert ti2_a.sort_order == 0
        assert ti2_b.sort_order == 1

        # trip1 mantiene il proprio ordine invertito.
        ti1_a_final = TripItem.query.get(ti1_a_id)
        ti1_b_final = TripItem.query.get(ti1_b_id)
        assert ti1_b_final.sort_order == 0
        assert ti1_a_final.sort_order == 1


def test_catalog_reorder_endpoint_changes_item_sort_order(app):
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        a = Item(owner_id=admin.id, name="Zaino da riordinare A", category_id=cat.id, sort_order=0)
        b = Item(owner_id=admin.id, name="Zaino da riordinare B", category_id=cat.id, sort_order=1)
        db.session.add_all([a, b])
        db.session.commit()
        a_id, b_id = a.id, b.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )
    resp = client.post("/api/riordina-oggetti", json={"item_ids": [b_id, a_id]})
    assert resp.get_json()["ok"] is True

    with app.app_context():
        assert Item.query.get(b_id).sort_order == 0
        assert Item.query.get(a_id).sort_order == 1


def test_nav_order_saved_and_reflected_in_page(app):
    """L'ordine (puramente visivo) delle voci del menu si salva e si riflette nell'ordine di comparsa nell'HTML."""
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        # Di default, l'ordine standard (Impostazioni non è più una voce
        # del menu principale: vive nel menu utente, non è riordinabile qui).
        assert admin.nav_order == ["home", "catalogo", "viaggi", "spesa"]

    resp = client.post("/impostazioni/menu", data={
        "top_order": ["viaggi", "home", "catalogo", "spesa"],
        "sub_order": ["valigie", "oggetti", "categorie"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Ordine del menu salvato" in resp.data.decode("utf-8")

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        assert admin.nav_order[0] == "viaggi"
        assert admin.catalog_submenu_order[0] == "valigie"

    home_html = client.get("/").data.decode("utf-8")
    idx_viaggi = home_html.find(">\n          <i data-lucide=\"plane\"")
    idx_home = home_html.find(">\n          <i data-lucide=\"layout-grid\"")
    assert 0 < idx_viaggi < idx_home

    # Un ordine manomesso (voce mancante) viene rifiutato.
    resp = client.post("/impostazioni/menu", data={
        "top_order": ["viaggi", "home"],
        "sub_order": ["valigie", "oggetti", "categorie"],
    }, follow_redirects=True)
    assert "Ordine non valido" in resp.data.decode("utf-8")


def test_variant_quantity_response_includes_fresh_data_for_all_luggages(app):
    """
    Bug reale corretto: il client mostrava "massimo qui" calcolato UNA
    SOLA volta al caricamento della pagina, senza aggiornarsi se la
    quantità cambiava in un'ALTRA valigia dello stesso oggetto nella
    stessa visita. La risposta dell'API deve sempre contenere i dati
    freschi per TUTTE le valigie (variant_quantities), non solo quella
    appena modificata, così il client può tenere sincronizzati anche
    gli altri stepper senza ricaricare la pagina.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Oggetto due valigie", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Modello raro", weight_grams=300, owned_qty=2)
        db.session.add(variant)
        db.session.commit()
        variant_id = variant.id

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti_id = ti.id
        luggage_ids = [tl.id for tl in trip.trip_luggages]
        assert len(luggage_ids) >= 2, "il test richiede almeno 2 valigie di base"

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    # Metto TUTTO il posseduto (2) nella PRIMA valigia.
    resp = client.post("/api/variante", json={
        "trip_item_id": ti_id, "item_variant_id": variant_id, "trip_luggage_id": luggage_ids[0], "quantity": 2,
    })
    payload = resp.get_json()
    assert payload["ok"] is True
    # La risposta include i dati per QUESTA valigia...
    assert payload["variant_quantities"][str(variant_id)][str(luggage_ids[0])] == 2

    # ...quindi il client può calcolare correttamente che nella SECONDA
    # valigia non resta più nulla di disponibile, SENZA dover
    # ricaricare la pagina o indovinare: un tentativo di mettercene
    # anche solo 1 dev'essere rifiutato dal server.
    resp = client.post("/api/variante", json={
        "trip_item_id": ti_id, "item_variant_id": variant_id, "trip_luggage_id": luggage_ids[1], "quantity": 1,
    })
    payload = resp.get_json()
    assert payload["ok"] is False
    assert "Modello raro" in payload["error"]


def test_variante_endpoint_not_eligible_for_offline_queue():
    """
    Bug reale corretto: /api/variante finiva nella coda offline, ma la
    finestra di scelta del modello ha bisogno di una risposta COMPLETA
    e immediata dal server (per il limite tra più valigie) — una
    risposta "in coda" (solo {ok:true, queued:true}, senza i dati
    necessari) lasciava la finestra in uno stato incoerente senza un
    errore chiaro. Va sempre fallito con un errore di rete esplicito,
    mai messo in coda silenziosamente.
    """
    content = open("app/static/js/offline.js", encoding="utf-8").read()
    idx = content.find("const ELIGIBLE_PATHS")
    line = content[idx:content.find("\n", idx)]
    assert "/api/variante" not in line


def test_deleting_luggage_cascades_variant_quantities(app):
    """
    Bug reale corretto: eliminare una valigia lasciava "appese" le
    quantità dei modelli portati in quella valigia (nessun cascade di
    eliminazione, a differenza delle quantità normali) — invisibili in
    qualunque stepper, ma CONTATE UGUALMENTE nel totale dell'oggetto,
    gonfiando lo stato mostrato (es. "in valigia" nonostante gli
    stepper visibili sommassero molto meno del necessario).
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Camicie test cascade", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Modello test", weight_grams=200, owned_qty=10)
        db.session.add(variant)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti.target_qty = 5
        db.session.commit()

        extra_luggage = Luggage(owner_id=admin.id, name="Zaino da eliminare", tipologia=LuggageType.ZAINO)
        db.session.add(extra_luggage)
        db.session.commit()
        extra_tl = TripLuggage(trip_id=trip.id, luggage_id=extra_luggage.id, user_id=admin.id, sort_order=99)
        db.session.add(extra_tl)
        db.session.commit()
        extra_tl_id = extra_tl.id

        # Metto TUTTO l'obiettivo (5) in questa valigia "temporanea".
        vq = TripItemVariantQty(trip_item_id=ti.id, item_variant_id=variant.id, trip_luggage_id=extra_tl_id, quantity=5)
        db.session.add(vq)
        db.session.commit()
        assert ti.status == "conservato"  # 5/5 raggiunto

        # Elimino la valigia: PRIMA di questa correzione, la riga sopra
        # sarebbe rimasta orfana, continuando a contare nel totale.
        db.session.delete(extra_tl)
        db.session.commit()

        db.session.refresh(ti)
        assert TripItemVariantQty.query.filter_by(trip_luggage_id=extra_tl_id).count() == 0
        assert ti.variants_total_qty == 0
        assert ti.status == "da_preparare"  # non più "conservato": l'obiettivo non è più coperto da nulla di visibile


def test_migration_v15_removes_orphaned_variant_quantities(app):
    """Righe già orfane (create prima di questa correzione) vengono ripulite da una migrazione, non solo prevenute in futuro."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Camicie test migrazione orfane", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Modello orfano", weight_grams=100, owned_qty=5)
        db.session.add(variant)
        db.session.commit()

        trip = _make_trip(admin, days=2)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)

        # Una riga che punta a un trip_luggage_id INESISTENTE (simula lo
        # stato lasciato da un'eliminazione avvenuta prima della
        # correzione, quando non esisteva ancora il cascade).
        from app.extensions import db as _db
        _db.session.execute(_db.text(
            "INSERT INTO trip_item_variant_qty (trip_item_id, item_variant_id, trip_luggage_id, quantity) "
            "VALUES (:ti, :v, 999999, 3)"
        ), {"ti": ti.id, "v": variant.id})
        _db.session.commit()
        assert TripItemVariantQty.query.filter_by(trip_luggage_id=999999).count() == 1

        # Il database di test è già alla versione più recente (creato da
        # zero con gli schemi correnti): per far RIESEGUIRE la
        # migrazione v15 (che altrimenti verrebbe saltata, pensando sia
        # già stata applicata), si riporta indietro il numero di
        # versione registrato — non serve altro, la v15 è scritta per
        # essere idempotente e sicura da rilanciare.
        _db.session.execute(_db.text("UPDATE schema_meta SET schema_version = 14"))
        _db.session.commit()

        from app.migrations import run_migrations
        from flask import current_app
        run_migrations(current_app)

        assert TripItemVariantQty.query.filter_by(trip_luggage_id=999999).count() == 0


def test_deleting_item_variant_cascades_trip_quantities(app):
    """
    Bug reale corretto (lo stesso problema del cascade mancante, ma
    sull'altro lato della riga): eliminare un modello dal catalogo
    lasciava "appese" le quantità già portate in viaggio per quel
    modello — invisibili in qualunque finestra di scelta modello (che
    elenca solo i modelli ancora esistenti), ma CONTATE UGUALMENTE nel
    totale. Sintomo esatto segnalato: uno stepper mostrava un numero
    (es. 5) mentre la finestra elencava ogni modello a 0, e l'obiettivo
    risultava "superato" anche quando la somma visibile era ben sotto
    il limite.
    """
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Pantaloni test cascade modello", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Modello da eliminare", weight_grams=300, owned_qty=5)
        db.session.add(variant)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti.target_qty = 4
        db.session.commit()

        tl = trip.trip_luggages[0]
        vq = TripItemVariantQty(trip_item_id=ti.id, item_variant_id=variant.id, trip_luggage_id=tl.id, quantity=2)
        db.session.add(vq)
        db.session.commit()
        assert ti.variants_total_qty == 2
        assert ti.is_overflowing is False

        # Elimino il modello (es. per sostituirlo con uno nuovo):
        # PRIMA di questa correzione, la riga sopra sarebbe rimasta
        # orfana, continuando a contare nel totale nonostante il
        # modello non esista più in nessuna finestra.
        db.session.delete(variant)
        db.session.commit()

        db.session.refresh(ti)
        assert TripItemVariantQty.query.filter_by(item_variant_id=variant.id).count() == 0
        assert ti.variants_total_qty == 0
        assert ti.is_overflowing is False


def test_migration_v16_removes_orphaned_variant_quantities_by_deleted_variant(app):
    """Righe orfane per un MODELLO eliminato (non solo per una valigia eliminata) vengono ripulite da una migrazione dedicata."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Camicie test migrazione v16", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

        trip = _make_trip(admin, days=2)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        tl = trip.trip_luggages[0]

        from app.extensions import db as _db
        _db.session.execute(_db.text(
            "INSERT INTO trip_item_variant_qty (trip_item_id, item_variant_id, trip_luggage_id, quantity) "
            "VALUES (:ti, 999999, :tl, 5)"
        ), {"ti": ti.id, "tl": tl.id})
        _db.session.commit()
        assert TripItemVariantQty.query.filter_by(item_variant_id=999999).count() == 1

        _db.session.execute(_db.text("UPDATE schema_meta SET schema_version = 15"))
        _db.session.commit()

        from app.migrations import run_migrations
        from flask import current_app
        run_migrations(current_app)

        assert TripItemVariantQty.query.filter_by(item_variant_id=999999).count() == 0


def test_variant_luggage_stepper_excluded_from_generic_quantity_handler():
    """
    Bug reale corretto: lo stepper per valigia di un oggetto CON modelli
    condivide la stessa classe base (".qty-stepper") e lo stesso
    attributo ("data-trip-luggage-id") dello stepper di un oggetto
    SENZA modelli — senza un'esclusione esplicita, il gestore generico
    (pensato per /api/quantita) si attaccava AGLI STESSI pulsanti +/-
    della finestra di scelta modello, aggiornando il numero mostrato
    tramite l'endpoint sbagliato mentre i modelli veri restavano
    invariati (segnalato: "il conteggio si aggiorna ma i modelli
    restano al numero originario").
    """
    content = open("app/static/js/dashboard.js", encoding="utf-8").read()
    assert '.qty-stepper[data-trip-luggage-id]:not(.qty-stepper--variant-luggage)' in content

    # I pulsanti della finestra di scelta modello non devono avere
    # "data-step": è l'attributo che initRobustStepper cerca per
    # agganciarsi — tenerlo lì, anche con l'esclusione sopra a posto,
    # sarebbe un'esca per il prossimo refactor.
    workspace_html = open("app/templates/trips/workspace.html", encoding="utf-8").read()
    idx = workspace_html.find("qty-stepper--variant-luggage")
    block_end = workspace_html.find("</div>", idx)
    block = workspace_html[idx:block_end]
    assert "data-step" not in block


def test_dashboard_js_updates_own_variant_dataset_after_save():
    """
    Bug reale corretto: dopo un salvataggio riuscito, la finestra di
    scelta modello aggiornava il "dataset.variants" di TUTTE le ALTRE
    valigie dello stesso oggetto, ma escludeva esplicitamente se stessa
    (`if (sibling === stepperRef) return;`) — riaprire la finestra per
    la STESSA valigia rileggeva quindi sempre i dati del primo
    caricamento della pagina, mai aggiornati: un salvataggio sembrava
    "non prendere mai" (segnalato: azzerare tutto e riaprire la
    finestra mostrava sempre i numeri vecchi). Il ciclo che propaga i
    dati freschi non deve più escludere l'elemento da cui è partito il
    salvataggio.
    """
    content = open("app/static/js/dashboard.js", encoding="utf-8").read()
    assert "if (sibling === stepperRef) return;" not in content


def test_reset_single_trip_item_clears_quantities_keeps_target(app):
    """Il pulsante "Azzera questo oggetto" rimuove quantità/modelli/indossato, ma NON tocca obiettivo e da comprare."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Oggetto da azzerare", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        variant = ItemVariant(item_id=item.id, description="Modello da azzerare", weight_grams=100, owned_qty=5)
        db.session.add(variant)
        db.session.commit()

        trip = _make_trip(admin, days=3)
        sync_trip_items(trip, admin)
        ti = next(t for t in trip.trip_items if t.item_id == item.id)
        ti.target_qty = 4
        ti.missing_qty = 2
        ti.indossato_qty = 1
        db.session.commit()
        tl = trip.trip_luggages[0]
        existing_qty = TripItemQty.query.filter_by(trip_item_id=ti.id, trip_luggage_id=tl.id).first()
        if existing_qty:
            existing_qty.quantity = 3
        else:
            db.session.add(TripItemQty(trip_item_id=ti.id, trip_luggage_id=tl.id, quantity=3))
        db.session.add(TripItemVariantQty(trip_item_id=ti.id, item_variant_id=variant.id, trip_luggage_id=tl.id, quantity=2))
        db.session.commit()
        ti_id, trip_id = ti.id, trip.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.post(f"/viaggi/{trip_id}/oggetti/{ti_id}/reset", follow_redirects=True)
    assert resp.status_code == 200
    assert "azzerato per questo viaggio" in resp.data.decode("utf-8")

    with app.app_context():
        ti = TripItem.query.get(ti_id)
        assert ti.total_qty == 0
        assert ti.variants_total_qty == 0
        assert ti.indossato_qty == 0
        # Invariati: non sono "dati residui", sono scelte dell'utente.
        assert ti.target_qty == 4
        assert ti.missing_qty == 2


def test_reset_all_trip_items(app):
    """Il pulsante "Azzera tutti gli oggetti" azzera OGNI oggetto del viaggio (solo i propri)."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item_a = Item(owner_id=admin.id, name="Oggetto A reset-tutti", category_id=cat.id)
        item_b = Item(owner_id=admin.id, name="Oggetto B reset-tutti", category_id=cat.id)
        db.session.add_all([item_a, item_b])
        db.session.commit()

        trip = _make_trip(admin, days=2)
        sync_trip_items(trip, admin)
        ti_a = next(t for t in trip.trip_items if t.item_id == item_a.id)
        ti_b = next(t for t in trip.trip_items if t.item_id == item_b.id)
        tl = trip.trip_luggages[0]
        qa = TripItemQty.query.filter_by(trip_item_id=ti_a.id, trip_luggage_id=tl.id).first()
        qa.quantity = 2
        qb = TripItemQty.query.filter_by(trip_item_id=ti_b.id, trip_luggage_id=tl.id).first()
        qb.quantity = 1
        db.session.commit()
        ti_a_id, ti_b_id, trip_id = ti_a.id, ti_b.id, trip.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.post(f"/viaggi/{trip_id}/reset-tutti-oggetti", follow_redirects=True)
    assert resp.status_code == 200
    assert "oggetti azzerati" in resp.data.decode("utf-8")

    with app.app_context():
        assert TripItem.query.get(ti_a_id).total_qty == 0
        assert TripItem.query.get(ti_b_id).total_qty == 0


def test_toggle_public_api_endpoint(app):
    """L'endpoint /api/pubblico spunta/toglie is_public su oggetto, categoria e valigia."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Oggetto toggle pubblico", category_id=cat.id)
        db.session.add(item)
        db.session.commit()
        lug = Luggage(owner_id=admin.id, name="Valigia toggle pubblico", tipologia=LuggageType.CABINA)
        db.session.add(lug)
        db.session.commit()
        item_id, cat_id, lug_id = item.id, cat.id, lug.id

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    for tipo, obj_id in [("oggetto", item_id), ("categoria", cat_id), ("valigia", lug_id)]:
        resp = client.post("/api/pubblico", json={"tipo": tipo, "id": obj_id, "is_public": True})
        payload = resp.get_json()
        assert resp.status_code == 200, f"{tipo} fallito: {payload}"
        assert payload["ok"] is True
        assert payload["is_public"] is True

    with app.app_context():
        assert Item.query.get(item_id).is_public is True
        assert Category.query.get(cat_id).is_public is True
        assert Luggage.query.get(lug_id).is_public is True

    # Tipo non riconosciuto: rifiutato con un errore chiaro, non un 500.
    resp = client.post("/api/pubblico", json={"tipo": "boh", "id": item_id, "is_public": True})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_column_resize_uses_th_geometry_not_col(app):
    """
    Bug reale corretto: il trascinamento leggeva la larghezza da <col>
    (dentro <colgroup>), che non è mai renderizzato come un riquadro
    normale — getBoundingClientRect() su un <col> torna quasi sempre
    {width:0} in ogni browser, quindi OGNI trascinamento calcolava
    percentuali vicine a zero e il server le rifiutava SEMPRE (non un
    caso limite). Corretto leggendo/scrivendo la geometria sulle <th>
    (che hanno sempre una geometria reale) invece che su <col>.
    """
    content = open("app/static/js/dashboard.js", encoding="utf-8").read()
    assert "querySelector(\"colgroup\")" not in content
    assert "getBoundingClientRect" in content
    # Le maniglie ora leggono dalla riga di intestazione (<th>), non da un colgroup.
    idx = content.find("function initColumnResize")
    section = content[idx:idx + 3000]
    assert "headerRow" in section
    assert "ths[colIndex]" in section

    html = open("app/templates/catalog/items.html", encoding="utf-8").read()
    assert "<colgroup>" not in html


def test_column_widths_persist_across_reload(app):
    """Larghezze salvate tramite /api/colonne-larghezza restano visibili in un caricamento SUCCESSIVO della pagina (bug reale corretto: "cambiare pagina e torna com'era prima")."""
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    resp = client.post("/api/colonne-larghezza", json={
        "table": "catalog-items", "widths": [28, 21, 17, 14, 20],
    })
    assert resp.get_json()["ok"] is True

    resp2 = client.get("/catalogo/oggetti")
    body = resp2.data.decode("utf-8")
    assert "width:28.0%" in body or "width:28%" in body
    assert "width:20.0%" in body or "width:20%" in body


def test_public_catalog_moved_to_dedicated_settings_page(app):
    """La spunta pubblica non compare più nelle pagine principali del catalogo: solo nella pagina dedicata, riservata agli admin."""
    with app.app_context():
        admin = User.query.first()
        cat = Category.query.filter_by(owner_id=admin.id).first()
        item = Item(owner_id=admin.id, name="Oggetto pagina dedicata", category_id=cat.id)
        db.session.add(item)
        db.session.commit()

    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuova123", "confirm_password": "nuova123"},
        follow_redirects=True,
    )

    for url in ["/catalogo/oggetti", "/catalogo/categorie", "/valigie/"]:
        resp = client.get(url)
        assert b"data-public-toggle" not in resp.data, f"{url} non deve mostrare la spunta pubblica"

    resp = client.get("/impostazioni/catalogo-pubblico")
    assert resp.status_code == 200
    assert b"data-public-toggle" in resp.data
    assert "Salva il catalogo da esportare".encode() in resp.data
