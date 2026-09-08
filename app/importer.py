"""
importer.py
===========
Importazione di un catalogo (categorie + oggetti, opzionalmente anche le
quantità personali di un viaggio) nel catalogo di UN utente specifico.

Usi:
  1. `import_base_catalog_for_user(user)` — importa il "catalogo di base"
     nel catalogo dell'utente indicato. Chiamata automaticamente alla
     creazione di ogni nuovo utente, ed è anche disponibile come azione
     manuale ("Importa catalogo di base") dalla pagina Catalogo. Usa il
     catalogo di base PERSONALIZZATO se un amministratore ne ha esportato
     uno (vedi sotto), altrimenti quello imbustato con l'app.
  2. `export_catalog_as_base(owner)` — SOLO admin: promuove il catalogo
     ATTUALE di `owner` (categorie + oggetti, con tutte le impostazioni:
     regola quantità, peso, tipologia predefinita) a nuovo "catalogo di
     base", salvato in un file JSON nella cartella dati persistente
     (sopravvive quindi agli aggiornamenti dell'app, a differenza del
     catalogo imbustato nel codice). Da qui in poi, ogni nuovo utente e
     ogni "Importa catalogo di base" useranno questo al posto
     dell'originale.
  3. `reset_base_catalog_to_default()` — rimuove la personalizzazione,
     tornando al catalogo di base originale imbustato con l'app.
  4. `import_notion_csv(csv_path, owner, target_trip=None)` — importa un
     CSV Notion qualsiasi nel catalogo di `owner`. Se `target_trip` è
     indicato, popola anche la lista PERSONALE di `owner` per quel
     viaggio (le quantità "N. Imbarco"/"N. Stiva" vengono assegnate alla
     prima valigia attiva di `owner` con tipologia cabina/stiva).

In tutti i casi l'importazione è "get-or-create" per nome+categoria
NELL'AMBITO DEL SINGOLO UTENTE: rilanciarla più volte non crea duplicati
e non tocca in alcun modo il catalogo di altri utenti.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.extensions import db
from app.models import (
    Category, Item, Trip, TripItem, TripItemQty, QuantityRule, User, LuggageType,
)


BASE_CATALOG_PATH = Path(__file__).resolve().parent / "seed_data" / "catalogo_base.csv"

KNOWN_PER_DAY_ITEMS = {"mutande", "calze", "calzini", "boxer"}
KNOWN_FIXED_ITEMS = {
    "iphone", "ipad", "apple watch", "patente", "passaporto",
    "carta di identità", "carta di identita", "tessera sanitaria",
}


def _custom_base_catalog_path() -> Path:
    """
    Percorso del catalogo di base PERSONALIZZATO (se un admin ne ha
    esportato uno), nella cartella dati persistente — non nel codice
    dell'app, altrimenti andrebbe perso ad ogni aggiornamento.
    """
    from app.config import DATA_DIR
    return DATA_DIR / "catalogo_base.json"


def export_catalog_as_base(owner: User) -> int:
    """
    Promuove il catalogo PUBBLICO di `owner` (categorie, oggetti, modelli
    e valigie con `is_public=True` — vedi Category/Item/Luggage.is_public
    e api/routes.py::toggle_public) a nuovo catalogo di base, con tutte le
    impostazioni di ciascun oggetto (non solo nome e categoria, a
    differenza del CSV originale). Ritorna il numero di oggetti esportati.
    Ciò che NON è spuntato come pubblico resta privato: non finisce mai
    in questo file, per quanto sia comunque presente nel catalogo
    personale di `owner`.
    """
    from app.models import Luggage

    categories = (
        Category.query.filter_by(owner_id=owner.id, is_public=True)
        .order_by(Category.sort_order).all()
    )
    public_category_ids = {c.id for c in categories}
    data = {"categories": [], "items": [], "luggage": []}

    for cat in categories:
        data["categories"].append({
            "name": cat.name, "color": cat.color, "icon": cat.icon, "sort_order": cat.sort_order,
        })

    # Un oggetto pubblico la cui categoria NON lo è finirebbe "orfano"
    # all'importazione (nessuna categoria pubblica da associargli) — si
    # esporta comunque, la categoria verrà semplicemente ricreata come
    # pubblica anche lei (comportamento più prevedibile che scartarlo
    # in silenzio, dato che l'utente ha spuntato ESPLICITAMENTE l'oggetto).
    items = (
        Item.query.filter_by(owner_id=owner.id, archived=False, is_public=True)
        .order_by(Item.category_id, Item.sort_order).all()
    )
    for item in items:
        if item.category_id not in public_category_ids:
            data["categories"].append({
                "name": item.category.name, "color": item.category.color,
                "icon": item.category.icon, "sort_order": item.category.sort_order,
            })
            public_category_ids.add(item.category_id)
        data["items"].append({
            "name": item.name,
            "category": item.category.name,
            "quantity_rule": item.quantity_rule,
            "fixed_qty": item.fixed_qty,
            "per_day_extra": item.per_day_extra,
            "default_luggage_type": item.default_luggage_type,
            "weight_grams": item.weight_grams,
            "notes": item.notes,
            "sort_order": item.sort_order,
            "variants": [
                {
                    "description": v.description, "weight_grams": v.weight_grams,
                    "owned_qty": v.owned_qty, "sort_order": v.sort_order,
                }
                for v in item.variants
            ],
        })

    luggages = (
        Luggage.query.filter_by(owner_id=owner.id, is_public=True)
        .order_by(Luggage.name).all()
    )
    for lug in luggages:
        data["luggage"].append({
            "brand": lug.brand, "name": lug.name, "tipologia": lug.tipologia,
            "weight_kg": lug.weight_kg, "capacity_liters": lug.capacity_liters,
            "notes": lug.notes, "is_default_for_new_trip": lug.is_default_for_new_trip,
        })

    path = _custom_base_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data["items"])


def reset_base_catalog_to_default() -> None:
    """Rimuove il catalogo di base personalizzato: si torna a quello originale imbustato con l'app."""
    _custom_base_catalog_path().unlink(missing_ok=True)


