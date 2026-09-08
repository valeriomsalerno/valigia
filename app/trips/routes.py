"""
trips/routes.py
================
Creazione e gestione dei viaggi, incluso il "workspace" di ogni viaggio
(`/viaggi/<id>`): la schermata con la carta d'imbarco, il pannello
Valigia (personale) e il pannello Lista della spesa (condivisa, divisa
per acquirente).

Permessi, in breve (vedi anche app/access.py e models.py):
  - meta/date/note, condivisione, eliminazione: solo il proprietario;
  - valigie attive nel viaggio: ciascun collaboratore gestisce le PROPRIE
    (nessuna relazione con l'essere proprietario del viaggio);
  - lista da mettere in valigia: personale, ogni collaboratore vede e
    modifica solo le proprie righe;
  - lista della spesa: condivisa in lettura tra i collaboratori, con le
    singole voci comunque modificabili solo da chi le ha inserite (puoi
    però riassegnare l'acquisto a un altro collaboratore).
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Trip, TripLuggage, Luggage, Item, Category, TripItem, TripShare, User, LuggageType
from app.forms import TripForm, ShareTripForm
from app.access import get_accessible_trip_or_403
from app.utils import (
    sync_trip_items, ensure_default_trip_luggages, recompute_automatic_quantities,
    trip_stats, accessible_trips_query, fetch_trip_cover_image, trip_shopping_summary,
    user_trip_luggages, luggage_display_labels,
)

trips_bp = Blueprint("trips", __name__, url_prefix="/viaggi", template_folder="../templates/trips")


def _owner_required(trip: Trip):
    if trip.owner_id != current_user.id:
        abort(403)


def _populate_copy_choices(form: TripForm) -> None:
    trips = Trip.query.filter_by(owner_id=current_user.id).order_by(Trip.start_date.desc()).all()
    form.copy_from_trip_id.choices = [(0, "— Non copiare, parti da zero —")] + [
        (t.id, f"{t.destination} ({t.start_date.strftime('%d/%m/%Y')})") for t in trips
    ]


@trips_bp.route("/")
@login_required
def list_trips():
    all_trips = accessible_trips_query(current_user).order_by(Trip.start_date.desc()).all()
    trips_with_stats = [(t, trip_stats(t, current_user)) for t in all_trips]
    return render_template("trips/list.html", trips_with_stats=trips_with_stats)


@trips_bp.route("/nuovo", methods=["GET", "POST"])
@login_required
def new():
    form = TripForm()
    _populate_copy_choices(form)

    if form.validate_on_submit():
        trip = Trip(
            owner_id=current_user.id,
            destination=form.destination.data.strip(),
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            notes=(form.notes.data or "").strip(),
            cover_search_terms=(form.cover_search_terms.data or "").strip() or None,
        )
        db.session.add(trip)
        db.session.commit()

        try:
            trip.cover_image_url = fetch_trip_cover_image(trip.destination, trip.cover_search_terms)
            db.session.commit()
        except Exception:
            db.session.rollback()

        ensure_default_trip_luggages(trip, current_user)

        copy_from_id = form.copy_from_trip_id.data or 0
        copy_from_trip = db.session.get(Trip, copy_from_id) if copy_from_id else None
        sync_trip_items(trip, current_user, copy_from_trip=copy_from_trip)

        flash(f'Viaggio "{trip.destination}" creato! Buona preparazione della valigia.', "success")
        return redirect(url_for("trips.workspace", trip_id=trip.id))

    has_trips = Trip.query.filter_by(owner_id=current_user.id).count() > 0
    return render_template("trips/form.html", form=form, trip=None, has_trips=has_trips)


@trips_bp.route("/<int:trip_id>")
@login_required
def workspace(trip_id):
    """Il workspace del viaggio: carta d'imbarco + pannelli Valigia / Lista della spesa."""
    trip = get_accessible_trip_or_403(trip_id)

    ensure_default_trip_luggages(trip, current_user)
    sync_trip_items(trip, current_user)

    search = request.args.get("q", "").strip()
    category_id = request.args.get("categoria", type=int)
    status_filter = request.args.get("stato", "")

    query = (
        TripItem.query.filter_by(trip_id=trip.id, user_id=current_user.id)
        .join(Item)
        .join(Category)
    )
    if search:
        query = query.filter(Item.name.ilike(f"%{search}%"))
    if category_id:
        query = query.filter(Item.category_id == category_id)

    trip_items = query.all()
    if status_filter:
        trip_items = [ti for ti in trip_items if ti.status == status_filter]

    categories = (
        Category.query.filter_by(owner_id=current_user.id)
        .order_by(Category.sort_order, Category.name).all()
    )
    grouped = []
    for cat in categories:
        cat_items = sorted(
            [ti for ti in trip_items if ti.item.category_id == cat.id],
            key=lambda ti: (ti.sort_order, ti.item.name.lower()),
        )
        if cat_items:
            grouped.append({"category": cat, "trip_items": cat_items})

    my_luggages = user_trip_luggages(trip, current_user)

    return render_template(
        "trips/workspace.html",
        trip=trip,
        is_owner=(trip.owner_id == current_user.id),
        grouped=grouped,
        my_luggages=my_luggages,
        luggage_labels=luggage_display_labels(my_luggages),
        stats=trip_stats(trip, current_user),
        categories=categories,
        search=search,
        category_id=category_id,
        status_filter=status_filter,
        shopping_summary=trip_shopping_summary(trip),
    )


