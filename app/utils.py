"""
utils.py
========
Logica di business che non appartiene né ai modelli né alle route.

Cambio chiave rispetto alla v2.0: quasi tutte le funzioni relative a un
viaggio ora richiedono anche l'utente (`user`) per cui si sta operando,
perché la lista da mettere in valigia è personale (vedi models.py per la
spiegazione completa). Le "valigie" (`Luggage`/`TripLuggage`) sostituiscono
il vecchio concetto di "tipo di bagaglio".
"""

import json
import re
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import (
    Item, Trip, TripLuggage, TripItem, TripItemQty, QuantityRule, Luggage,
    LuggageType, User, TripShare, TripItemVariantQty,
)


def db_file_path() -> Path | None:
    """
    Percorso del file SQLite corrente, oppure None se il database non è
    un file su disco (es. ':memory:' usato nei test): condivisa tra i
    blueprint backup e settings (statistiche), che ne hanno entrambi
    bisogno.
    """
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    raw_path = uri[len(prefix):]
    if raw_path in (":memory:", ""):
        return None
    return Path(raw_path)


# ---------------------------------------------------------------------------
# Numeri in stile italiano/internazionale: punto = separatore delle
# migliaia, virgola = separatore decimale (es. "1.500,25"). Usate sia dal
# campo form DecimalCommaFloatField (app/forms.py) sia dal filtro Jinja
# `numero_it` (app/__init__.py), così le due direzioni (scrittura e
# lettura) restano sempre coerenti tra loro.
# ---------------------------------------------------------------------------
def format_number_it(value, decimals: int = 2) -> str:
    """
    Formatta un numero secondo la convenzione italiana. Es. 1500.5 con
    decimals=2 -> "1.500,5" (gli zeri decimali superflui vengono tolti).
    Restituisce stringa vuota per None.
    """
    if value is None:
        return ""
    # f"{...:,.Nf}" usa la virgola per le migliaia e il punto per i
    # decimali (stile statunitense): scambiamo i due separatori per
    # ottenere lo stile italiano.
    formatted = f"{float(value):,.{decimals}f}"
    if "." in formatted:
        integer_part, decimal_part = formatted.split(".")
        decimal_part = decimal_part.rstrip("0")
    else:
        integer_part, decimal_part = formatted, ""
    integer_part = integer_part.replace(",", ".")
    return f"{integer_part},{decimal_part}" if decimal_part else integer_part


def parse_number_it(raw: str) -> float | None:
    """
    Converte una stringa scritta in stile italiano in un float standard:
    il PUNTO (se presente) è SEMPRE trattato come separatore delle
    migliaia e rimosso; la VIRGOLA (se presente) è SEMPRE il separatore
    decimale e diventa un punto per il parsing. Restituisce None per una
    stringa vuota; solleva ValueError se il risultato non è un numero.
    """
    raw = (raw or "").strip().replace(" ", "")
    if not raw:
        return None
    raw = raw.replace(".", "").replace(",", ".")
    return float(raw)


# ---------------------------------------------------------------------------
# Calcolo della quantità automatica di un oggetto per un dato viaggio
# ---------------------------------------------------------------------------
def compute_auto_quantity(item: Item, trip: Trip) -> int:
    if item.quantity_rule == QuantityRule.FIXED:
        return max(item.fixed_qty, 0)
    if item.quantity_rule == QuantityRule.PER_DAY:
        return max(trip.days + item.per_day_extra, 0)
    return 0  # MANUAL


