"""
api/routes.py
==============
Endpoint JSON usati dal JavaScript della dashboard per le modifiche al
volo. La lista da mettere in valigia è personale: quasi tutti questi
endpoint verificano che il TripItem coinvolto appartenga proprio
all'utente autenticato (`trip_item.user_id == current_user.id`), non
solo che il viaggio sia accessibile — altrimenti un collaboratore
potrebbe modificare la lista di un altro.
"""

from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.models import TripItem, TripItemQty, TripLuggage, User

api_bp = Blueprint("api", __name__)


def _forbidden():
    return jsonify({"ok": False, "error": "Non hai accesso a questo oggetto."}), 403


def _get_own_trip_item(trip_item_id):
    """Recupera un TripItem verificando che appartenga all'utente corrente. None se non trovato/non tuo."""
    ti = db.session.get(TripItem, trip_item_id)
    if ti is None:
        return None
    if ti.user_id != current_user.id:
        return None
    if not ti.trip.is_accessible_by(current_user):
        return None
    return ti


def _trip_item_payload(trip_item: TripItem) -> dict:
    from app.utils import trip_stats

    mismatch_message = None
    if trip_item.item.default_luggage_type:
        mismatch_message = (
            f"{trip_item.item.name} andrebbe messo nella valigia da "
            f"{trip_item.item.default_luggage_type_label.lower()}"
        )

    return {
        "trip_item_id": trip_item.id,
        "total_qty": trip_item.total_qty,
        "total_ready_qty": trip_item.total_ready_qty,
        "owned_qty": trip_item.owned_qty,
        "target_qty": trip_item.target_qty,
        "missing_qty": trip_item.missing_qty,
        "indossato_qty": trip_item.indossato_qty,
        "status": trip_item.status,
        "status_label": trip_item.status_label,
        "is_overflowing": trip_item.is_overflowing,
        "quantities": {q.trip_luggage_id: q.quantity for q in trip_item.quantities},
        # Per ciascuna valigia con quantità impostata, indica se è "sbagliata"
        # rispetto alla tipologia predefinita dell'oggetto (solo un avviso,
        # mai un blocco). Il messaggio è lo stesso per tutte, cambia solo
        # QUALE valigia risulta segnalata.
        "mismatches": {q.trip_luggage_id: trip_item.has_luggage_mismatch(q.trip_luggage_id) for q in trip_item.quantities},
        "mismatch_message": mismatch_message,
        "variants_total_qty": trip_item.variants_total_qty,
        # Per ciascun modello, quante unità in CIASCUNA valigia — usato
        # dalla finestra di scelta del modello per precompilare i valori
        # correnti quando la si riapre.
        "variant_quantities": _variant_quantities_by_variant_and_luggage(trip_item),
        # Totale (di TUTTI i modelli insieme) per ciascuna valigia —
        # usato per aggiornare lo stepper della valigia dopo un
        # salvataggio, esattamente come "quantities" sopra per un
        # oggetto senza modelli.
        "variant_luggage_totals": _variant_totals_by_luggage(trip_item),
        "stats": trip_stats(trip_item.trip, current_user),
    }


def _variant_quantities_by_variant_and_luggage(trip_item: TripItem) -> dict:
    result: dict = {}
    for vq in trip_item.variant_quantities:
        result.setdefault(vq.item_variant_id, {})[vq.trip_luggage_id] = vq.quantity
    return result


def _variant_totals_by_luggage(trip_item: TripItem) -> dict:
    result: dict = {}
    for vq in trip_item.variant_quantities:
        result[vq.trip_luggage_id] = result.get(vq.trip_luggage_id, 0) + vq.quantity
    return result


