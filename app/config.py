"""
config.py
=========
Configurazione centralizzata dell'applicazione "Valigia".

Tutti i valori "sensibili" o dipendenti dall'ambiente (chiave segreta,
percorso del database, credenziali iniziali dell'admin) vengono letti da
variabili d'ambiente, con dei valori di default sensati per lo sviluppo
locale. In produzione (Docker) questi valori vanno impostati tramite il
file `.env` (vedi `.env.example`).
"""

import os
from datetime import timedelta
from pathlib import Path

# Cartella radice del progetto (un livello sopra la cartella app/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Cartella dove viene salvato il database SQLite e altri dati persistenti.
# In Docker questa cartella viene montata come volume, così i dati
# sopravvivono ai riavvii/aggiornamenti del container.
DATA_DIR = Path(os.environ.get("VALIGIA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Configurazione base, condivisa da tutti gli ambienti."""

    # Chiave usata da Flask per firmare i cookie di sessione e i token CSRF.
    # In produzione DEVE essere impostata tramite variabile d'ambiente.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-chiave-non-sicura-cambiami")

    # Percorso del database SQLite (di default dentro la cartella data/).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'valigia.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Credenziali dell'utente amministratore creato al primo avvio.
    # Vengono usate SOLO se nel database non esiste ancora nessun utente.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

    # Numero di "cambi extra" di default per gli oggetti con regola
    # "per giorno" (es. mutande/calzini): giorni_viaggio + questo valore.
    DEFAULT_PER_DAY_EXTRA = 1

    # Durata della sessione: app ad uso familiare/domestico, non serve
    # dover rifare il login di continuo (bug reale corretto: la chiave
    # usata prima, REMEMBER_COOKIE_DURATION_DAYS, non è quella che
    # Flask-Login legge davvero — non aveva mai avuto alcun effetto; la
    # sessione "normale", senza permanent=True, dura solo finché il
    # browser non la scarta, il che su iOS può succedere in fretta).
    # Login sempre "ricordato": vedi auth/routes.py::login.
    REMEMBER_COOKIE_DURATION = timedelta(days=180)
    PERMANENT_SESSION_LIFETIME = timedelta(days=180)

    # Nome del cookie di sessione (personalizzato per evitare conflitti se
    # sulla stessa macchina girano altre app Flask dietro Cloudflare Tunnel)
    SESSION_COOKIE_NAME = "valigia_session"

    # Applicazione installabile su iOS/iPadOS come Web App (PWA-like)
    APP_NAME = "Valigia"

    # Versione corrente, mostrata in fondo a ogni pagina e nella pagina di
    # login: serve a verificare a colpo d'occhio, da browser, se il
    # container in esecuzione è stato davvero aggiornato all'ultima build
    # (senza dover controllare log o entrare in SSH). Va aggiornata ad
    # ogni release insieme a CHANGELOG.md — vedi CONTEXT.md, sezione 9.
    APP_VERSION = "3.6.7"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # Dietro Cloudflare Tunnel il traffico è HTTPS end-to-end fino al
    # container solo se configurato: per sicurezza lasciamo i cookie
    # "Secure" disattivabili tramite variabile d'ambiente, dato che il
    # tunnel Cloudflare termina normalmente il TLS lui stesso.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Mappa usata da create_app() per scegliere la configurazione in base a
# FLASK_ENV / VALIGIA_ENV
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