def user_trip_luggages(trip: Trip, user: User) -> list[TripLuggage]:
    """
    Le valigie utilizzabili da `user` in questo viaggio: le PROPRIE
    valigie attive, più quelle di ALTRI collaboratori condivise
    esplicitamente con `user` (vedi TripLuggageShare) — così può
    metterci dentro le proprie cose anche se non è lui il proprietario
    della valigia fisica. Ordinate cabina/stiva/zaino.

    Esclude difensivamente eventuali righe "orfane" (TripLuggage.luggage_id
    che punta a una Luggage ormai eliminata): SQLite non applica i
    vincoli di integrità referenziale di default, quindi eliminare una
    valigia ancora usata in un viaggio poteva lasciare in giro un
    riferimento a nulla e mandare in errore l'intera Home/Viaggi (bug
    reale, vedi CHANGELOG). La causa a monte è corretta in models.py
    (cascade automatico) e in migrations.py (pulizia dei dati già
    orfani), ma questo controllo resta comunque utile come ulteriore
    rete di sicurezza.
    """
    usable = [
        tl for tl in trip.trip_luggages
        if tl.luggage is not None and tl.is_usable_by(user.id)
    ]
    return sorted(usable, key=lambda tl: (LuggageType.sort_key(tl.luggage.tipologia), tl.sort_order))


def luggage_display_labels(trip_luggages: list[TripLuggage]) -> dict[int, str]:
    """
    Etichetta breve da mostrare per ciascuna valigia attiva negli steppers:
    solo la tipologia (es. "Cabina") se è l'UNICA di quel tipo nel
    viaggio; se ce ne sono due o più della stessa tipologia (es. due
    valigie da cabina), aggiunge un riferimento alla valigia specifica
    (marca o nome) per poterle distinguere — altrimenti, sullo stepper,
    sarebbero indistinguibili a colpo d'occhio (specialmente su mobile,
    dove il nome completo compare solo al tocco prolungato/hover, poco
    scopribile — bug reale segnalato).
    """
    counts: dict[str, int] = {}
    for tl in trip_luggages:
        counts[tl.luggage.tipologia] = counts.get(tl.luggage.tipologia, 0) + 1

    labels = {}
    for tl in trip_luggages:
        base = tl.luggage.tipologia_label
        if counts[tl.luggage.tipologia] > 1:
            labels[tl.id] = f"{base} · {tl.luggage.brand or tl.luggage.name}"
        else:
            labels[tl.id] = base
    return labels


def sync_trip_items(trip: Trip, user: User, copy_from_trip: Trip | None = None) -> None:
    """
    Garantisce che esista un TripItem PERSONALE di `user` per ogni oggetto
    attivo del SUO catalogo, per il viaggio indicato. Idempotente: righe
    già esistenti non vengono toccate. Se `copy_from_trip` è indicato (un
    viaggio precedente dello STESSO utente), le quantità vengono copiate
    per valigia fisica (stessa `Luggage.id`, se ancora attiva in questo
    viaggio) invece che ricalcolate da zero.

    IMPORTANTE: l'automazione (Fissa/Per giorno) determina SOLO
    `target_qty` (l'obiettivo). La distribuzione tra le valigie resta
    SEMPRE a zero e va compilata a mano dall'utente — non viene mai
    pre-scelta una valigia "di default" per l'automazione, nemmeno se
    `Item.default_luggage_type` è impostato (quel campo serve solo a
    mostrare un avviso se l'oggetto finisce in una valigia diversa, vedi
    TripItem.has_luggage_mismatch). Unica eccezione: quando si copiano le
    quantità da un viaggio precedente, che restano quelle scelte a mano
    dall'utente in quel viaggio.
    """
    existing_item_ids = {
        ti.item_id for ti in TripItem.query.filter_by(trip_id=trip.id, user_id=user.id).all()
    }
    active_items = Item.query.filter_by(owner_id=user.id, archived=False).all()
    user_luggages = user_trip_luggages(trip, user)

    prev_data = {}
    if copy_from_trip is not None:
        prev_items = TripItem.query.filter_by(trip_id=copy_from_trip.id, user_id=user.id).all()
        for pti in prev_items:
            qty_by_luggage_id = {q.trip_luggage.luggage_id: q.quantity for q in pti.quantities}
            prev_data[pti.item_id] = {
                "target_qty": pti.target_qty,
                "missing_qty": pti.missing_qty,
                "note": pti.note,
                "qty_by_luggage_id": qty_by_luggage_id,
            }

    for item in active_items:
        if item.id in existing_item_ids:
            continue

        ti = TripItem(trip_id=trip.id, item_id=item.id, user_id=user.id, sort_order=item.sort_order)
        prev = prev_data.get(item.id)

        if prev is not None:
            ti.missing_qty = prev["missing_qty"]
            ti.note = prev["note"]
            ti.target_qty = prev["target_qty"]
        elif item.quantity_rule != QuantityRule.MANUAL:
            ti.target_qty = compute_auto_quantity(item, trip)

        db.session.add(ti)
        db.session.flush()

        for tl in user_luggages:
            qty = prev["qty_by_luggage_id"].get(tl.luggage_id, 0) if prev is not None else 0
            db.session.add(TripItemQty(trip_item_id=ti.id, trip_luggage_id=tl.id, quantity=qty))

    db.session.commit()


