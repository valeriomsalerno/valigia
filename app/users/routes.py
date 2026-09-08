"""
users/routes.py
================
Gestione utenti. La creazione, l'attivazione/disattivazione e il reset
password restano riservate all'amministratore. La modifica di nome
completo e nickname è invece raggiungibile sia dall'amministratore (per
qualunque utente, se stesso incluso) sia da ciascun utente per il
proprio profilo (link "Profilo" nel menu utente).
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, UserRole
from app.forms import NewUserForm, EditUserForm
from app.access import admin_required
from app.utils import provision_new_user_defaults

users_bp = Blueprint("users", __name__, url_prefix="/utenti", template_folder="../templates/users")


@users_bp.route("/")
@login_required
@admin_required
def list_users():
    all_users = User.query.order_by(User.created_at).all()
    return render_template("users/list.html", users=all_users)


@users_bp.route("/nuovo", methods=["GET", "POST"])
@login_required
@admin_required
def new_user():
    form = NewUserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash(f'Esiste già un utente "{username}".', "error")
        else:
            user = User(
                username=username,
                full_name=(form.full_name.data or "").strip(),
                role=form.role.data,
                must_change_password=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            provision_new_user_defaults(user)

            flash(
                f'Utente "{username}" creato con il proprio catalogo personale '
                "(precaricato dal catalogo di base). Comunicagli le credenziali: "
                "dovrà cambiare la password al primo accesso.",
                "success",
            )
            return redirect(url_for("users.list_users"))

    return render_template("users/form.html", form=form)


@users_bp.route("/<int:user_id>/modifica", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    """Modifica nome completo e nickname: consentita all'admin per chiunque, o a chiunque per sé stesso."""
    if user_id != current_user.id and not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        new_username = form.username.data.strip()
        clash = User.query.filter(User.username == new_username, User.id != user.id).first()
        if clash:
            flash(f'Esiste già un utente "{new_username}".', "error")
        else:
            user.username = new_username
            user.full_name = (form.full_name.data or "").strip()
            db.session.commit()
            flash("Profilo aggiornato.", "success")
            return redirect(url_for("users.list_users") if current_user.is_admin and user_id != current_user.id
                             else url_for("dashboard.index"))

    return render_template("users/edit.html", form=form, edited_user=user)


@users_bp.route("/<int:user_id>/attiva-disattiva", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Non puoi disattivare te stesso.", "error")
        return redirect(url_for("users.list_users"))

    user.active = not user.active
    db.session.commit()
    flash(f'Utente "{user.username}" {"riattivato" if user.active else "disattivato"}.', "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 4:
        flash("La nuova password deve avere almeno 4 caratteri.", "error")
        return redirect(url_for("users.list_users"))

    user.set_password(new_password)
    user.must_change_password = True
    db.session.commit()
    flash(f'Password di "{user.username}" reimpostata: dovrà cambiarla al prossimo accesso.', "success")
    return redirect(url_for("users.list_users"))
