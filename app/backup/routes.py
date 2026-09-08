"""
backup/routes.py
=================
Esportazione e ripristino dell'intero database in un solo file (il
database SQLite stesso: contiene già tutti gli utenti, i cataloghi, i
viaggi, tutto). Riservato all'amministratore.

Il ripristino sostituisce il file del database mentre l'app è in
esecuzione: per un'app a singolo processo va bene così, ma se il
container gira con più worker (vedi entrypoint.sh, --workers 2) i worker
diversi da quello che ha eseguito il ripristino potrebbero continuare a
usare connessioni già aperte verso il vecchio file finché non vengono
riavviati. Per questo, dopo un ripristino, in interfaccia consigliamo
esplicitamente `docker compose restart`.
"""

import shutil
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    send_file,
)
from flask_login import login_required

from app.extensions import db
from app.access import admin_required
from app.utils import db_file_path

backup_bp = Blueprint("backup", __name__, url_prefix="/backup", template_folder="../templates/backup")


def _safety_backups_dir() -> Path:
    """Cartella dove vengono conservate le copie di sicurezza automatiche fatte prima di ogni ripristino."""
    db_path = db_file_path()
    backups_dir = (db_path.parent if db_path else Path(".")) / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


@backup_bp.route("/")
@login_required
@admin_required
def index():
    db_path = db_file_path()
    size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path and db_path.exists() else None

    safety_backups = []
    if db_path:
        backups_dir = _safety_backups_dir()
        for f in sorted(backups_dir.glob("valigia-*.db"), reverse=True)[:10]:
            safety_backups.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(f.stat().st_mtime),
            })

    return render_template(
        "backup/index.html",
        db_available=db_path is not None,
        size_mb=size_mb,
        safety_backups=safety_backups,
    )


@backup_bp.route("/esporta", methods=["POST"])
@login_required
@admin_required
def export_backup():
    db_path = db_file_path()
    if db_path is None or not db_path.exists():
        flash("Nessun database su file da esportare in questo ambiente.", "error")
        return redirect(url_for("backup.index"))

    # SQLite può scrivere ancora nella cache/WAL: un checkpoint prima
    # dell'esportazione assicura che il file su disco sia aggiornato.
    try:
        db.session.execute(db.text("PRAGMA wal_checkpoint(FULL)"))
    except Exception:
        pass

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    download_name = f"valigia-backup-{timestamp}.db"
    return send_file(db_path, as_attachment=True, download_name=download_name, mimetype="application/octet-stream")


@backup_bp.route("/ripristina", methods=["POST"])
@login_required
@admin_required
def restore_backup():
    db_path = db_file_path()
    if db_path is None:
        flash("Nessun database su file in questo ambiente: impossibile ripristinare.", "error")
        return redirect(url_for("backup.index"))

    uploaded = request.files.get("backup_file")
    if not uploaded or not uploaded.filename:
        flash("Seleziona un file di backup (.db) da ripristinare.", "error")
        return redirect(url_for("backup.index"))

    tmp_path = db_path.parent / f"_upload_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
    uploaded.save(tmp_path)

    if not _looks_like_valigia_db(tmp_path):
        tmp_path.unlink(missing_ok=True)
        flash(
            "Il file caricato non sembra un database di Valigia valido "
            "(manca la tabella 'users' attesa). Ripristino annullato.", "error",
        )
        return redirect(url_for("backup.index"))

    # Checkpoint completo + chiusura di tutte le connessioni PRIMA di fare
    # la copia di sicurezza: così il database attuale è autosufficiente
    # (nessun dato ancora solo nel file -wal) quando lo copiamo, e non
    # lasciamo connessioni aperte mentre sostituiamo il file sotto di loro.
    try:
        db.session.execute(db.text("PRAGMA wal_checkpoint(FULL)"))
    except Exception:
        pass
    db.session.remove()
    db.engine.dispose()

    # Copia di sicurezza del database ATTUALE prima di sovrascriverlo,
    # così un ripristino sbagliato è comunque recuperabile.
    safety_name = f"valigia-{datetime.now().strftime('%Y%m%d-%H%M%S')}-prima-del-ripristino.db"
    shutil.copy2(db_path, _safety_backups_dir() / safety_name)

    shutil.move(str(tmp_path), str(db_path))

    # Rimuove eventuali file -wal/-shm residui del database PRECEDENTE:
    # appartengono ai dati di prima e, se lasciati lì, SQLite potrebbe
    # provare a riapplicarli al file appena ripristinato, corrompendolo.
    for suffix in ("-wal", "-shm"):
        stale = db_path.parent / (db_path.name + suffix)
        stale.unlink(missing_ok=True)

    flash(
        "Database ripristinato. Per sicurezza, riavvia il container "
        "(docker compose restart) così tutti i processi ripartono puliti "
        "con i dati appena ripristinati.", "success",
    )
    return redirect(url_for("backup.index"))


def _looks_like_valigia_db(path: Path) -> bool:
    """Controllo minimo di validità: è un SQLite reale e ha una tabella 'users'."""
    import sqlite3

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        conn.close()
        return row is not None
    except sqlite3.Error:
        return False