@trips_bp.route("/<int:trip_id>/spesa-frammento")
@login_required
def shopping_panel_fragment(trip_id):
    """
    Ricalcola e ritorna solo il markup del pannello "Lista della spesa",
    per l'aggiornamento istantaneo via JS (senza ricaricare l'intera
    pagina) quando qualcosa passa "da comprare" o viene acquistato.
    """
    trip = get_accessible_trip_or_403(trip_id)
    return render_template("trips/_shopping_panel.html", trip=trip, shopping_summary=trip_shopping_summary(trip))


@trips_bp.route("/<int:trip_id>/stats-live")
@login_required
def stats_live(trip_id):
    """
    Solo le statistiche (quantità/peso per valigia, conteggi di stato),
    per l'aggiornamento periodico via JS del workspace: serve soprattutto
    per le valigie CONDIVISE, il cui contenuto può cambiare per mano di
    un altro collaboratore senza che il proprio browser abbia modo di
    saperlo altrimenti (nessuna azione propria che lo faccia scattare).
    """
    trip = get_accessible_trip_or_403(trip_id)
    return jsonify({"ok": True, "stats": trip_stats(trip, current_user)})


@trips_bp.route("/<int:trip_id>/modifica", methods=["GET", "POST"])
@login_required
def edit(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    _owner_required(trip)

    form = TripForm(obj=trip)
    _populate_copy_choices(form)

    if form.validate_on_submit():
        old_days = trip.days
        destination_changed = trip.destination != form.destination.data.strip()
        terms_changed = (trip.cover_search_terms or "") != (form.cover_search_terms.data or "").strip()

        trip.destination = form.destination.data.strip()
        trip.start_date = form.start_date.data
        trip.end_date = form.end_date.data
        trip.notes = (form.notes.data or "").strip()
        trip.cover_search_terms = (form.cover_search_terms.data or "").strip() or None
        db.session.commit()

        # Non tocca una copertina caricata a mano dall'utente: la ricerca
        # automatica riparte solo se la destinazione o i termini di
        # ricerca cambiano, e solo se l'immagine attuale non è un upload.
        if (destination_changed or terms_changed) and not trip.cover_image_is_upload:
            try:
                trip.cover_image_url = fetch_trip_cover_image(trip.destination, trip.cover_search_terms)
                db.session.commit()
            except Exception:
                db.session.rollback()

        if trip.days != old_days:
            for collaborator in trip.collaborators():
                updated = recompute_automatic_quantities(trip, collaborator)
                if updated and collaborator.id == current_user.id:
                    flash(
                        f"Le date sono cambiate: {updated} tuoi oggetti con quantità automatica "
                        "sono stati ricalcolati (lo stesso vale per gli altri collaboratori).",
                        "info",
                    )

        flash(f'Viaggio "{trip.destination}" aggiornato.', "success")
        return redirect(url_for("trips.workspace", trip_id=trip.id))

    return render_template("trips/form.html", form=form, trip=trip, has_trips=True)


@trips_bp.route("/<int:trip_id>/aggiorna-copertina", methods=["POST"])
@login_required
def refresh_cover(trip_id):
    """
    Cerca (o ricerca) un'immagine di copertina, usando i valori di meta e
    termini di ricerca INVIATI nella richiesta — NON quelli già salvati
    sul viaggio — così funziona subito con quanto scritto nel modulo,
    senza dover prima cliccare "Salva viaggio" (bug reale corretto: la
    ricerca usava sempre l'ultimo valore salvato, ignorando le modifiche
    non ancora salvate — vedi CHANGELOG). Risponde in JSON per
    aggiornare l'anteprima all'istante, senza ricaricare la pagina;
    salva comunque subito anche destinazione e termini di ricerca usati,
    così restano coerenti con l'immagine trovata anche prima di un
    salvataggio esplicito del resto del modulo.
    """
    trip = get_accessible_trip_or_403(trip_id)
    if trip.owner_id != current_user.id:
        return jsonify({"ok": False, "error": "Solo il proprietario del viaggio può farlo."}), 403

    data = request.get_json(silent=True) or {}
    destination = (data.get("destination") or trip.destination or "").strip()
    search_terms = (data.get("search_terms") or "").strip() or None

    if not destination:
        return jsonify({"ok": False, "error": "Manca la meta del viaggio."}), 400

    try:
        image_url = fetch_trip_cover_image(destination, search_terms)
    except Exception:
        image_url = None

    trip.cover_search_terms = search_terms
    trip.cover_image_url = image_url
    trip.cover_image_is_upload = False
    trip.cover_image_position = "50% 50%"
    _delete_uploaded_cover_file(trip)
    db.session.commit()

    return jsonify({
        "ok": True,
        "found": image_url is not None,
        "image_url": image_url,
        "position": trip.cover_image_position,
    })


def _cover_uploads_dir():
    from app.config import DATA_DIR
    d = DATA_DIR / "cover-uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _delete_uploaded_cover_file(trip):
    """Rimuove il file caricato in precedenza per questo viaggio, se esiste (es. prima di sostituirlo o tornare all'automatica)."""
    d = _cover_uploads_dir()
    for f in d.glob(f"trip_{trip.id}.*"):
        f.unlink(missing_ok=True)


_ALLOWED_COVER_EXTENSIONS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}