def recompute_automatic_quantities(trip: Trip, user: User) -> int:
    """
    Ricalcola SOLO `target_qty` per gli oggetti FIXED/PER_DAY di `user` in
    questo viaggio (es. sono cambiate le date). Non tocca MAI la
    distribuzione tra le valigie, che resta quella scelta a mano
    dall'utente — vedi la nota in sync_trip_items.
    """
    updated = 0

    trip_items = (
        TripItem.query.filter_by(trip_id=trip.id, user_id=user.id)
        .join(Item)
        .filter(Item.quantity_rule.in_([QuantityRule.FIXED, QuantityRule.PER_DAY]))
        .all()
    )
    for ti in trip_items:
        new_qty = compute_auto_quantity(ti.item, trip)
        if ti.target_qty != new_qty:
            ti.target_qty = new_qty
            updated += 1

    db.session.commit()
    return updated


def ensure_default_trip_luggages(trip: Trip, user: User) -> None:
    """
    Se `user` non ha ancora nessuna valigia attiva su questo viaggio,
    attiva automaticamente le sue valigie marcate "predefinita per un
    nuovo viaggio". Chiamata sia alla creazione di un viaggio (per il
    proprietario) sia, in modo pigro, la prima volta che un collaboratore
    apre un viaggio condiviso.
    """
    already_active_ids = {tl.luggage_id for tl in trip.trip_luggages if tl.user_id == user.id}
    defaults = Luggage.query.filter_by(owner_id=user.id, is_default_for_new_trip=True).all()
    sort_order = len(trip.trip_luggages)
    for lug in defaults:
        if lug.id in already_active_ids:
            continue
        db.session.add(TripLuggage(trip_id=trip.id, luggage_id=lug.id, user_id=user.id, sort_order=sort_order))
        sort_order += 1
    if defaults:
        db.session.commit()


# ---------------------------------------------------------------------------
# Provisioning di un nuovo utente
# ---------------------------------------------------------------------------
def provision_new_user_defaults(user: User) -> None:
    """
    Importa il catalogo di base nel catalogo personale del nuovo
    utente, poi crea le due valigie generiche di partenza SOLO se il
    catalogo importato non ne ha già portate (un catalogo JSON
    personalizzato, a differenza del vecchio CSV, può includere le
    proprie valigie — due valigie generiche IN PIÙ, oltre a quelle già
    scelte con cura in un catalogo curato, sarebbero solo doppioni).
    """
    from app.importer import import_base_catalog_for_user

    import_base_catalog_for_user(user)

    if Luggage.query.filter_by(owner_id=user.id).count() == 0:
        db.session.add_all([
            Luggage(owner_id=user.id, name="Valigia da stiva", tipologia=LuggageType.STIVA,
                    is_default_for_new_trip=True),
            Luggage(owner_id=user.id, name="Bagaglio a mano", tipologia=LuggageType.CABINA,
                    is_default_for_new_trip=True),
        ])
        db.session.commit()


