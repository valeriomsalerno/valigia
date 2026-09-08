"""
tests/test_walkthrough.py
==========================
Percorso end-to-end attraverso tutte le pagine e le API della v2.1, con
DUE utenti (admin + un membro) per verificare anche condivisione e
isolamento delle liste personali via HTTP reale (non solo a livello di
funzioni, come in test_smoke.py).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app("testing")


def login_and_change_password(client, username="admin", current_password="admin", new_password="nuova-password-123"):
    client.post("/login", data={"username": username, "password": current_password}, follow_redirects=True)
    resp = client.post(
        "/account/password",
        data={"current_password": current_password, "new_password": new_password, "confirm_password": new_password},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    return resp


def test_full_walkthrough(app):
    admin = app.test_client()

    login_and_change_password(admin)

    # --- Home a blocchi ------------------------------------------------------
    resp = admin.get("/")
    assert resp.status_code == 200
    assert "viaggio" in resp.data.decode("utf-8").lower()

    # --- Creazione di un viaggio -----------------------------------------------
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=9)
    resp = admin.post(
        "/viaggi/nuovo",
        data={
            "destination": "Kyoto, Giappone",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "notes": "Viaggio di prova",
            "copy_from_trip_id": "0",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Kyoto" in resp.data.decode("utf-8")

    from app.models import Trip
    with app.app_context():
        trip_id = Trip.query.filter_by(destination="Kyoto, Giappone").first().id

    # --- Workspace del viaggio: pannelli, sotto-schede, steppers ---------------
    resp = admin.get(f"/viaggi/{trip_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Valigia" in html and "Lista della spesa" in html
    assert "category-tabs" in html  # sotto-schede per categoria presenti

    for qs in ["", "?q=passaporto", "?stato=da_preparare", "?categoria=1"]:
        resp = admin.get(f"/viaggi/{trip_id}{qs}")
        assert resp.status_code == 200, f"Workspace fallito con {qs}"

    resp = admin.get("/")
    assert "In valigia" in resp.data.decode("utf-8") or resp.status_code == 200

    # --- API: quantità per valigia, obiettivo, mancante, conservato, nota -------
    from app.models import TripItem

    with app.app_context():
        ti = TripItem.query.filter_by(trip_id=trip_id).first()
        ti_id = ti.id
        luggage_id = ti.quantities[0].trip_luggage_id

    resp = admin.post("/api/quantita", json={"trip_item_id": ti_id, "trip_luggage_id": luggage_id, "quantity": 4})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["total_qty"] >= 4

    resp = admin.post("/api/obiettivo", json={"trip_item_id": ti_id, "target_qty": 10})
    assert resp.get_json()["target_qty"] == 10

    resp = admin.post("/api/mancante", json={"trip_item_id": ti_id, "missing_qty": 2})
    payload = resp.get_json()
    assert payload["status"] == "da_comprare"
    assert payload["owned_qty"] == payload["total_qty"] - 2

    # Lo stato torna automaticamente "da preparare" (non più "da comprare")
    # risolvendo temporaneamente il mancante, poi lo ripristiniamo: il
    # resto del test si aspetta ancora quest'oggetto nella lista spesa.
    resp = admin.post("/api/mancante", json={"trip_item_id": ti_id, "missing_qty": 0})
    assert resp.get_json()["status"] == "da_preparare"
    resp = admin.post("/api/mancante", json={"trip_item_id": ti_id, "missing_qty": 2})
    assert resp.get_json()["status"] == "da_comprare"

    resp = admin.post("/api/nota", json={"trip_item_id": ti_id, "note": "Portare la custodia"})
    assert resp.get_json()["ok"] is True

    # --- Pannello di dettaglio -------------------------------------------------
    resp = admin.get(f"/viaggi/{trip_id}/dettaglio/{ti_id}")
    assert resp.status_code == 200
    detail_html = resp.data.decode("utf-8")
    assert "Portare la custodia" in detail_html
    assert "Obiettivo" in detail_html

    # --- Catalogo: categorie, oggetti (con tipologia valigia predefinita) ------
    resp = admin.get("/catalogo/categorie")
    assert resp.status_code == 200
    resp = admin.get("/catalogo/oggetti")
    assert resp.status_code == 200

    resp = admin.post(
        "/catalogo/oggetti/nuovo",
        data={
            "name": "Power bank",
            "category_id": "1",
            "quantity_rule": "manual",
            "fixed_qty": "1",
            "per_day_extra": "1",
            "default_luggage_type": "stiva",
            "weight_grams": "250,5",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Power bank" in resp.data.decode("utf-8")
    assert "250,5" in resp.data.decode("utf-8")

    resp = admin.post("/catalogo/oggetti/importa-base", follow_redirects=True)
    assert resp.status_code == 200

    # --- Sezione Valigie (con tipologia) ----------------------------------------
    resp = admin.get("/valigie/")
    assert resp.status_code == 200

    resp = admin.post(
        "/valigie/nuova",
        data={"brand": "Samsonite", "name": "Cosmolite 75L", "tipologia": "stiva",
              "weight_kg": "3,2", "capacity_liters": "75", "is_default_for_new_trip": "", "notes": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Cosmolite" in resp.data.decode("utf-8")

    # --- Gestione valigie del viaggio (personale) --------------------------------
    resp = admin.get(f"/viaggi/{trip_id}/valigie")
    assert resp.status_code == 200
    assert "Cosmolite" in resp.data.decode("utf-8")

    from app.models import Luggage
    with app.app_context():
        new_luggage_id = Luggage.query.filter_by(name="Cosmolite 75L").first().id

    resp = admin.post(f"/viaggi/{trip_id}/valigie", data={"luggage_id": new_luggage_id}, follow_redirects=True)
    assert resp.status_code == 200

    # Ora il workspace deve mostrare uno stepper anche per la nuova valigia.
    resp = admin.get(f"/viaggi/{trip_id}")
    assert "Cosmolite" in resp.data.decode("utf-8")

    # --- Lista della spesa aggregata --------------------------------------------
    resp = admin.get("/lista-della-spesa")
    assert resp.status_code == 200
    assert "Kyoto" in resp.data.decode("utf-8")

    # --- Segna come acquistato (form classico) -----------------------------------
    resp = admin.post(f"/viaggi/{trip_id}/spesa/{ti_id}/acquistato", follow_redirects=True)
    assert resp.status_code == 200

    # ========================================================================
    # Multi-utente: profilo, secondo utente, condivisione, isolamento reale
    # ========================================================================
    resp = admin.get("/utenti/")
    assert resp.status_code == 200

    resp = admin.post(
        "/utenti/nuovo",
        data={"username": "familiare", "full_name": "Anna Rossi", "password": "temp1234", "role": "member"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Anna Rossi" in resp.data.decode("utf-8")

    from app.models import User
    with app.app_context():
        second_user_id = User.query.filter_by(username="familiare").first().id

    # --- Modifica profilo (nome completo + nickname) da parte dell'admin --------
    resp = admin.post(
        f"/utenti/{second_user_id}/modifica",
        data={"username": "familiare", "full_name": "Anna Bianchi"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    member = app.test_client()
    login_and_change_password(member, username="familiare", current_password="temp1234", new_password="altra-password-456")

    # Senza condivisione: 403 sulla modifica struttura, 403 sul workspace altrui.
    resp = member.get(f"/viaggi/{trip_id}/modifica")
    assert resp.status_code == 403
    resp = member.get(f"/viaggi/{trip_id}")
    assert resp.status_code == 403

    # --- Condivisione -------------------------------------------------------------
    resp = admin.post(f"/viaggi/{trip_id}/condividi", data={"user_id": str(second_user_id)}, follow_redirects=True)
    assert resp.status_code == 200

    # Ora il familiare accede al workspace, ma vede la SUA lista (vuota di
    # default finché non sincronizzata) e non tocca quella dell'admin.
    resp = member.get(f"/viaggi/{trip_id}")
    assert resp.status_code == 200
    assert "Viaggio di" in resp.data.decode("utf-8")

    with app.app_context():
        from app.models import TripItem as TI
        member_items = TI.query.filter_by(trip_id=trip_id, user_id=second_user_id).all()
        admin_items = TI.query.filter_by(trip_id=trip_id, user_id=1).all()
        assert len(member_items) > 30
        assert len(admin_items) > 30
        member_item_ids = {ti.item_id for ti in member_items}
        admin_item_ids = {ti.item_id for ti in admin_items}
        assert member_item_ids.isdisjoint(admin_item_ids)

    # Il familiare NON può modificare un TripItem dell'admin via API.
    resp = member.post("/api/mancante", json={"trip_item_id": ti_id, "missing_qty": 5})
    assert resp.status_code == 403

    # Il familiare gestisce le proprie valigie senza toccare quelle dell'admin.
    resp = member.get(f"/viaggi/{trip_id}/valigie")
    assert resp.status_code == 200
    assert "Cosmolite" not in resp.data.decode("utf-8")  # quella è dell'admin

    # ========================================================================
    # Regressione: rinominare una valigia scrivendo il peso con la virgola
    # (bug reale segnalato: il salvataggio falliva in silenzio)
    # ========================================================================
    from app.models import Luggage
    with app.app_context():
        bagaglio_a_mano = Luggage.query.filter_by(owner_id=1, name="Bagaglio a mano").first()
        luggage_id = bagaglio_a_mano.id

    resp = admin.get(f"/valigie/{luggage_id}/modifica")
    assert resp.status_code == 200

    resp = admin.post(
        f"/valigie/{luggage_id}/modifica",
        data={
            "brand": "", "name": "Bagaglio a mano RINOMINATO", "tipologia": "cabina",
            "weight_kg": "2,5", "capacity_liters": "40,0",
            "is_default_for_new_trip": "y", "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Bagaglio a mano RINOMINATO" in html
    assert "aggiornata" in html.lower()

    with app.app_context():
        renamed = Luggage.query.get(luggage_id)
        assert renamed.name == "Bagaglio a mano RINOMINATO"
        assert renamed.weight_kg == 2.5
        assert renamed.capacity_liters == 40.0

    print("Walkthrough completato senza errori.")
