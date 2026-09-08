"""
luggage/routes.py
==================
La sezione "Valigie": l'elenco delle borse FISICHE possedute (marca,
nome, tipologia cabina/stiva/zaino, peso a vuoto, capacità in litri). È
l'UNICO catalogo di bagagli dell'app: si scelgono per nome, viaggio per
viaggio, dalla pagina "Valigie" di ciascun viaggio (vedi
trips/routes.py::manage_luggage).
"""

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Luggage, LuggageType
from app.forms import LuggageForm

luggage_bp = Blueprint("luggage", __name__, url_prefix="/valigie", template_folder="../templates/luggage")


@luggage_bp.route("/")
@login_required
def list_luggage():
    items = Luggage.query.filter_by(owner_id=current_user.id).all()
    items = sorted(items, key=lambda l: (LuggageType.sort_key(l.tipologia), l.brand, l.name))
    return render_template("luggage/list.html", items=items)


@luggage_bp.route("/nuova", methods=["GET", "POST"])
@login_required
def new_luggage():
    form = LuggageForm()
    if form.validate_on_submit():
        item = Luggage(
            owner_id=current_user.id,
            brand=(form.brand.data or "").strip(),
            name=form.name.data.strip(),
            tipologia=form.tipologia.data,
            weight_kg=form.weight_kg.data,
            capacity_liters=form.capacity_liters.data,
            is_default_for_new_trip=form.is_default_for_new_trip.data,
            notes=(form.notes.data or "").strip(),
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Valigia "{item.name}" aggiunta.', "success")
        return redirect(url_for("luggage.list_luggage"))

    return render_template("luggage/form.html", form=form, item=None)


@luggage_bp.route("/<int:luggage_id>/modifica", methods=["GET", "POST"])
@login_required
def edit_luggage(luggage_id):
    item = Luggage.query.filter_by(id=luggage_id, owner_id=current_user.id).first_or_404()
    form = LuggageForm(obj=item)

    if form.validate_on_submit():
        item.brand = (form.brand.data or "").strip()
        item.name = form.name.data.strip()
        item.tipologia = form.tipologia.data
        item.weight_kg = form.weight_kg.data
        item.capacity_liters = form.capacity_liters.data
        item.is_default_for_new_trip = form.is_default_for_new_trip.data
        item.notes = (form.notes.data or "").strip()
        db.session.commit()
        flash(f'Valigia "{item.name}" aggiornata.', "success")
        return redirect(url_for("luggage.list_luggage"))

    return render_template("luggage/form.html", form=form, item=item)


@luggage_bp.route("/<int:luggage_id>/elimina", methods=["POST"])
@login_required
def delete_luggage(luggage_id):
    item = Luggage.query.filter_by(id=luggage_id, owner_id=current_user.id).first_or_404()
    trip_count = len(item.trip_luggages)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    if trip_count:
        flash(
            f'Valigia "{name}" eliminata e rimossa automaticamente da {trip_count} '
            "viaggio/i in cui era attiva.", "success",
        )
    else:
        flash(f'Valigia "{name}" eliminata.', "success")
    return redirect(url_for("luggage.list_luggage"))