# ---------------------------------------------------------------------------
# Accesso ai viaggi (proprietà + condivisione)
# ---------------------------------------------------------------------------
def accessible_trips_query(user: User):
    shared_trip_ids = [s.trip_id for s in TripShare.query.filter_by(user_id=user.id).all()]
    if shared_trip_ids:
        return Trip.query.filter(db.or_(Trip.owner_id == user.id, Trip.id.in_(shared_trip_ids)))
    return Trip.query.filter(Trip.owner_id == user.id)


# ---------------------------------------------------------------------------
# Statistiche personali per un viaggio (chi guarda vede il PROPRIO stato)
# ---------------------------------------------------------------------------
def trip_stats(trip: Trip, user: User) -> dict:
    trip_items = TripItem.query.filter_by(trip_id=trip.id, user_id=user.id).all()

    totale = len(trip_items)
    conservati = sum(1 for ti in trip_items if ti.status == "conservato")
    da_comprare = sum(1 for ti in trip_items if ti.status == "da_comprare")
    da_preparare = sum(1 for ti in trip_items if ti.status == "da_preparare")
    non_necessari = sum(1 for ti in trip_items if ti.status == "non_necessario")
    unita_mancanti = sum(ti.missing_qty for ti in trip_items)

    necessari = totale - non_necessari
    percentuale_pronta = round((conservati / necessari) * 100) if necessari else 0

    luggages = []
    for tl in user_trip_luggages(trip, user):
        # Somma GREZZA di quanto è fisicamente nella valigia, indipendentemente
        # dallo stato dell'oggetto: da quando la distribuzione tra le
        # valigie è sempre manuale (mai pre-compilata dall'automazione),
        # ogni quantità > 0 qui rappresenta davvero qualcosa di fisicamente
        # smistato in quella valigia. Filtrare per stato="conservato" (come
        # in versioni precedenti) sottostimava il totale per qualunque
        # oggetto non ancora al proprio obiettivo — bug reale, vedi CHANGELOG.
        #
        # Se la valigia è CONDIVISA, il contenuto va sommato su TUTTI gli
        # utenti che ci hanno messo qualcosa dentro (non solo `user`):
        # interroghiamo quindi TUTTE le righe TripItemQty per questa
        # valigia sul viaggio, indipendentemente da chi possiede il
        # TripItem collegato.
        qty_rows = (
            TripItemQty.query.filter_by(trip_luggage_id=tl.id)
            .join(TripItem)
            .filter(TripItem.trip_id == trip.id)
            .all()
        )
        packed_qty = sum(q.quantity for q in qty_rows)
        content_grams = sum((q.trip_item.item.weight_grams or 0) * q.quantity for q in qty_rows)

        # Oggetti con MODELLI (Item.has_variants): il peso di ciascun
        # modello si somma qui, con lo stesso criterio (per valigia,
        # su tutti gli utenti se condivisa) — senza questo, il peso dei
        # modelli non compariva MAI nella carta d'imbarco (bug reale
        # segnalato), perché prima non erano nemmeno legati a una
        # valigia specifica.
        variant_qty_rows = (
            TripItemVariantQty.query.filter_by(trip_luggage_id=tl.id)
            .join(TripItem)
            .filter(TripItem.trip_id == trip.id)
            .all()
        )
        packed_qty += sum(vq.quantity for vq in variant_qty_rows)
        content_grams += sum((vq.item_variant.weight_grams or 0) * vq.quantity for vq in variant_qty_rows)

        empty_grams = (tl.luggage.weight_kg or 0) * 1000
        luggages.append({
            "trip_luggage_id": tl.id,
            "luggage_id": tl.luggage_id,
            "name": tl.luggage.display_name,
            "tipologia": tl.luggage.tipologia,
            "tipologia_label": LuggageType.LABELS.get(tl.luggage.tipologia, tl.luggage.tipologia),
            "packed_qty": packed_qty,
            "content_weight_grams": content_grams,
            "total_weight_grams": content_grams + empty_grams,
            "is_shared": tl.is_shared,
            "is_mine": tl.user_id == user.id,
        })

    return {
        "totale": totale,
        "conservati": conservati,
        "da_comprare": da_comprare,
        "da_preparare": da_preparare,
        "non_necessari": non_necessari,
        "necessari": necessari,
        "percentuale_pronta": percentuale_pronta,
        "unita_mancanti": unita_mancanti,
        "luggages": luggages,
    }


