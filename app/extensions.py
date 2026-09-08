"""
extensions.py
=============
Istanze delle estensioni Flask create qui (senza `app`) per evitare import
circolari: ogni modulo può importare `db`, `login_manager`, ecc. da qui,
mentre l'inizializzazione vera e propria (`db.init_app(app)`) avviene in
`app/__init__.py` dentro la funzione `create_app()`.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

# ORM per l'accesso al database (SQLite)
db = SQLAlchemy()

# Gestione della sessione utente (login/logout, "utente corrente")
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Effettua l'accesso per continuare."
login_manager.login_message_category = "info"

# Protezione CSRF su tutti i form POST/PATCH/DELETE
csrf = CSRFProtect()
