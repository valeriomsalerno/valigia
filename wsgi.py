"""
wsgi.py
=======
Punto di ingresso usato da gunicorn in produzione (vedi entrypoint.sh) e,
in locale, per lanciare il server di sviluppo con `python wsgi.py`.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Solo per sviluppo locale senza Docker. In produzione si usa gunicorn.
    app.run(host="0.0.0.0", port=8000, debug=False)
