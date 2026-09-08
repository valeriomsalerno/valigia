# =============================================================================
# Dockerfile — Valigia
# =============================================================================
# Immagine Python minimale con l'app Flask pronta per essere servita da
# gunicorn. I dati (database SQLite) vivono in /app/data, che va montato
# come volume da docker-compose.yml per sopravvivere ai riavvii/rebuild
# del container.
# =============================================================================

FROM python:3.12-slim

# Evita file .pyc e forza l'output non bufferizzato (log leggibili subito)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VALIGIA_ENV=production

WORKDIR /app

# Le dipendenze vengono installate in un layer separato dal codice, così
# `docker build` le riusa dalla cache finché requirements.txt non cambia.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
