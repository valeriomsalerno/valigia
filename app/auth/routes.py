"""
auth/routes.py
===============
Login, logout e cambio password.

Ogni utente ha le proprie credenziali; il primo admin viene creato al
primissimo avvio (vedi app/__init__.py::_ensure_seed_data). Al primo
accesso (o dopo un reset da parte dell'amministratore) l'utente viene
obbligato a cambiare la password prima di poter usare il resto della
piattaforma (flag `must_change_password`).
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.forms import LoginForm, ChangePasswordForm

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        from app.models import User  # import locale per evitare cicli

        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and not user.active:
            flash("Questo utente è stato disattivato. Contatta l'amministratore.", "error")
        elif user and user.check_password(form.password.data):
            # Sessione sempre "lunga" (vedi PERMANENT_SESSION_LIFETIME in
            # config.py), a prescindere dalla spunta "ricordami": è un'app
            # ad uso familiare/domestico, non serve dover rifare il login
            # di continuo. La spunta resta comunque disponibile per chi la
            # preferisce esplicita.
            login_user(user, remember=True)
            session.permanent = True
            if user.must_change_password:
                flash("Per sicurezza, imposta subito una nuova password.", "info")
                return redirect(url_for("auth.change_password"))
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))
        flash("Utente o password non corretti.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Hai effettuato il logout.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("La password attuale non è corretta.", "error")
        else:
            current_user.set_password(form.new_password.data)
            current_user.must_change_password = False
            db.session.commit()
            flash("Password aggiornata con successo.", "success")
            return redirect(url_for("dashboard.index"))

    # Se l'utente è obbligato al cambio password, glielo ricordiamo in UI
    forced = current_user.must_change_password
    return render_template("auth/change_password.html", form=form, forced=forced)