def has_custom_base_catalog() -> bool:
    return _custom_base_catalog_path().exists()


def _import_base_catalog_json(json_path: Path, owner: User) -> "ImportSummary":
    """Importa il catalogo di base PERSONALIZZATO (JSON, con tutte le impostazioni) nel catalogo di `owner`."""
    from app.models import ItemVariant, Luggage

    summary = ImportSummary()
    data = json.loads(json_path.read_text(encoding="utf-8"))

    category_cache: dict[str, Category] = {
        c.name: c for c in Category.query.filter_by(owner_id=owner.id).all()
    }
    for cat_data in data.get("categories", []):
        if cat_data["name"] in category_cache:
            continue
        category = Category(
            name=cat_data["name"], owner_id=owner.id,
            color=cat_data.get("color") or "#8C6D46", icon=cat_data.get("icon") or "shapes",
            sort_order=cat_data.get("sort_order", len(category_cache)),
        )
        db.session.add(category)
        db.session.flush()
        category_cache[cat_data["name"]] = category
        summary.categories_created += 1

    next_sort_order: dict[int, int] = {}
    for item_data in data.get("items", []):
        name = (item_data.get("name") or "").strip()
        if not name:
            summary.rows_skipped += 1
            continue

        cat_name = item_data.get("category") or "Senza categoria"
        category = category_cache.get(cat_name)
        if category is None:
            category = Category(name=cat_name, owner_id=owner.id, sort_order=len(category_cache))
            db.session.add(category)
            db.session.flush()
            category_cache[cat_name] = category
            summary.categories_created += 1

        item = Item.query.filter_by(name=name, category_id=category.id, owner_id=owner.id).first()
        if item is not None:
            summary.items_matched += 1
            continue

        item = Item(
            name=name,
            owner_id=owner.id,
            category_id=category.id,
            quantity_rule=item_data.get("quantity_rule", QuantityRule.MANUAL),
            fixed_qty=item_data.get("fixed_qty", 1),
            per_day_extra=item_data.get("per_day_extra", 1),
            default_luggage_type=item_data.get("default_luggage_type"),
            weight_grams=item_data.get("weight_grams"),
            notes=item_data.get("notes", ""),
            sort_order=next_sort_order.setdefault(
                category.id,
                Item.query.filter_by(owner_id=owner.id, category_id=category.id).count(),
            ),
        )
        next_sort_order[category.id] += 1
        db.session.add(item)
        db.session.flush()
        summary.items_created += 1

        for v_data in item_data.get("variants", []):
            description = (v_data.get("description") or "").strip()
            if not description:
                continue
            db.session.add(ItemVariant(
                item_id=item.id, description=description,
                weight_grams=v_data.get("weight_grams"),
                owned_qty=v_data.get("owned_qty", 1),
                sort_order=v_data.get("sort_order", 0),
            ))

    for lug_data in data.get("luggage", []):
        name = (lug_data.get("name") or "").strip()
        if not name:
            continue
        exists = Luggage.query.filter_by(owner_id=owner.id, name=name).first()
        if exists is not None:
            continue
        db.session.add(Luggage(
            owner_id=owner.id, brand=lug_data.get("brand", ""), name=name,
            tipologia=lug_data.get("tipologia", LuggageType.STIVA),
            weight_kg=lug_data.get("weight_kg"), capacity_liters=lug_data.get("capacity_liters"),
            notes=lug_data.get("notes", ""),
            is_default_for_new_trip=lug_data.get("is_default_for_new_trip", False),
        ))

    db.session.commit()
    return summary


def _parse_bool(value: str) -> bool:
    return (value or "").strip().lower() in ("sì", "si", "yes", "true", "x", "1")


def _parse_int(value: str) -> int:
    try:
        return max(int(str(value).strip()), 0)
    except (ValueError, TypeError):
        return 0


@dataclass
class ImportSummary:
    categories_created: int = 0
    items_created: int = 0
    items_matched: int = 0
    rows_skipped: int = 0
    trip_items_written: int = 0
    warnings: list = field(default_factory=list)


