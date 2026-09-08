"""
cli.py
======
Comandi da riga di comando aggiuntivi, disponibili con `flask <comando>`
dentro il container (o nel virtualenv locale).

    flask reset-admin-password <nuova_password>
        Reimposta la password del primo utente amministratore trovato.

    flask import-notion <percorso_csv> --user-id N [--trip-id M]
        Importa il CSV nel catalogo dell'utente indicato (obbligatorio,
        dato che ogni utente ha un catalogo separato), opzionalmente
        popolando anche un viaggio specifico.
"""

import click
from flask import Flask


def register_cli(app: Flask) -> None:

    @app.cli.command("reset-admin-password")
    @click.argument("new_password")
    def reset_admin_password(new_password):
        """Reimposta la password del primo utente amministratore."""
        from app.extensions import db
        from app.models import User, UserRole

        admin = User.query.filter_by(role=UserRole.ADMIN).order_by(User.id).first()
        if admin is None:
            click.echo("Nessun amministratore trovato: avvia l'app almeno una volta prima.")
            return
        admin.set_password(new_password)
        admin.must_change_password = True
        db.session.commit()
        click.echo(f'Password di "{admin.username}" reimpostata. Al prossimo login verrà richiesto il cambio.')

    @app.cli.command("import-notion")
    @click.argument("csv_path")
    @click.option("--user-id", type=int, required=True, help="ID dell'utente nel cui catalogo importare.")
    @click.option("--trip-id", type=int, default=None, help="ID del viaggio da popolare con le quantità.")
    def import_notion(csv_path, user_id, trip_id):
        """Importa oggetti (e opzionalmente un viaggio) dal CSV esportato da Notion."""
        from app.models import Trip, User
        from app.importer import import_notion_csv

        owner = User.query.get(user_id)
        if owner is None:
            click.echo(f"Nessun utente con id {user_id}.")
            return

        target_trip = None
        if trip_id is not None:
            target_trip = Trip.query.get(trip_id)
            if target_trip is None or target_trip.owner_id != owner.id:
                click.echo(f"Nessun viaggio con id {trip_id} di proprietà dell'utente {owner.username}.")
                return

        summary = import_notion_csv(csv_path, owner=owner, target_trip=target_trip)

        click.echo(f"--- Importazione completata per {owner.username} ---")
        click.echo(f"Categorie create:       {summary.categories_created}")
        click.echo(f"Oggetti creati:         {summary.items_created}")
        click.echo(f"Oggetti già esistenti:  {summary.items_matched}")
        click.echo(f"Righe saltate (vuote):  {summary.rows_skipped}")
        if target_trip:
            click.echo(f"Righe viaggio scritte:  {summary.trip_items_written}")
        for w in summary.warnings:
            click.echo(f"ATTENZIONE: {w}")

    @app.cli.command("list-users")
    def list_users():
        """Elenca gli utenti esistenti (utile per trovare l'--user-id da usare)."""
        from app.models import User

        for u in User.query.order_by(User.id).all():
            stato = "attivo" if u.active else "disattivato"
            click.echo(f"#{u.id}  {u.username}  ruolo={u.role}  {stato}")
