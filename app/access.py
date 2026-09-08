"""
access.py
=========
Helper di controllo accessi condivisi tra più blueprint. Tenuti in un
modulo a parte (invece che dentro auth/ o trips/) per evitare import
circolari, dato che sono usati da auth, users, trips e dashboard.
"""

from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(view_func):
    """
    Decoratore da usare DOPO @login_required: restituisce 403 se
    l'utente autenticato non è un amministratore. Usato dalla sezione
    "Utenti", raggiungibile solo dall'admin.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper


def get_accessible_trip_or_403(trip_id: int):
    """
    Recupera un Trip verificando che l'utente corrente possa accedervi
    (proprietario o condiviso — vedi Trip.is_accessible_by). Solleva 404
    se il viaggio non esiste, 403 se esiste ma non è accessibile
    all'utente corrente (così non si rivela nemmeno l'esistenza del
    viaggio altrui).
    """
    from app.models import Trip

    trip = Trip.query.get_or_404(trip_id)
    if not trip.is_accessible_by(current_user):
        abort(403)
    return trip