def import_notion_csv(csv_path, owner: User, target_trip: Trip | None = None) -> ImportSummary:
    """Importa un file CSV esportato da Notion nel catalogo di `owner`."""
    summary = ImportSummary()

    category_cache: dict[str, Category] = {
        c.name: c for c in Category.query.filter_by(owner_id=owner.id).all()
    }
    # Prossimo sort_order libero per ciascuna categoria (per accodare i
    # nuovi oggetti importati in fondo, senza mischiare l'ordine manuale
    # già impostato su quelli esistenti).
    next_sort_order: dict[int, int] = {}

    trip_luggage_cabina = trip_luggage_stiva = None
    if target_trip is not None:
        for tl in target_trip.trip_luggages:
            if tl.user_id != owner.id or tl.luggage is None:
                continue
            if tl.luggage.tipologia == LuggageType.CABINA and trip_luggage_cabina is None:
                trip_luggage_cabina = tl
            if tl.luggage.tipologia == LuggageType.STIVA and trip_luggage_stiva is None:
                trip_luggage_stiva = tl

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                summary.rows_skipped += 1
                continue

            tipo = (row.get("Tipo") or "Senza categoria").strip() or "Senza categoria"
            category = category_cache.get(tipo)
            if category is None:
                category = Category(
                    name=tipo,
                    owner_id=owner.id,
                    sort_order=len(category_cache),
                )
                db.session.add(category)
                db.session.flush()
                category_cache[tipo] = category
                summary.categories_created += 1

            item = Item.query.filter_by(name=name, category_id=category.id, owner_id=owner.id).first()
            if item is None:
                quantity_rule = QuantityRule.MANUAL
                fixed_qty = 1
                per_day_extra = 1
                lname = name.lower()
                if lname in KNOWN_PER_DAY_ITEMS:
                    quantity_rule = QuantityRule.PER_DAY
                elif lname in KNOWN_FIXED_ITEMS:
                    quantity_rule = QuantityRule.FIXED

                item = Item(
                    name=name,
                    owner_id=owner.id,
                    category_id=category.id,
                    quantity_rule=quantity_rule,
                    fixed_qty=fixed_qty,
                    per_day_extra=per_day_extra,
                    sort_order=next_sort_order.setdefault(
                        category.id,
                        Item.query.filter_by(owner_id=owner.id, category_id=category.id).count(),
                    ),
                )
                next_sort_order[category.id] += 1
                db.session.add(item)
                db.session.flush()
                summary.items_created += 1
            else:
                summary.items_matched += 1

            if target_trip is not None:
                trip_item = TripItem.query.filter_by(trip_id=target_trip.id, item_id=item.id).first()
                if trip_item is None:
                    trip_item = TripItem(trip_id=target_trip.id, item_id=item.id, user_id=owner.id)
                    db.session.add(trip_item)
                    db.session.flush()

                trip_item.conservato = _parse_bool(row.get("Conservato"))
                if _parse_bool(row.get("Da comprare")):
                    n_tot = _parse_int(row.get("N. Totale"))
                    trip_item.missing_qty = n_tot if n_tot > 0 else 1

                n_imbarco = _parse_int(row.get("N. Imbarco"))
                n_stiva = _parse_int(row.get("N. Stiva"))
                trip_item.target_qty = n_imbarco + n_stiva

                if trip_luggage_cabina:
                    _upsert_qty(trip_item.id, trip_luggage_cabina.id, n_imbarco)
                elif n_imbarco:
                    summary.warnings.append(
                        f'"{name}": {n_imbarco} in cabina ignorati (nessuna valigia di cabina attiva).'
                    )
                if trip_luggage_stiva:
                    _upsert_qty(trip_item.id, trip_luggage_stiva.id, n_stiva)
                elif n_stiva:
                    summary.warnings.append(
                        f'"{name}": {n_stiva} in stiva ignorati (nessuna valigia di stiva attiva).'
                    )

                summary.trip_items_written += 1

    db.session.commit()
    return summary


def import_base_catalog_for_user(user: User) -> ImportSummary:
    """
    Importa il catalogo di base nel catalogo dell'utente indicato: quello
    PERSONALIZZATO se un admin ne ha esportato uno (vedi
    export_catalog_as_base), altrimenti quello originale imbustato con
    l'app.
    """
    custom_path = _custom_base_catalog_path()
    if custom_path.exists():
        return _import_base_catalog_json(custom_path, owner=user)
    return import_notion_csv(BASE_CATALOG_PATH, owner=user, target_trip=None)


def _upsert_qty(trip_item_id: int, trip_luggage_id: int, quantity: int) -> None:
    row = TripItemQty.query.filter_by(trip_item_id=trip_item_id, trip_luggage_id=trip_luggage_id).first()
    if row is None:
        db.session.add(TripItemQty(trip_item_id=trip_item_id, trip_luggage_id=trip_luggage_id, quantity=quantity))
    else:
        row.quantity = quantity
