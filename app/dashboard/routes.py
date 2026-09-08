"""
dashboard/routes.py
====================
La NUOVA schermata iniziale ("/"): non è più la lista di un singolo
viaggio (quella ora vive nel "workspace" di ogni viaggio, vedi
app/trips/routes.py::workspace), ma una panoramica a blocchi:

    ┌──────────────────────────────────────────────┐
    │  Viaggi futuri (largo)                        │
    ├──────────────────────┬─────────────────────────┤
    │  Catalogo (metà)      │  Valigie (metà)          │
    ├──────────────────────────────────────────────┤
    │  Viaggi passati (largo)                       │
    └──────────────────────────────────────────────┘

Ogni viaggio ha ora un proprio URL permanente (`/viaggi/<id>`), quindi
qui non serve più tenere in sessione un "viaggio corrente".
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Trip, Category, Item, Luggage
from app.utils import accessible_trips_query, trip_stats, trip_shopping_summary

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    all_trips = accessible_trips_query(current_user).all()

    upcoming = sorted(
        [t for t in all_trips if not t.is_past],
        key=lambda t: t.start_date,
    )
    past = sorted(
        [t for t in all_trips if t.is_past],
        key=lambda t: t.end_date,
        reverse=True,
    )

    upcoming_with_stats = [(t, trip_stats(t, current_user)) for t in upcoming]
    past_with_stats = [(t, trip_stats(t, current_user)) for t in past[:6]]

    catalog_summary = {
        "categorie": Category.query.filter_by(owner_id=current_user.id).count(),
        "oggetti": Item.query.filter_by(owner_id=current_user.id, archived=False).count(),
    }
    luggage_list = Luggage.query.filter_by(owner_id=current_user.id).order_by(Luggage.brand, Luggage.name).all()

    return render_template(
        "dashboard/index.html",
        upcoming_with_stats=upcoming_with_stats,
        past_with_stats=past_with_stats,
        past_total=len(past),
        catalog_summary=catalog_summary,
        luggage_list=luggage_list,
    )


@dashboard_bp.route("/lista-della-spesa")
@login_required
def shopping_index():
    """
    Le liste della spesa di TUTTI i viaggi accessibili, ordinate per
    vicinanza della data di partenza (i viaggi in corso/imminenti prima).
    """
    all_trips = accessible_trips_query(current_user).all()

    def _departure_key(t: Trip):
        # I viaggi futuri/in corso vengono prima (ordinati per partenza più
        # vicina), quelli passati dopo (dal più recente al più vecchio).
        if not t.is_past:
            return (0, t.start_date)
        return (1, -t.start_date.toordinal())

    sorted_trips = sorted(all_trips, key=_departure_key)

    rows = []
    for trip in sorted_trips:
        summary = trip_shopping_summary(trip)
        total_missing = sum(len(s["missing_items"]) for s in summary)
        if total_missing == 0:
            continue
        rows.append({"trip": trip, "summary": summary, "total_missing": total_missing})

    return render_template("dashboard/shopping_index.html", rows=rows)
