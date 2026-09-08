"""
catalog/routes.py
==================
Gestione del catalogo PERSONALE dell'utente autenticato: categorie e
oggetti. Ogni query è filtrata per `owner_id == current_user.id`. La
gestione dei "tipi di bagaglio" non esiste più come catalogo separato:
è sostituita dalla sezione Valigie (vedi app/luggage/routes.py).

Qui vive anche la "vista più approfondita" di un singolo oggetto, e il
pulsante per (ri)importare il catalogo di base nel proprio catalogo.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Category, Item, TripItem, Trip, ItemVariant
from app.forms import CategoryForm, ItemForm, ItemVariantForm
from app.utils import sync_trip_items
from app.importer import (
    import_base_catalog_for_user, has_custom_base_catalog,
    has_custom_base_catalog,
)
from app.access import admin_required

catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalogo", template_folder="../templates/catalog")


# ---------------------------------------------------------------------------
# Categorie
# ---------------------------------------------------------------------------
@catalog_bp.route("/categorie", methods=["GET", "POST"])
@login_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        cat = Category(
            owner_id=current_user.id,
            name=form.name.data.strip(),
            color=form.color.data.strip(),
            icon=(form.icon.data or "shapes").strip(),
            sort_order=Category.query.filter_by(owner_id=current_user.id).count(),
        )
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{cat.name}" creata.', "success")
        return redirect(url_for("catalog.categories"))

    all_categories = (
        Category.query.filter_by(owner_id=current_user.id)
        .order_by(Category.sort_order, Category.name).all()
    )
    return render_template("catalog/categories.html", form=form, categories=all_categories)


@catalog_bp.route("/categorie/<int:category_id>/modifica", methods=["POST"])
@login_required
def edit_category(category_id):
    cat = Category.query.filter_by(id=category_id, owner_id=current_user.id).first_or_404()
    cat.name = request.form.get("name", cat.name).strip()
    cat.color = request.form.get("color", cat.color).strip()
    cat.icon = request.form.get("icon", cat.icon).strip() or cat.icon
    db.session.commit()
    flash(f'Categoria "{cat.name}" aggiornata.', "success")
    return redirect(url_for("catalog.categories"))


@catalog_bp.route("/categorie/<int:category_id>/elimina", methods=["POST"])
@login_required
def delete_category(category_id):
    cat = Category.query.filter_by(id=category_id, owner_id=current_user.id).first_or_404()
    if cat.items:
        flash(
            f'Non puoi eliminare "{cat.name}": contiene ancora {len(cat.items)} oggetti. '
            "Spostali in un'altra categoria prima di eliminarla.",
            "error",
        )
    else:
        db.session.delete(cat)
        db.session.commit()
        flash(f'Categoria "{cat.name}" eliminata.', "success")
    return redirect(url_for("catalog.categories"))


# ---------------------------------------------------------------------------
# Oggetti
# ---------------------------------------------------------------------------
def _populate_item_choices(form: ItemForm) -> None:
    form.category_id.choices = [
        (c.id, c.name)
        for c in Category.query.filter_by(owner_id=current_user.id)
        .order_by(Category.sort_order, Category.name).all()
    ]


@catalog_bp.route("/oggetti")
@login_required
def items():
    show_archived = request.args.get("archiviati") == "1"

    query = Item.query.filter_by(owner_id=current_user.id)
    query = query.filter_by(archived=True) if show_archived else query.filter_by(archived=False)

    all_items = query.join(Category).order_by(Category.sort_order, Item.sort_order, Item.name).all()
    all_categories = (
        Category.query.filter_by(owner_id=current_user.id)
        .order_by(Category.sort_order, Category.name).all()
    )

    # Raggruppati per categoria, come nel workspace di un viaggio: schede
    # per categoria invece di un menu a tendina che ricarica la pagina.
    grouped = []
    for cat in all_categories:
        cat_items = [i for i in all_items if i.category_id == cat.id]
        if cat_items:
            grouped.append({"category": cat, "catalog_items": cat_items})

    return render_template(
        "catalog/items.html",
        grouped=grouped,
        show_archived=show_archived,
        has_custom_base=has_custom_base_catalog(),
    )


@catalog_bp.route("/oggetti/importa-base", methods=["POST"])
@login_required
def import_base():
    """(Ri)importa il catalogo di base nel catalogo dell'utente corrente, senza duplicare oggetti già presenti."""
    summary = import_base_catalog_for_user(current_user)

    for trip in Trip.query.filter_by(owner_id=current_user.id).all():
        sync_trip_items(trip, current_user)

    if summary.items_created:
        flash(
            f"Catalogo di base importato: {summary.categories_created} categorie e "
            f"{summary.items_created} oggetti nuovi aggiunti al tuo catalogo "
            f"({summary.items_matched} già presenti, lasciati invariati).",
            "success",
        )
    else:
        flash("Il tuo catalogo contiene già tutti gli oggetti del catalogo di base.", "info")
    return redirect(url_for("catalog.items"))


