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


def _safe_internal_redirect_target(url):
    """
    Restituisce `url` solo se punta a QUESTA stessa applicazione (stesso
    host) — altrimenti None. Diverse viste in questo file tornano
    "da dove si veniva" leggendo il Referer o un campo "ritorno": un
    Referer è un header che il browser invia così com'è, quindi in
    teoria contraffabile da un link costruito ad arte; non va mai
    usato alla cieca in un redirect.
    """
    if not url:
        return None
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != request.host:
        return None
    return url


def _resolve_navigation_context(item=None):
    """
    Da dove tornare, per la pagina "Nuovo oggetto" e per quella
    (unificata) di un oggetto esistente: o un viaggio specifico —
    tramite il parametro esplicito `da_viaggio` (link "Vai alle
    impostazioni dell'oggetto" dal workspace di un viaggio: sempre
    prioritario, perché è deliberato, non un'euristica) — oppure,
    SEMPRE, il catalogo vero e proprio, ancorato esattamente alla riga
    di `item` (`id="item-<id>"`, vedi items.html) quando `item` è già
    un oggetto esistente.

    PRIMA si usava il Referer HTTP (o un campo "ritorno" portato a
    mano lungo la navigazione) per dedurre "da dove si veniva": si
    comportava come il pulsante Indietro del browser — dipendeva
    dall'ultima pagina visitata, non da un punto fisso — e poteva
    finire ovunque (bug reale segnalato). Ora "Torna al catalogo" è
    SEMPRE un link fisso al catalogo vero, mai una supposizione basata
    sulla cronologia: lo scroll fino alla riga giusta lo fa il browser
    da solo, nativamente, tramite l'ancora HTML — non serve nessun
    meccanismo di memorizzazione lato client.

    Restituisce (from_trip, return_to): quest'ultimo è SEMPRE un URL
    utilizzabile (mai None).
    """
    from_trip = None
    trip_id_param = request.values.get("da_viaggio", type=int)
    if trip_id_param:
        candidate = Trip.query.get(trip_id_param)
        if candidate is not None and candidate.is_accessible_by(current_user):
            from_trip = candidate

    if from_trip:
        return_to = url_for("trips.workspace", trip_id=from_trip.id)
    elif item is not None:
        return_to = url_for("catalog.items", archiviati=("1" if item.archived else None)) + f"#item-{item.id}"
    else:
        return_to = url_for("catalog.items")

    return from_trip, return_to