@api_bp.route("/quantita", methods=["POST"])
@login_required
def update_quantity():
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    trip_luggage = db.session.get(TripLuggage, data.get("trip_luggage_id"))
    if trip_luggage is None or trip_luggage.trip_id != trip_item.trip_id or not trip_luggage.is_usable_by(current_user.id):
        return jsonify({"ok": False, "error": "Valigia non valida."}), 404

    try:
        quantity = max(0, min(int(data.get("quantity")), 999))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Quantità non valida."}), 400

    qty_row = next((q for q in trip_item.quantities if q.trip_luggage_id == trip_luggage.id), None)
    if qty_row is None:
        qty_row = TripItemQty(trip_item_id=trip_item.id, trip_luggage_id=trip_luggage.id, quantity=quantity)
        db.session.add(qty_row)
    else:
        qty_row.quantity = quantity

    if trip_item.missing_qty > trip_item.total_qty:
        trip_item.missing_qty = trip_item.total_qty

    db.session.commit()
    payload = _trip_item_payload(trip_item)
    payload["ok"] = True
    return jsonify(payload)


@api_bp.route("/mancante", methods=["POST"])
@login_required
def update_missing_qty():
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    try:
        missing_qty = int(data.get("missing_qty"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Quantità non valida."}), 400

    # Nessun tetto legato alla quantità già nelle valigie: si può segnare
    # "da comprare" un numero qualunque di unità, a prescindere da quante
    # ne hai già smistate (bug reale corretto: prima restava bloccato a 1
    # se non avevi ancora messo nulla in una valigia — vedi CHANGELOG).
    trip_item.missing_qty = max(0, min(missing_qty, 999))
    db.session.commit()
    payload = _trip_item_payload(trip_item)
    payload["ok"] = True
    return jsonify(payload)


@api_bp.route("/indossato", methods=["POST"])
@login_required
def update_indossato_qty():
    """Imposta quante unità di un oggetto si indossano direttamente (non vanno in valigia)."""
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    try:
        qty = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Quantità non valida."}), 400

    trip_item.indossato_qty = max(0, min(qty, 999))
    db.session.commit()
    payload = _trip_item_payload(trip_item)
    payload["ok"] = True
    return jsonify(payload)


@api_bp.route("/variante", methods=["POST"])
@login_required
def update_variant_qty():
    """
    Imposta quante unità di un MODELLO specifico (ItemVariant) si
    portano in QUESTA valigia, per questo viaggio. Il limite rispetto
    al posseduto (Item.owned_qty) è calcolato sulla SOMMA in TUTTE le
    valigie insieme — non ha senso possedere 2 camicie bianche e
    poterne mettere 2 in cabina E 2 in stiva contemporaneamente.
    """
    from app.models import ItemVariant, TripItemVariantQty, TripLuggage

    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    variant = db.session.get(ItemVariant, data.get("item_variant_id"))
    if variant is None or variant.item_id != trip_item.item_id:
        return jsonify({"ok": False, "error": "Modello non valido."}), 404

    trip_luggage = db.session.get(TripLuggage, data.get("trip_luggage_id"))
    if trip_luggage is None or trip_luggage.trip_id != trip_item.trip_id or not trip_luggage.is_usable_by(current_user.id):
        return jsonify({"ok": False, "error": "Valigia non valida."}), 404

    try:
        qty = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Quantità non valida."}), 400
    qty = max(0, qty)

    # Somma nelle ALTRE valigie (per il limite rispetto al posseduto,
    # che vale sul totale, non per singola valigia).
    qty_in_other_luggages = sum(
        vq.quantity for vq in trip_item.variant_quantities
        if vq.item_variant_id == variant.id and vq.trip_luggage_id != trip_luggage.id
    )
    upper_bound = max(variant.owned_qty, 0)
    if qty_in_other_luggages + qty > upper_bound:
        remaining = max(upper_bound - qty_in_other_luggages, 0)
        return jsonify({
            "ok": False,
            "error": f'Ne possiedi solo {upper_bound} di "{variant.description}" (al massimo {remaining} qui, il resto è già in un\'altra valigia).',
        }), 400

    vq = next(
        (v for v in trip_item.variant_quantities
         if v.item_variant_id == variant.id and v.trip_luggage_id == trip_luggage.id),
        None,
    )
    if vq is None:
        vq = TripItemVariantQty(
            trip_item_id=trip_item.id, item_variant_id=variant.id,
            trip_luggage_id=trip_luggage.id, quantity=qty,
        )
        db.session.add(vq)
    else:
        vq.quantity = qty
    db.session.commit()

    payload = _trip_item_payload(trip_item)
    payload["ok"] = True
    return jsonify(payload)


@api_bp.route("/obiettivo", methods=["POST"])
@login_required
def update_target_qty():
    """Aggiorna la quantità 'obiettivo' per il viaggio (riferimento libero, non vincolante)."""
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    raw = data.get("target_qty")
    if raw in (None, ""):
        trip_item.target_qty = None
    else:
        try:
            trip_item.target_qty = max(0, min(int(raw), 999))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Quantità non valida."}), 400

    db.session.commit()
    payload = _trip_item_payload(trip_item)
    payload["ok"] = True
    return jsonify(payload)


@api_bp.route("/assegna-acquisto", methods=["POST"])
@login_required
def assign_purchase():
    """Assegna (o rimuove l'assegnazione de) l'acquisto delle unità mancanti a un altro collaboratore."""
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    buyer_id = data.get("assigned_buyer_id")
    if buyer_id in (None, "", 0):
        trip_item.assigned_buyer_id = None
    else:
        buyer = db.session.get(User, int(buyer_id))
        if buyer is None or not trip_item.trip.is_accessible_by(buyer):
            return jsonify({"ok": False, "error": "Utente non valido per questo viaggio."}), 400
        trip_item.assigned_buyer_id = buyer.id

    db.session.commit()
    return jsonify({"ok": True, "assigned_buyer_id": trip_item.assigned_buyer_id})


@api_bp.route("/nota", methods=["POST"])
@login_required
def update_note():
    data = request.get_json(silent=True) or {}
    trip_item = _get_own_trip_item(data.get("trip_item_id"))
    if trip_item is None:
        return _forbidden()

    trip_item.note = (data.get("note") or "").strip()[:2000]
    db.session.commit()
    return jsonify({"ok": True, "note": trip_item.note})


@api_bp.route("/riordina-oggetti", methods=["POST"])
@login_required
def reorder_items():
    """
    Riordina manualmente (trascinamento) gli oggetti di UNA categoria del
    proprio catalogo. Spostare un oggetto in un'ALTRA categoria resta
    possibile solo dal Catalogo, non da qui.
    """
    from app.models import Item

    data = request.get_json(silent=True) or {}
    item_ids = data.get("item_ids")
    if not isinstance(item_ids, list) or not item_ids:
        return jsonify({"ok": False, "error": "Elenco non valido."}), 400

    try:
        item_ids = [int(i) for i in item_ids]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Elenco non valido."}), 400

    items = Item.query.filter(Item.id.in_(item_ids), Item.owner_id == current_user.id).all()
    items_by_id = {i.id: i for i in items}
    if len(items_by_id) != len(set(item_ids)):
        return jsonify({"ok": False, "error": "Alcuni oggetti non sono più validi: ricarica la pagina."}), 400

    # Si riordina solo ALL'INTERNO di una categoria: tutti gli oggetti
    # dell'elenco devono già appartenere alla stessa.
    if len({i.category_id for i in items_by_id.values()}) != 1:
        return jsonify({"ok": False, "error": "Gli oggetti non appartengono alla stessa categoria."}), 400

    for order, item_id in enumerate(item_ids):
        items_by_id[item_id].sort_order = order
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/riordina-oggetti-viaggio", methods=["POST"])
@login_required
def reorder_trip_items():
    """
    Riordina gli oggetti di una categoria SOLO per questo viaggio
    (TripItem.sort_order): a differenza di /riordina-oggetti (che
    cambia l'ordine nel catalogo, riflesso poi nei NUOVI viaggi), questo
    NON tocca il catalogo né altri viaggi — un cambiamento qui resta
    isolato a questo viaggio soltanto.
    """
    from app.models import TripItem

    data = request.get_json(silent=True) or {}
    trip_item_ids = data.get("trip_item_ids")
    if not isinstance(trip_item_ids, list) or not trip_item_ids:
        return jsonify({"ok": False, "error": "Elenco non valido."}), 400

    try:
        trip_item_ids = [int(i) for i in trip_item_ids]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Elenco non valido."}), 400

    trip_items = TripItem.query.filter(
        TripItem.id.in_(trip_item_ids), TripItem.user_id == current_user.id
    ).all()
    by_id = {ti.id: ti for ti in trip_items}
    if len(by_id) != len(set(trip_item_ids)):
        return jsonify({"ok": False, "error": "Alcuni oggetti non sono più validi: ricarica la pagina."}), 400

    if len({ti.trip_id for ti in by_id.values()}) != 1:
        return jsonify({"ok": False, "error": "Gli oggetti non appartengono allo stesso viaggio."}), 400
    if len({ti.item.category_id for ti in by_id.values()}) != 1:
        return jsonify({"ok": False, "error": "Gli oggetti non appartengono alla stessa categoria."}), 400

    for order, trip_item_id in enumerate(trip_item_ids):
        by_id[trip_item_id].sort_order = order
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/pagine-offline")
@login_required
def offline_pages():
    """
    Elenco delle pagine "importanti" per l'utente corrente (i suoi
    viaggi + le pagine principali), usato dal pulsante "Prepara per
    l'uso offline" (vedi static/js/app.js::prepareOfflineCache) per
    sapere COSA precaricare — non fa nulla da sé, si limita a elencare
    gli indirizzi: è il browser a scaricarli davvero, uno alla volta.
    """
    from app.utils import accessible_trips_query

    urls = [
        url_for("dashboard.index"), url_for("trips.list_trips"),
        url_for("luggage.list_luggage"), url_for("catalog.items"),
        url_for("catalog.categories"), url_for("dashboard.shopping_index"),
    ]
    for trip in accessible_trips_query(current_user).all():
        urls.append(url_for("trips.workspace", trip_id=trip.id))

    return jsonify({"ok": True, "urls": urls})


# Chiavi valide per le larghezze di colonna scelte a mano — un elenco
# esplicito (non qualunque stringa) per evitare che il campo JSON
# dell'utente si riempia di chiavi arbitrarie nel tempo.
_COLUMN_WIDTH_TABLES = {"catalog-items": 5}


@api_bp.route("/colonne-larghezza", methods=["POST"])
@login_required
def save_column_widths():
    """
    Salva la larghezza (in percentuale) di ciascuna colonna di una
    tabella, scelta trascinando il bordo di un'intestazione — vedi
    static/js/dashboard.js::initColumnResize. Si applica SOLO in vista
    testo (mai con le icone): salvata comunque anche se in quel momento
    si è in vista icone, così è pronta appena si torna al testo.
    """
    data = request.get_json(silent=True) or {}
    table_key = data.get("table")
    widths = data.get("widths")

    expected_cols = _COLUMN_WIDTH_TABLES.get(table_key)
    if expected_cols is None:
        return jsonify({"ok": False, "error": "Tabella non riconosciuta."}), 400
    if not isinstance(widths, list) or len(widths) != expected_cols:
        return jsonify({"ok": False, "error": "Larghezze non valide."}), 400
    try:
        widths = [round(float(w), 2) for w in widths]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Larghezze non valide."}), 400
    if any(w < 4 or w > 90 for w in widths):
        return jsonify({"ok": False, "error": "Ogni colonna deve restare tra il 4% e il 90%."}), 400

    current_user.set_column_widths(table_key, widths)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/pubblico", methods=["POST"])
@login_required
def toggle_public():
    """
    Spunta/togli dal catalogo PUBBLICO esportabile — un oggetto,
    categoria o valigia del PROPRIO catalogo. Non ha alcun effetto
    sull'uso normale dell'app: serve solo a scegliere cosa finisce nel
    file scaricato da "Esporta catalogo pubblico" (impostazioni).
    """
    from app.models import Category, Item, Luggage

    data = request.get_json(silent=True) or {}
    tipo = data.get("tipo")
    obj_id = data.get("id")
    is_public = bool(data.get("is_public"))

    model_by_tipo = {"oggetto": Item, "categoria": Category, "valigia": Luggage}
    model = model_by_tipo.get(tipo)
    if model is None:
        return jsonify({"ok": False, "error": "Tipo non riconosciuto."}), 400

    obj = model.query.filter_by(id=obj_id, owner_id=current_user.id).first()
    if obj is None:
        return jsonify({"ok": False, "error": "Non trovato."}), 404

    obj.is_public = is_public
    db.session.commit()
    return jsonify({"ok": True, "is_public": obj.is_public})