@catalog_bp.route("/oggetti/nuovo", methods=["GET", "POST"])
@login_required
def new_item():
    form = ItemForm()
    _populate_item_choices(form)

    if form.validate_on_submit():
        item = Item(
            owner_id=current_user.id,
            name=form.name.data.strip(),
            category_id=form.category_id.data,
            quantity_rule=form.quantity_rule.data,
            fixed_qty=form.fixed_qty.data or 0,
            per_day_extra=form.per_day_extra.data or 0,
            default_luggage_type=form.default_luggage_type.data or None,
            weight_grams=form.weight_grams.data,
            notes=(form.notes.data or "").strip(),
            sort_order=Item.query.filter_by(owner_id=current_user.id, category_id=form.category_id.data).count(),
        )
        db.session.add(item)
        db.session.commit()

        for trip in Trip.query.filter_by(owner_id=current_user.id).all():
            sync_trip_items(trip, current_user)

        flash(f'Oggetto "{item.name}" aggiunto al catalogo.', "success")
        return redirect(url_for("catalog.items"))

    return render_template("catalog/item_form.html", form=form, item=None)


@catalog_bp.route("/oggetti/<int:item_id>")
@login_required
def item_detail(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()

    history = (
        TripItem.query.filter_by(item_id=item.id, user_id=current_user.id)
        .join(Trip)
        .order_by(Trip.start_date.desc())
        .all()
    )

    # Se si arriva qui da "Vai alle impostazioni dell'oggetto" dentro un
    # viaggio, mostra un pulsante per tornarci direttamente (invece di
    # dover rifare tutta la strada dal Catalogo).
    from_trip = None
    trip_id_param = request.args.get("da_viaggio", type=int)
    if trip_id_param:
        candidate = Trip.query.get(trip_id_param)
        if candidate is not None and candidate.is_accessible_by(current_user):
            from_trip = candidate

    return render_template(
        "catalog/item_detail.html", item=item, history=history, from_trip=from_trip,
        variant_form=ItemVariantForm(),
    )


@catalog_bp.route("/oggetti/<int:item_id>/modelli", methods=["POST"])
@login_required
def add_variant(item_id):
    """Aggiunge un nuovo modello (es. una camicia/un paio di pantaloni specifico) a un oggetto."""
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    form = ItemVariantForm()
    if form.validate_on_submit():
        variant = ItemVariant(
            item_id=item.id,
            description=form.description.data.strip(),
            weight_grams=form.weight_grams.data,
            owned_qty=form.owned_qty.data or 0,
            sort_order=len(item.variants),
        )
        db.session.add(variant)
        db.session.commit()
        flash(f'Modello "{variant.description}" aggiunto.', "success")
    else:
        for errors in form.errors.values():
            for e in errors:
                flash(e, "error")
    return redirect(url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/modifica", methods=["GET", "POST"])
@login_required
def edit_variant(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    form = ItemVariantForm(obj=variant)

    if form.validate_on_submit():
        variant.description = form.description.data.strip()
        variant.weight_grams = form.weight_grams.data
        variant.owned_qty = form.owned_qty.data or 0
        db.session.commit()
        flash(f'Modello "{variant.description}" aggiornato.', "success")
        return redirect(url_for("catalog.item_detail", item_id=item.id))

    return render_template("catalog/variant_form.html", item=item, variant=variant, form=form)


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/elimina", methods=["POST"])
@login_required
def delete_variant(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    nome = variant.description
    db.session.delete(variant)
    db.session.commit()
    flash(f'Modello "{nome}" eliminato.', "success")
    return redirect(url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modifica", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    form = ItemForm(obj=item)
    _populate_item_choices(form)

    if request.method == "GET":
        form.default_luggage_type.data = item.default_luggage_type or ""

    # Oggetto precedente/successivo nella STESSA categoria (stesso ordine
    # del catalogo) — calcolato PRIMA della convalida perché serve sia
    # per i pulsanti di navigazione (in ogni caso) sia per decidere dove
    # reindirizzare dopo "Salva e vai al successivo" (solo se il salvataggio riesce).
    # Resta nello stesso insieme attivo/archiviato dell'oggetto corrente,
    # per coerenza col contesto da cui si viene.
    siblings = (
        Item.query.filter_by(owner_id=current_user.id, category_id=item.category_id, archived=item.archived)
        .order_by(Item.sort_order, Item.name).all()
    )
    sibling_ids = [i.id for i in siblings]
    idx = sibling_ids.index(item.id) if item.id in sibling_ids else -1
    prev_item_id = sibling_ids[idx - 1] if idx > 0 else None
    next_item_id = sibling_ids[idx + 1] if 0 <= idx < len(sibling_ids) - 1 else None

    if form.validate_on_submit():
        category_changed = item.category_id != form.category_id.data
        item.name = form.name.data.strip()
        item.category_id = form.category_id.data
        item.quantity_rule = form.quantity_rule.data
        item.fixed_qty = form.fixed_qty.data or 0
        item.per_day_extra = form.per_day_extra.data or 0
        item.default_luggage_type = form.default_luggage_type.data or None
        item.weight_grams = form.weight_grams.data
        item.notes = (form.notes.data or "").strip()
        if category_changed:
            # Spostato in un'altra categoria (solo da qui, mai per
            # trascinamento): va in fondo al suo nuovo ordine.
            item.sort_order = Item.query.filter_by(
                owner_id=current_user.id, category_id=item.category_id
            ).count()
        db.session.commit()
        flash(f'Oggetto "{item.name}" aggiornato.', "success")

        if "save_and_next" in request.form:
            if next_item_id:
                return redirect(url_for("catalog.edit_item", item_id=next_item_id))
            flash("Non c'è un oggetto successivo in questa categoria: sei rimasto sull'ultimo.", "success")
            return redirect(url_for("catalog.edit_item", item_id=item.id))

        # Resta sulla pagina di modifica (non porta al dettaglio o altrove):
        # così i pulsanti precedente/successivo restano usabili in sequenza.
        return redirect(url_for("catalog.edit_item", item_id=item.id))

    return render_template(
        "catalog/item_form.html", form=form, item=item,
        prev_item_id=prev_item_id, next_item_id=next_item_id,
    )


@catalog_bp.route("/oggetti/<int:item_id>/archivia", methods=["POST"])
@login_required
def toggle_archive_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    item.archived = not item.archived
    db.session.commit()
    stato = "archiviato" if item.archived else "ripristinato nel catalogo attivo"
    flash(f'Oggetto "{item.name}" {stato}.', "success")
    return redirect(request.referrer or url_for("catalog.items"))


@catalog_bp.route("/oggetti/<int:item_id>/elimina", methods=["POST"])
@login_required
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    if item.trip_items:
        flash(
            f'Non puoi eliminare definitivamente "{item.name}": è presente in '
            f"{len(item.trip_items)} viaggi. Puoi archiviarlo per nasconderlo dal catalogo attivo.",
            "error",
        )
        return redirect(url_for("catalog.item_detail", item_id=item.id))

    db.session.delete(item)
    db.session.commit()
    flash(f'Oggetto "{item.name}" eliminato definitivamente.', "success")
    return redirect(url_for("catalog.items"))