@trips_bp.route("/<int:trip_id>/copertina/carica", methods=["POST"])
@login_required
def upload_cover(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    _owner_required(trip)

    uploaded = request.files.get("cover_file")
    if not uploaded or not uploaded.filename:
        flash("Seleziona un'immagine da caricare.", "error")
        return redirect(url_for("trips.edit", trip_id=trip.id))

    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in _ALLOWED_COVER_EXTENSIONS:
        flash("Formato non supportato: usa JPG, PNG o WEBP.", "error")
        return redirect(url_for("trips.edit", trip_id=trip.id))

    uploaded.seek(0, 2)
    size = uploaded.tell()
    uploaded.seek(0)
    if size > 8 * 1024 * 1024:
        flash("Immagine troppo grande (massimo 8 MB).", "error")
        return redirect(url_for("trips.edit", trip_id=trip.id))

    _delete_uploaded_cover_file(trip)
    dest = _cover_uploads_dir() / f"trip_{trip.id}.{ext}"
    uploaded.save(dest)

    trip.cover_image_url = url_for("trips.cover_image_file", trip_id=trip.id)
    trip.cover_image_is_upload = True
    trip.cover_image_position = "50% 50%"
    db.session.commit()

    flash("Immagine caricata. Trascinala nel riquadro del viaggio per inquadrarla come preferisci.", "success")
    return redirect(url_for("trips.edit", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/copertina/file")
@login_required
def cover_image_file(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    d = _cover_uploads_dir()
    matches = list(d.glob(f"trip_{trip.id}.*"))
    if not matches:
        abort(404)
    return send_file(matches[0])


@trips_bp.route("/<int:trip_id>/copertina/posizione", methods=["POST"])
@login_required
def update_cover_position(trip_id):
    """Salva la posizione (CSS background-position) scelta trascinando l'immagine di copertina caricata a mano."""
    trip = get_accessible_trip_or_403(trip_id)
    if trip.owner_id != current_user.id:
        return jsonify({"ok": False}), 403

    data = request.get_json(silent=True) or {}
    try:
        x = max(0.0, min(100.0, float(data.get("x"))))
        y = max(0.0, min(100.0, float(data.get("y"))))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Posizione non valida."}), 400

    trip.cover_image_position = f"{x:.1f}% {y:.1f}%"
    db.session.commit()
    return jsonify({"ok": True, "position": trip.cover_image_position})


@trips_bp.route("/<int:trip_id>/elimina", methods=["POST"])
@login_required
def delete(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    _owner_required(trip)

    nome = trip.destination
    _delete_uploaded_cover_file(trip)
    db.session.delete(trip)
    db.session.commit()
    flash(f'Viaggio "{nome}" eliminato.', "success")
    return redirect(url_for("trips.list_trips"))


@trips_bp.route("/<int:trip_id>/ricalcola", methods=["POST"])
@login_required
def recompute(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    updated = recompute_automatic_quantities(trip, current_user)
    flash(
        f"{updated} tuoi oggetti ricalcolati in base ai giorni di viaggio." if updated
        else "Le tue quantità automatiche sono già aggiornate.",
        "success" if updated else "info",
    )
    return redirect(url_for("trips.workspace", trip_id=trip.id))


# ---------------------------------------------------------------------------
# Condivisione di un viaggio con altri utenti
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:trip_id>/condividi", methods=["GET", "POST"])
@login_required
def manage_sharing(trip_id):
    trip = get_accessible_trip_or_403(trip_id)
    _owner_required(trip)

    form = ShareTripForm()
    already_shared_ids = {s.user_id for s in trip.shares}
    shareable_users = User.query.filter(
        User.id != current_user.id, User.active.is_(True)
    ).order_by(User.username).all()
    form.user_id.choices = [
        (u.id, u.display_name) for u in shareable_users if u.id not in already_shared_ids
    ]

    if request.method == "POST" and form.user_id.choices and form.validate_on_submit():
        db.session.add(TripShare(trip_id=trip.id, user_id=form.user_id.data))
        db.session.commit()
        flash("Viaggio condiviso.", "success")
        return redirect(url_for("trips.manage_sharing", trip_id=trip.id))

    return render_template("trips/sharing.html", trip=trip, form=form)


@trips_bp.route("/<int:trip_id>/condividi/<int:share_id>/rimuovi", methods=["POST"])
@login_required
def remove_sharing(trip_id, share_id):
    trip = get_accessible_trip_or_403(trip_id)
    _owner_required(trip)

    share = TripShare.query.filter_by(id=share_id, trip_id=trip.id).first_or_404()
    db.session.delete(share)
    db.session.commit()
    flash("Condivisione rimossa.", "success")
    return redirect(url_for("trips.manage_sharing", trip_id=trip.id))


# ---------------------------------------------------------------------------
# Valigie attive nel viaggio — PERSONALI: ogni collaboratore gestisce le proprie
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:trip_id>/valigie", methods=["GET", "POST"])
@login_required
def manage_luggage(trip_id):
    trip = get_accessible_trip_or_403(trip_id)

    if request.method == "POST":
        luggage_id = request.form.get("luggage_id", type=int)
        luggage = Luggage.query.filter_by(id=luggage_id, owner_id=current_user.id).first_or_404()

        already_active = any(
            tl.luggage_id == luggage_id and tl.user_id == current_user.id for tl in trip.trip_luggages
        )
        if already_active:
            flash(f'"{luggage.display_name}" è già attiva per questo viaggio.', "info")
        else:
            my_count = sum(1 for tl in trip.trip_luggages if tl.user_id == current_user.id)
            new_tl = TripLuggage(trip_id=trip.id, luggage_id=luggage.id, user_id=current_user.id, sort_order=my_count)
            db.session.add(new_tl)
            db.session.commit()

            from app.models import TripItemQty
            my_items = TripItem.query.filter_by(trip_id=trip.id, user_id=current_user.id).all()
            for ti in my_items:
                db.session.add(TripItemQty(trip_item_id=ti.id, trip_luggage_id=new_tl.id, quantity=0))
            db.session.commit()
            flash(f'"{luggage.display_name}" aggiunta a questo viaggio.', "success")
        return redirect(url_for("trips.manage_luggage", trip_id=trip.id))

    my_active = [tl for tl in trip.trip_luggages if tl.user_id == current_user.id and tl.luggage is not None]
    my_active.sort(key=lambda tl: (LuggageType.sort_key(tl.luggage.tipologia), tl.sort_order))
    my_active_luggage_ids = {tl.luggage_id for tl in my_active}
    my_available_luggage = (
        Luggage.query.filter_by(owner_id=current_user.id)
        .order_by(Luggage.brand, Luggage.name).all()
    )

    # Valigie di ALTRI collaboratori condivise con me: mostrate qui in sola
    # lettura, per trasparenza (spiega perché nel workspace compaiono
    # steppers in più oltre alle proprie valigie).
    shared_with_me = [
        tl for tl in trip.trip_luggages
        if tl.luggage is not None and tl.user_id != current_user.id and current_user.id in tl.shared_with_user_ids()
    ]

    other_collaborators = [u for u in trip.collaborators() if u.id != current_user.id]

    return render_template(
        "trips/luggage.html", trip=trip, my_active=my_active,
        my_available_luggage=my_available_luggage, my_active_luggage_ids=my_active_luggage_ids,
        shared_with_me=shared_with_me, other_collaborators=other_collaborators,
    )


@trips_bp.route("/<int:trip_id>/valigie/<int:trip_luggage_id>/condividi", methods=["POST"])
@login_required
def share_trip_luggage(trip_id, trip_luggage_id):
    """
    Sostituisce l'intero insieme di collaboratori con cui questa valigia
    è condivisa (solo il proprietario può farlo). Chi riceve la
    condivisione può mettere le PROPRIE cose in questa valigia, anche
    oggetti che il proprietario della valigia non ha nel suo catalogo.
    """
    trip = get_accessible_trip_or_403(trip_id)
    tl = TripLuggage.query.get_or_404(trip_luggage_id)
    if tl.trip_id != trip.id or tl.user_id != current_user.id:
        abort(403)

    from app.models import TripLuggageShare

    valid_collaborator_ids = {u.id for u in trip.collaborators() if u.id != current_user.id}
    selected_ids = {int(x) for x in request.form.getlist("shared_with") if x.isdigit()} & valid_collaborator_ids

    TripLuggageShare.query.filter_by(trip_luggage_id=tl.id).delete()
    for uid in selected_ids:
        db.session.add(TripLuggageShare(trip_luggage_id=tl.id, shared_with_user_id=uid))
    db.session.commit()

    flash(f'Condivisione di "{tl.luggage.display_name}" aggiornata.', "success")
    return redirect(url_for("trips.manage_luggage", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/valigie/<int:trip_luggage_id>/rimuovi", methods=["POST"])
@login_required
def remove_trip_luggage(trip_id, trip_luggage_id):
    trip = get_accessible_trip_or_403(trip_id)
    tl = TripLuggage.query.get_or_404(trip_luggage_id)
    if tl.trip_id != trip.id or tl.user_id != current_user.id:
        abort(403)

    my_count = sum(1 for x in trip.trip_luggages if x.user_id == current_user.id)
    if my_count <= 1:
        flash("Deve rimanere almeno una tua valigia attiva per il viaggio.", "error")
        return redirect(url_for("trips.manage_luggage", trip_id=trip.id))

    db.session.delete(tl)
    db.session.commit()
    flash("Valigia rimossa da questo viaggio.", "success")
    return redirect(url_for("trips.manage_luggage", trip_id=trip.id))


# ---------------------------------------------------------------------------
# Lista della spesa condivisa
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:trip_id>/spesa/<int:trip_item_id>/acquistato", methods=["POST"])
@login_required
def mark_purchased(trip_id, trip_item_id):
    trip = get_accessible_trip_or_403(trip_id)
    trip_item = TripItem.query.filter_by(id=trip_item_id, trip_id=trip.id).first_or_404()

    trip_item.missing_qty = 0
    db.session.commit()
    flash(f'"{trip_item.item.name}" tolto dalla lista della spesa.', "success")
    return redirect(url_for("trips.workspace", trip_id=trip.id) + "#spesa")


@trips_bp.route("/<int:trip_id>/dettaglio/<int:trip_item_id>")
@login_required
def item_detail_panel(trip_id, trip_item_id):
    trip = get_accessible_trip_or_403(trip_id)
    trip_item = TripItem.query.filter_by(id=trip_item_id, trip_id=trip.id).first_or_404()
    if trip_item.user_id != current_user.id:
        abort(403)

    from app.utils import compute_auto_quantity
    from app.models import QuantityRule

    item = trip_item.item
    auto_info = None
    if item.quantity_rule == QuantityRule.FIXED:
        auto_info = f"Quantità fissa: sempre {item.fixed_qty}."
    elif item.quantity_rule == QuantityRule.PER_DAY:
        suggerita = compute_auto_quantity(item, trip)
        auto_info = (
            f"Calcolata sui giorni di viaggio: {trip.days} giorni + "
            f"{item.per_day_extra} di scorta = {suggerita}."
        )

    history = (
        TripItem.query.filter(TripItem.item_id == item.id, TripItem.trip_id != trip.id, TripItem.user_id == current_user.id)
        .join(Trip)
        .order_by(Trip.start_date.desc())
        .limit(5)
        .all()
    )
    collaborators = [u for u in trip.collaborators() if u.id != current_user.id]

    return render_template(
        "trips/_item_detail_panel.html",
        trip_item=trip_item, item=item, trip=trip, auto_info=auto_info,
        history=history, collaborators=collaborators,
    )


@trips_bp.route("/<int:trip_id>/oggetti/<int:trip_item_id>/reset", methods=["POST"])
@login_required
def reset_trip_item(trip_id, trip_item_id):
    """
    Azzera TUTTO ciò che riguarda "quanto è pronto" per questo oggetto,
    in questo viaggio: quantità per valigia, quantità per modello (in
    OGNI valigia), e indossato — mai l'obiettivo né "da comprare", che
    restano impostazioni intenzionali dell'utente, non dati "da
    riempire". Pensato come rimedio pratico contro eventuali residui
    inconsistenti (es. da bug ormai corretti ma i cui effetti erano già
    stati salvati) — più semplice ed affidabile che inseguire la causa
    esatta di un singolo caso: si riparte da zero per quell'oggetto.
    """
    trip = get_accessible_trip_or_403(trip_id)
    trip_item = TripItem.query.filter_by(id=trip_item_id, trip_id=trip.id).first_or_404()
    if trip_item.user_id != current_user.id:
        abort(403)

    for q in list(trip_item.quantities):
        db.session.delete(q)
    for vq in list(trip_item.variant_quantities):
        db.session.delete(vq)
    trip_item.indossato_qty = 0
    db.session.commit()

    flash(f'"{trip_item.item.name}" azzerato per questo viaggio (obiettivo e "da comprare" invariati).', "success")
    return redirect(url_for("trips.workspace", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/reset-tutti-oggetti", methods=["POST"])
@login_required
def reset_all_trip_items(trip_id):
    """Come reset_trip_item, ma per TUTTI gli oggetti del viaggio (solo i propri, non quelli di altri collaboratori)."""
    trip = get_accessible_trip_or_403(trip_id)
    my_items = TripItem.query.filter_by(trip_id=trip.id, user_id=current_user.id).all()

    count = 0
    for trip_item in my_items:
        changed = bool(trip_item.quantities) or bool(trip_item.variant_quantities) or trip_item.indossato_qty
        for q in list(trip_item.quantities):
            db.session.delete(q)
        for vq in list(trip_item.variant_quantities):
            db.session.delete(vq)
        trip_item.indossato_qty = 0
        if changed:
            count += 1
    db.session.commit()

    flash(f'{count} oggetti azzerati per questo viaggio (obiettivi e "da comprare" invariati).', "success")
    return redirect(url_for("trips.edit", trip_id=trip.id))
