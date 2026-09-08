"""
tests/test_backup.py
=====================
Verifica che l'esportazione e il ripristino del database funzionino
correttamente: solo l'admin vi accede, il file esportato è un database
valido, il ripristino sostituisce davvero i dati e crea una copia di
sicurezza di quelli precedenti.
"""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "valigia.db"
    monkeypatch.setenv("VALIGIA_DATABASE_URI_OVERRIDE", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-backup-secret")
    return create_app("testing")


def _login_admin(client):
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    client.post(
        "/account/password",
        data={"current_password": "admin", "new_password": "nuovaPass123", "confirm_password": "nuovaPass123"},
        follow_redirects=True,
    )


def test_backup_page_requires_admin(app):
    with app.app_context():
        from app.models import User, UserRole
        from app.extensions import db as _db

        member = User(username="membro", role=UserRole.MEMBER, must_change_password=False)
        member.set_password("password123")
        _db.session.add(member)
        _db.session.commit()

    client = app.test_client()
    client.post("/login", data={"username": "membro", "password": "password123"}, follow_redirects=True)
    resp = client.get("/backup/")
    assert resp.status_code == 403


def test_export_returns_valid_sqlite_file(app):
    client = app.test_client()
    _login_admin(client)

    resp = client.post("/backup/esporta")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")

    # Il contenuto scaricato deve essere un vero database SQLite valido,
    # con dentro l'utente admin appena creato.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        f.write(resp.data)
        f.flush()
        conn = sqlite3.connect(f.name)
        row = conn.execute("SELECT username FROM users WHERE username='admin'").fetchone()
        conn.close()
        assert row is not None


def test_restore_replaces_data_and_creates_safety_copy(app, tmp_path, monkeypatch):
    client = app.test_client()
    _login_admin(client)

    # Costruisce un secondo database v2.1 valido (schema completo) con un
    # utente diverso, usando la stessa create_app puntata su un file a parte.
    other_db_path = tmp_path / "other.db"
    monkeypatch.setenv("VALIGIA_DATABASE_URI_OVERRIDE", f"sqlite:///{other_db_path}")
    other_app = create_app("testing")
    with other_app.app_context():
        from app.models import User
        from app.extensions import db as other_db
        other_admin = User.query.first()
        other_admin.username = "altro_admin"
        other_db.session.commit()
        # Con la modalità WAL attiva, le scritture recenti possono restare
        # nel file -wal finché non c'è un checkpoint: un vero backup
        # esportato dall'app lo fa sempre (vedi backup/routes.py), qui lo
        # forziamo a mano per simulare correttamente un file già esportato.
        other_db.session.execute(other_db.text("PRAGMA wal_checkpoint(FULL)"))

    with open(other_db_path, "rb") as f:
        resp = client.post(
            "/backup/ripristina",
            data={"backup_file": (f, "other.db")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert "ripristinato" in resp.data.decode("utf-8").lower()

    with app.app_context():
        from app.models import User
        assert User.query.filter_by(username="altro_admin").first() is not None
        assert User.query.filter_by(username="admin").first() is None  # sostituito, non unito

    backups_dir = tmp_path / "backups"
    assert any(backups_dir.glob("valigia-*-prima-del-ripristino.db"))


def test_restore_rejects_invalid_file(app, tmp_path):
    client = app.test_client()
    _login_admin(client)

    bad_file = tmp_path / "not_a_db.db"
    bad_file.write_text("questo non è un database sqlite")

    with open(bad_file, "rb") as f:
        resp = client.post(
            "/backup/ripristina",
            data={"backup_file": (f, "not_a_db.db")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert "non sembra un database" in resp.data.decode("utf-8").lower()

    with app.app_context():
        from app.models import User
        assert User.query.filter_by(username="admin").first() is not None


def test_statistics_page_shows_system_resources(app):
    """La pagina Statistiche (CPU/memoria/disco) compare per l'admin senza errori."""
    client = app.test_client()
    _login_admin(client)

    resp = client.get("/impostazioni/statistiche")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Statistiche del sistema" in html
    assert "Memoria (questo processo)" in html
    assert "CPU macchina" in html
