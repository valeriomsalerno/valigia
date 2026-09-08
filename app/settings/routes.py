"""
settings/routes.py
===================
Sezione "Impostazioni": al momento ospita solo la pagina Statistiche
(uso di CPU/memoria/disco, solo amministratore). Gestione utenti,
backup e cambio password restano nei rispettivi blueprint dedicati
(users, backup, auth): questo blueprint li raggruppa solo nel menu di
navigazione (vedi base.html), non ne duplica la logica.
"""

from datetime import datetime, timedelta

from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.access import admin_required
from app.utils import db_file_path

settings_bp = Blueprint("settings", __name__, url_prefix="/impostazioni", template_folder="../templates/settings")


def _gather_resource_stats() -> dict | None:
    """
    Statistiche di massima sull'uso di CPU/memoria/disco da parte del
    processo corrente e della macchina/container che lo ospita — utile
    per capire se l'app sta consumando più del previsto. Richiede
    `psutil` (in requirements.txt). Se per qualunque motivo non è
    disponibile o fallisce, ritorna None piuttosto che rompere la pagina.
    """
    try:
        import psutil
        import shutil

        process = psutil.Process()
        with process.oneshot():
            mem_info = process.memory_info()
            cpu_percent = process.cpu_percent(interval=0.15)
            create_time = process.create_time()
            num_threads = process.num_threads()

        uptime_seconds = int(datetime.now().timestamp() - create_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        if days > 0:
            uptime_label = f"{days}g {hours}h"
        elif hours > 0:
            uptime_label = f"{hours}h {minutes}min"
        else:
            uptime_label = f"{minutes}min"

        db_path = db_file_path()
        disk_usage = shutil.disk_usage(db_path.parent if db_path else "/")

        data_dir_bytes = 0
        if db_path is not None:
            for f in db_path.parent.rglob("*"):
                if f.is_file():
                    data_dir_bytes += f.stat().st_size

        return {
            "process_memory_mb": mem_info.rss / (1024 * 1024),
            "process_cpu_percent": cpu_percent,
            "process_threads": num_threads,
            "process_uptime": uptime_label,
            "system_cpu_percent": psutil.cpu_percent(interval=0.1),
            "system_cpu_count": psutil.cpu_count() or 1,
            "system_memory_percent": psutil.virtual_memory().percent,
            "system_memory_used_mb": psutil.virtual_memory().used / (1024 * 1024),
            "system_memory_total_mb": psutil.virtual_memory().total / (1024 * 1024),
            "disk_total_gb": disk_usage.total / (1024 ** 3),
            "disk_used_gb": (disk_usage.total - disk_usage.free) / (1024 ** 3),
            "disk_free_gb": disk_usage.free / (1024 ** 3),
            "disk_percent": round((disk_usage.total - disk_usage.free) / disk_usage.total * 100, 1) if disk_usage.total else 0,
            "data_dir_mb": data_dir_bytes / (1024 * 1024),
        }
    except Exception:
        current_app.logger.exception("Impossibile calcolare le statistiche di sistema.")
        return None


@settings_bp.route("/statistiche")
@login_required
@admin_required
def resources():
    return render_template("settings/statistiche.html", resources=_gather_resource_stats())


@settings_bp.route("/menu", methods=["GET", "POST"])
@login_required
def nav_order():
    """
    Ordine PERSONALE (solo visivo) delle voci del menu in alto e del
    sottomenu Catalogo. Nessun impatto su permessi o funzionalità.
    """
    from app.extensions import db

    labels_top = {
        "home": "Home", "catalogo": "Catalogo", "viaggi": "Viaggi",
        "spesa": "Lista della spesa",
    }
    labels_sub = {"oggetti": "Oggetti", "categorie": "Categorie", "valigie": "Valigie"}

    if request.method == "POST":
        top = request.form.getlist("top_order")
        sub = request.form.getlist("sub_order")
        if set(top) == set(current_user.DEFAULT_NAV_ORDER) and set(sub) == set(current_user.DEFAULT_CATALOG_SUBMENU_ORDER):
            current_user.set_nav_order(top, sub)
            db.session.commit()
            flash("Ordine del menu salvato.", "success")
        else:
            flash("Ordine non valido: ricarica la pagina e riprova.", "error")
        return redirect(url_for("settings.nav_order"))

    return render_template(
        "settings/menu_order.html",
        top_order=current_user.nav_order, labels_top=labels_top,
        sub_order=current_user.catalog_submenu_order, labels_sub=labels_sub,
    )


@settings_bp.route("/catalogo", methods=["GET", "POST"])
@login_required
def catalog_prefs():
    """
    Preferenze PERSONALI di visualizzazione del catalogo: colonne come
    icona o testo, e quale icona usare per ciascuna regola quantità e
    tipologia di valigia. Vedi User.quantity_rule_icon()/luggage_type_icon().
    """
    from app.forms import CatalogPrefsForm
    from app.extensions import db

    form = CatalogPrefsForm()
    if request.method == "GET":
        form.column_style.data = current_user.catalog_column_style
        form.icon_fixed.data = current_user.quantity_rule_icon("fixed")
        form.icon_per_day.data = current_user.quantity_rule_icon("per_day")
        form.icon_manual.data = current_user.quantity_rule_icon("manual")
        form.icon_cabina.data = current_user.luggage_type_icon("cabina")
        form.icon_stiva.data = current_user.luggage_type_icon("stiva")
        form.icon_zaino.data = current_user.luggage_type_icon("zaino")

    if form.validate_on_submit():
        current_user.catalog_column_style = form.column_style.data
        current_user.set_icon_prefs(
            quantity_rule_icons={
                "fixed": form.icon_fixed.data,
                "per_day": form.icon_per_day.data,
                "manual": form.icon_manual.data,
            },
            luggage_type_icons={
                "cabina": form.icon_cabina.data,
                "stiva": form.icon_stiva.data,
                "zaino": form.icon_zaino.data,
            },
        )
        db.session.commit()
        flash("Preferenze del catalogo salvate.", "success")
        return redirect(url_for("settings.catalog_prefs"))

    return render_template("settings/catalogo.html", form=form)


@settings_bp.route("/catalogo-pubblico", methods=["GET"])
@login_required
@admin_required
def public_catalog():
    """
    SOLO admin: elenco spoglio di oggetti e valigie (proprie), ciascuno
    con la sola spunta "pubblico" — nessun'altra informazione, per
    restare una pagina puramente operativa (spunta, salva) e non
    un'altra vista del catalogo. Le categorie non compaiono qui: quelle
    di un oggetto spuntato vengono incluse automaticamente all'export
    (vedi importer.py::export_catalog_as_base), non serve spuntarle a parte.
    """
    from app.models import Item, Luggage
    from app.importer import has_custom_base_catalog

    items = (
        Item.query.filter_by(owner_id=current_user.id, archived=False)
        .join(Item.category)
        .order_by(Item.category_id, Item.sort_order, Item.name).all()
    )
    luggages = Luggage.query.filter_by(owner_id=current_user.id).order_by(Luggage.name).all()

    return render_template(
        "settings/catalogo_pubblico.html",
        items=items, luggages=luggages, has_custom_base=has_custom_base_catalog(),
    )


@settings_bp.route("/catalogo-pubblico/esporta", methods=["POST"])
@login_required
@admin_required
def export_public_catalog():
    from app.importer import export_catalog_as_base

    count = export_catalog_as_base(current_user)
    flash(
        f"{count} oggetti pubblici sono ora il catalogo di base: verrà usato per ogni "
        "nuovo utente e per chi preme \"Importa catalogo di base\". Usa \"Scarica il file\" per portarlo su GitHub.",
        "success",
    )
    return redirect(url_for("settings.public_catalog"))


@settings_bp.route("/catalogo-pubblico/scarica")
@login_required
@admin_required
def download_public_catalog():
    from app.importer import _custom_base_catalog_path
    from flask import send_file

    path = _custom_base_catalog_path()
    if not path.exists():
        flash("Nessun catalogo di base personalizzato da scaricare: esportane prima uno.", "error")
        return redirect(url_for("settings.public_catalog"))
    return send_file(path, as_attachment=True, download_name="catalogo_base.json", mimetype="application/json")


@settings_bp.route("/catalogo-pubblico/ripristina", methods=["POST"])
@login_required
@admin_required
def reset_public_catalog():
    from app.importer import reset_base_catalog_to_default

    reset_base_catalog_to_default()
    flash("Catalogo di base ripristinato all'originale.", "success")
    return redirect(url_for("settings.public_catalog"))
