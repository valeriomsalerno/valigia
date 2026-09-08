#!/usr/bin/env python3
"""
scripts/import_notion.py
=========================
Script standalone per importare un CSV esportato da Notion nel catalogo
di un utente specifico, senza dover configurare FLASK_APP.

    # Trova prima l'ID dell'utente:
    docker compose exec valigia flask list-users

    # Poi importa nel suo catalogo:
    python scripts/import_notion.py /percorso/export.csv --user-id 2

    # Per popolare anche un viaggio specifico con le quantità:
    python scripts/import_notion.py /percorso/export.csv --user-id 2 --trip-id 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.models import Trip, User  # noqa: E402
from app.importer import import_notion_csv  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Importa oggetti dal CSV esportato da Notion.")
    parser.add_argument("csv_path", help="Percorso del file CSV da importare.")
    parser.add_argument("--user-id", type=int, required=True, help="ID dell'utente nel cui catalogo importare.")
    parser.add_argument("--trip-id", type=int, default=None, help="Viaggio da popolare con le quantità.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        owner = User.query.get(args.user_id)
        if owner is None:
            print(f"Nessun utente con id {args.user_id}. Usa 'flask list-users' per vedere gli ID disponibili.")
            sys.exit(1)

        target_trip = None
        if args.trip_id is not None:
            target_trip = Trip.query.get(args.trip_id)
            if target_trip is None or target_trip.owner_id != owner.id:
                print(f"Nessun viaggio con id {args.trip_id} di proprietà di {owner.username}.")
                sys.exit(1)

        summary = import_notion_csv(args.csv_path, owner=owner, target_trip=target_trip)

        print(f"--- Importazione completata per {owner.username} ---")
        print(f"Categorie create:       {summary.categories_created}")
        print(f"Oggetti creati:         {summary.items_created}")
        print(f"Oggetti già esistenti:  {summary.items_matched}")
        print(f"Righe saltate (vuote):  {summary.rows_skipped}")
        if target_trip:
            print(f"Righe viaggio scritte:  {summary.trip_items_written}")
        for w in summary.warnings:
            print(f"ATTENZIONE: {w}")


if __name__ == "__main__":
    main()