def _nav_context_kwargs(from_trip):
    """Il parametro da riattaccare ai link "Precedente"/"Successivo" e ai
    redirect interni, per non perdere il contesto del viaggio passando
    da un oggetto all'altro in sequenza — il ritorno al catalogo non ha
    più bisogno di essere "portato a mano": si ricalcola da sé ad ogni
    pagina, ancorato all'oggetto CORRENTE (vedi _resolve_navigation_context)."""
    if from_trip:
        return {"da_viaggio": from_trip.id}
    return {}


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
    from_trip, return_to = _resolve_navigation_context()

    if form.validate_on_submit():
        item = Item(
            owner_id=current_user.id,
            name=form.name.data.strip(),
            category_id=form.category_id.data,
            icon=(form.icon.data or "").strip() or None,
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

        flash(f'Oggetto "{item.name}" aggiunto al catalogo. Ora puoi aggiungere i modelli, se ne ha.', "success")
        # Alla pagina UNIFICATA di questo stesso oggetto (non alla lista):
        # è lì che si gestiscono i modelli — un oggetto nuovo non poteva
        # mai averne finché non veniva prima salvato e riaperto, un giro
        # inutile (bug reale segnalato: "non mi viene fornita la
        # possibilità di aggiungere nuovi modelli"). Porta con sé lo
        # stesso contesto (viaggio/pagina di provenienza) da cui si è
        # aperta "Nuovo oggetto".
        return redirect(url_for("catalog.item_detail", item_id=item.id, **_nav_context_kwargs(from_trip)))

    return render_template(
        "catalog/item_detail.html", form=form, item=None,
        from_trip=from_trip, return_to=return_to, nav_kwargs=_nav_context_kwargs(from_trip),
    )


@catalog_bp.route("/oggetti/<int:item_id>", methods=["GET", "POST"])
@login_required
def item_detail(item_id):
    """
    Pagina UNICA di un oggetto: prima erano due pagine separate (questa,
    di sola visualizzazione, e catalog.edit_item, di sola modifica) che
    si rimandavano continuamente l'un l'altra — "Modifica" di qua,
    "Modelli e dettagli" di là — troppi click per una singola modifica
    (bug reale segnalato). Ora un'unica pagina fa entrambe le cose: il
    modulo di modifica (nome, categoria, regola quantità, peso, foto,
    note) e i "dettagli" che richiedono che l'oggetto esista già (zona
    pericolosa, modelli, storico nei viaggi) — questi ultimi non hanno
    più bisogno di una card "Automazione quantità" a parte, che si
    limitava a ripetere in sola lettura campi già editabili proprio
    accanto, nel modulo.
    """
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    form = ItemForm(obj=item)
    _populate_item_choices(form)

    if request.method == "GET":
        form.default_luggage_type.data = item.default_luggage_type or ""

    from_trip, return_to = _resolve_navigation_context(item)
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
        item.icon = (form.icon.data or "").strip() or None
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

        nav_kwargs = _nav_context_kwargs(from_trip)

        if "save_and_next" in request.form:
            if next_item_id:
                return redirect(url_for("catalog.item_detail", item_id=next_item_id, **nav_kwargs))
            flash("Non c'è un oggetto successivo in questa categoria: sei rimasto sull'ultimo.", "success")
            return redirect(url_for("catalog.item_detail", item_id=item.id, **nav_kwargs))

        # "Salva oggetto": salva e riporta ESATTAMENTE alla pagina da cui
        # si era arrivati — lista del catalogo (anche filtrata su
        # "Archiviati"), ancorata esattamente alla riga di questo
        # oggetto — oppure il workspace del viaggio se si veniva da lì —
        # invece di restare bloccati sulla pagina di modifica (bug reale
        # segnalato). `return_to` è un link FISSO (vedi
        # _resolve_navigation_context: niente più Referer/cronologia,
        # bug reale segnalato in seguito — "si comporta come il
        # pulsante Indietro del browser"): lo scroll fino alla riga
        # giusta lo fa il browser da solo, nativamente, tramite l'ancora
        # HTML `#item-<id>` — non serve alcun meccanismo lato client per
        # questo caso specifico (resta invece utile altrove, vedi
        # initGenericScrollRestore in dashboard.js, per pagine come
        # "Categorie" che si ricaricano sulla stessa identica URL).
        return redirect(return_to)

    history = (
        TripItem.query.filter_by(item_id=item.id, user_id=current_user.id)
        .join(Trip)
        .order_by(Trip.start_date.desc())
        .all()
    )

    return render_template(
        "catalog/item_detail.html", form=form, item=item,
        prev_item_id=prev_item_id, next_item_id=next_item_id,
        from_trip=from_trip, return_to=return_to, nav_kwargs=_nav_context_kwargs(from_trip),
        history=history, variant_form=ItemVariantForm(),
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
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/modifica", methods=["GET", "POST"])
@login_required
def edit_variant(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    form = ItemVariantForm(obj=variant)
    return_to = _safe_internal_redirect_target(request.values.get("ritorno") or request.referrer) \
        or url_for("catalog.item_detail", item_id=item.id)

    if form.validate_on_submit():
        variant.description = form.description.data.strip()
        variant.weight_grams = form.weight_grams.data
        variant.owned_qty = form.owned_qty.data or 0
        db.session.commit()
        flash(f'Modello "{variant.description}" aggiornato.', "success")
        return redirect(return_to)

    return render_template("catalog/variant_form.html", item=item, variant=variant, form=form, return_to=return_to)


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/elimina", methods=["POST"])
@login_required
def delete_variant(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    nome = variant.description
    if variant.has_photo:
        old = _existing_photo_path(f"variant_{variant.id}")
        if old:
            old.unlink(missing_ok=True)
    db.session.delete(variant)
    db.session.commit()
    flash(f'Modello "{nome}" eliminato.', "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modifica")
@login_required
def edit_item(item_id):
    """
    Retrocompatibilità: la pagina di modifica separata non esiste più
    da quando si è unita con la pagina dettaglio (vedi catalog.item_detail,
    che ora gestisce entrambe) — un eventuale link o segnalibro verso
    questo vecchio URL viene rediretto lì, preservando eventuali
    parametri di navigazione (`da_viaggio`, `ritorno`).
    """
    return redirect(url_for("catalog.item_detail", item_id=item_id, **request.args))


@catalog_bp.route("/oggetti/<int:item_id>/archivia", methods=["POST"])
@login_required
def toggle_archive_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    item.archived = not item.archived
    db.session.commit()
    stato = "archiviato" if item.archived else "ripristinato nel catalogo attivo"
    flash(f'Oggetto "{item.name}" {stato}.', "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.items"))


@catalog_bp.route("/oggetti/<int:item_id>/elimina", methods=["POST"])
@login_required
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    # Un oggetto ancora ATTIVO (non archiviato) e presente in dei viaggi
    # resta protetto: va prima archiviato — la conferma di eliminazione,
    # in quel caso, arriva sempre da "Vedi archiviati" / dalla pagina
    # dettaglio di un oggetto già archiviato. Un oggetto ARCHIVIATO,
    # invece, può essere eliminato definitivamente anche se compare
    # ancora in dei viaggi passati: la cascata su Item.trip_items se ne
    # occupa (cascade="all, delete-orphan" in models.py), rimuovendo
    # anche quelle righe — è la richiesta esplicita di "svuotare"
    # davvero il catalogo archiviato, non solo nasconderlo.
    if item.trip_items and not item.archived:
        flash(
            f'Non puoi eliminare definitivamente "{item.name}": è presente in '
            f"{len(item.trip_items)} viaggi. Archivialo per poterlo eliminare definitivamente.",
            "error",
        )
        return redirect(url_for("catalog.item_detail", item_id=item.id))

    if item.has_photo:
        old = _existing_photo_path(f"item_{item.id}")
        if old:
            old.unlink(missing_ok=True)
    for v in item.variants:
        if v.has_photo:
            old = _existing_photo_path(f"variant_{v.id}")
            if old:
                old.unlink(missing_ok=True)

    db.session.delete(item)
    db.session.commit()
    flash(f'Oggetto "{item.name}" eliminato definitivamente.', "success")
    # Torna a dove si veniva — tipicamente la lista "Archiviati" da cui
    # si è appena eliminato l'oggetto — non sempre al catalogo attivo.
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.items"))


# ---------------------------------------------------------------------------
# Foto di un oggetto o di un modello (caricata dal telefono o dalla
# libreria foto — vedi templates/catalog/item_form.html e
# _item_variant_row.html per i moduli di caricamento).
# ---------------------------------------------------------------------------

_ALLOWED_PHOTO_EXTENSIONS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "heic": "heic"}


def _item_photos_dir():
    from app.config import DATA_DIR
    d = DATA_DIR / "item-photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _existing_photo_path(prefix: str):
    """Trova il file già caricato per questo prefisso (es. "item_12"), qualunque sia l'estensione."""
    for f in _item_photos_dir().glob(f"{prefix}.*"):
        return f
    return None


def _save_uploaded_photo(uploaded, prefix: str) -> bool:
    """
    Convalida e salva una foto caricata, rimuovendo prima quella
    precedente per lo stesso prefisso (se esiste, qualunque estensione
    avesse). Ritorna True se salvata, False se il file non era valido
    (in quel caso ha già impostato un messaggio flash con il motivo).
    """
    if not uploaded or not uploaded.filename:
        flash("Seleziona una foto da caricare.", "error")
        return False
    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in _ALLOWED_PHOTO_EXTENSIONS:
        flash("Formato non supportato: usa JPG, PNG, WEBP o HEIC.", "error")
        return False
    uploaded.seek(0, 2)
    size = uploaded.tell()
    uploaded.seek(0)
    if size > 10 * 1024 * 1024:
        flash("Foto troppo grande (massimo 10 MB).", "error")
        return False

    old = _existing_photo_path(prefix)
    if old:
        old.unlink(missing_ok=True)
    uploaded.save(_item_photos_dir() / f"{prefix}.{ext}")
    return True


@catalog_bp.route("/oggetti/<int:item_id>/foto/carica", methods=["POST"])
@login_required
def upload_item_photo(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    if _save_uploaded_photo(request.files.get("photo_file"), f"item_{item.id}"):
        item.has_photo = True
        db.session.commit()
        flash("Foto caricata.", "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/foto/rimuovi", methods=["POST"])
@login_required
def remove_item_photo(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    old = _existing_photo_path(f"item_{item.id}")
    if old:
        old.unlink(missing_ok=True)
    item.has_photo = False
    db.session.commit()
    flash("Foto rimossa.", "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/foto")
@login_required
def item_photo_file(item_id):
    """
    Serve il file per QUALUNQUE utente possa vedere questo oggetto in
    un contesto legittimo (non solo il proprietario del catalogo): un
    collaboratore in un viaggio condiviso vede gli oggetti dell'altro
    nella stessa lista, quindi deve poter vedere anche le loro foto.
    """
    from flask import send_file, abort

    item = Item.query.get_or_404(item_id)
    path = _existing_photo_path(f"item_{item.id}")
    if path is None:
        abort(404)
    return send_file(path)


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/foto/carica", methods=["POST"])
@login_required
def upload_variant_photo(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    if _save_uploaded_photo(request.files.get("photo_file"), f"variant_{variant.id}"):
        variant.has_photo = True
        db.session.commit()
        flash("Foto caricata.", "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/foto/rimuovi", methods=["POST"])
@login_required
def remove_variant_photo(item_id, variant_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item.id).first_or_404()
    old = _existing_photo_path(f"variant_{variant.id}")
    if old:
        old.unlink(missing_ok=True)
    variant.has_photo = False
    db.session.commit()
    flash("Foto rimossa.", "success")
    return redirect(_safe_internal_redirect_target(request.referrer) or url_for("catalog.item_detail", item_id=item.id))


@catalog_bp.route("/oggetti/<int:item_id>/modelli/<int:variant_id>/foto")
@login_required
def variant_photo_file(item_id, variant_id):
    from flask import send_file, abort

    variant = ItemVariant.query.filter_by(id=variant_id, item_id=item_id).first_or_404()
    path = _existing_photo_path(f"variant_{variant.id}")
    if path is None:
        abort(404)
    return send_file(path)