STATUS_LABELS = {
    "conservato": "In valigia",
    "da_comprare": "Da comprare",
    "da_preparare": "Da preparare",
    "non_necessario": "Non necessario",
}


# ---------------------------------------------------------------------------
# Lista della spesa condivisa, divisa per acquirente
# ---------------------------------------------------------------------------
def trip_shopping_summary(trip: Trip) -> list[dict]:
    """
    Tutti gli oggetti a cui manca qualcosa in questo viaggio (di
    QUALUNQUE collaboratore), raggruppati per chi è assegnato
    all'acquisto (o, se non riassegnato, per chi l'ha segnalato). Un
    sotto-pannello per ciascun collaboratore del viaggio, nell'ordine
    proprietario -> condivisi.
    """
    rows = (
        TripItem.query.filter(TripItem.trip_id == trip.id, TripItem.missing_qty > 0)
        .join(Item)
        .all()
    )

    collaborators = trip.collaborators()
    by_buyer = {u.id: {"user": u, "missing_items": []} for u in collaborators}
    valid_ids = set(by_buyer.keys())

    for ti in rows:
        buyer_id = ti.assigned_buyer_id if ti.assigned_buyer_id in valid_ids else ti.user_id
        if buyer_id not in by_buyer:
            buyer_id = trip.owner_id
        by_buyer[buyer_id]["missing_items"].append(ti)

    return [by_buyer[u.id] for u in collaborators]


# ---------------------------------------------------------------------------
# Immagine di copertina automatica per un viaggio (best-effort)
# ---------------------------------------------------------------------------
_WIKI_TIMEOUT_SECONDS = 4
_HEADERS = {"User-Agent": "ValigiaApp/2.1 (self-hosted personal travel packing app)"}


def _split_destination_candidates(destination: str) -> list[str]:
    parts = re.split(r"\s*(?:,|e |and |et |&)\s*", destination, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    candidates = []
    if parts:
        candidates.append(parts[0])
    if destination.strip() not in candidates:
        candidates.append(destination.strip())
    return candidates


def _wiki_search_title(query: str, lang: str) -> str | None:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(query)}&format=json&srlimit=1"
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_WIKI_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = data.get("query", {}).get("search", [])
    return results[0]["title"] if results else None


def _wiki_page_image(title: str, lang: str) -> str | None:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_WIKI_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    original = data.get("originalimage", {}).get("source")
    thumbnail = data.get("thumbnail", {}).get("source")
    return original or thumbnail


def fetch_trip_cover_image(destination: str, search_terms: str | None = None) -> str | None:
    """
    Cerca un'immagine rappresentativa su Wikipedia. Se `search_terms` è
    indicato, cerca SOLO quello (non anche la destinazione): utile per
    ottenere un'immagine più precisa (es. "tour eiffel" invece della
    sola città). Non solleva mai eccezioni: None se non trova nulla.
    """
    query = (search_terms or "").strip() or (destination or "").strip()
    if not query:
        return None

    candidates = [query] if search_terms else _split_destination_candidates(destination)
    for candidate in candidates:
        for lang in ("it", "en"):
            try:
                title = _wiki_search_title(candidate, lang)
                if not title:
                    continue
                image_url = _wiki_page_image(title, lang)
                if image_url:
                    return image_url
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
                continue
    return None
