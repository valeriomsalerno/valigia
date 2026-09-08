# Valigia

Gestore di oggetti da mettere in valigia per i tuoi viaggi. Multi-utente:
ogni persona ha il proprio catalogo, le proprie valigie fisiche e la
propria lista di imballaggio — anche sui viaggi condivisi.

Per lo stato tecnico dettagliato del progetto vedi **`CONTEXT.md`**. Per
l'elenco delle funzionalità della versione corrente vedi **`CHANGELOG.md`**.

## Requisiti

- Docker e Docker Compose (v2, il comando `docker compose`)
- Un Cloudflare Tunnel già configurato sulla macchina host, che inoltri
  il traffico verso `http://127.0.0.1:4825`

## Avvio

```bash
cd valigia
cp .env.example .env
```

Apri `.env` e imposta almeno `SECRET_KEY` con una stringa lunga e
casuale (`python3 -c "import secrets; print(secrets.token_hex(32))"`).
Personalizza anche `ADMIN_USERNAME`/`ADMIN_PASSWORD` se vuoi (le
credenziali di partenza, che dovrai comunque cambiare al primo accesso).

```bash
docker compose up -d --build
```

L'app risponde su `http://127.0.0.1:4825` dell'host, e sul tuo dominio
pubblico tramite il Cloudflare Tunnel già configurato.

**Aggiornando da una versione precedente?** Non serve alcun intervento
manuale: al primo avvio i tuoi dati esistenti vengono aggiornati
automaticamente al nuovo schema, senza perdite. Vedi "Persistenza dei
dati" più sotto per i dettagli.

In fondo ad ogni pagina (anche il login) trovi il numero di versione in
esecuzione: utile per verificare che un aggiornamento sia andato a buon
fine senza dover controllare i log.

## Primo accesso

Utente e password di default sono quelli in `.env` (`admin`/`admin` se
non li hai cambiati). Al primo login devi impostare subito una nuova
password: nessun'altra pagina è raggiungibile finché non lo fai.
L'amministratore riceve un catalogo precaricato con tutti gli oggetti
del database Notion originale.

## Uso quotidiano

1. **Crea un viaggio** (meta + date, dalla home). L'app cerca anche
   un'immagine di copertina automaticamente in base alla meta.
2. Nella schermata del viaggio (che ha un suo indirizzo permanente,
   salvabile come segnalibro) trovi due schede:
   - **Valigia**: la tua lista personale, con gli oggetti raggruppati
     per categoria (una categoria alla volta, per non dover scorrere
     tanto). Per ogni oggetto: quante ne vuoi in totale ("obiettivo"),
     quante in ciascuna delle tue valigie attive, quante ne mancano da
     comprare, se è già in valigia.
   - **Lista della spesa**: condivisa con chi partecipa al viaggio,
     divisa per chi si è preso in carico l'acquisto di ciascun oggetto.
3. In **Valigie** (menu) censisci le tue borse reali: marca, nome,
   tipologia (Cabina / Stiva / Zaino), peso a vuoto, capacità. Dalla
   pagina "Valigie" di un viaggio scegli quali porti con te.
4. Dal menu **Catalogo** gestisci categorie e oggetti (anche con il loro
   peso in grammi) — compariranno automaticamente in tutti i tuoi viaggi.
   Puoi reimportare il catalogo di base in qualsiasi momento.

## Multi-utente e condivisione

- Solo l'amministratore crea nuovi utenti (sezione **Utenti**, visibile
  solo agli admin). Ogni nuovo utente riceve subito il proprio catalogo
  e due valigie di partenza.
- **La lista da mettere in valigia è sempre personale**, anche sui
  viaggi condivisi: se condividi un viaggio con un familiare, ognuno
  vede/modifica SOLO la propria lista, mai quella dell'altro.
- Quello che si condivide è: meta/date/note del viaggio (solo il
  proprietario le modifica) e la lista della spesa (visibile a tutti,
  divisa per chi compra cosa).
- Ogni utente può modificare il proprio nome/nickname dal menu utente
  ("Profilo"); l'admin può farlo per chiunque dalla sezione Utenti.

## Persistenza dei dati tra gli aggiornamenti

I dati vivono nel volume Docker `./data` (mai toccato da un rebuild
dell'immagine) e, dalla v2.1.0, un sistema di migrazioni automatiche
aggiorna lo schema del database ad ogni avvio senza mai cancellare
nulla: puoi sempre limitarti a `docker compose up -d --build`.

## Backup e ripristino

Dalla sezione **Backup** (menu, solo admin):
- **Esporta**: scarica l'intero database (tutti gli utenti, cataloghi,
  viaggi, valigie) in un unico file `.db`.
- **Ripristina**: carica un file `.db` precedentemente esportato per
  sostituire tutti i dati attuali. Viene creata automaticamente una
  copia di sicurezza dei dati precedenti prima del ripristino
  (`data/backups/`). Dopo un ripristino, riavvia il container
  (`docker compose restart`) per essere certo che tutti i processi
  vedano i dati appena ripristinati.

**Backup automatici periodici** (facoltativo, lato host): un semplice
cron che copia il file basta, dato che è autosufficiente:
```bash
# crontab -e sull'host, es. ogni notte alle 3:00
0 3 * * * cp /percorso/valigia/data/valigia.db /percorso/backup-esterno/valigia-$(date +\%F).db
```

## Importare (o reimportare) un catalogo da Notion

Il catalogo di base è già incorporato e importato automaticamente per
ogni nuovo utente. Per importare un ALTRO export CSV (colonne `Name,
Conservato, Da comprare, N. Imbarco, N. Stiva, N. Totale, Tipo`):

```bash
cp /percorso/del/tuo/export.csv ./data/import.csv
docker compose exec valigia flask list-users   # trova il tuo --user-id
docker compose exec valigia python scripts/import_notion.py /app/data/import.csv --user-id 1
```

Aggiungi `--trip-id N` per popolare anche le quantità di un tuo viaggio
già creato.

## Manutenzione

```bash
docker compose logs -f                                    # log
docker compose up -d --build                               # aggiorna
docker compose exec valigia flask reset-admin-password "x"  # password admin dimenticata
```

## Sviluppo locale (senza Docker)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python wsgi.py          # http://127.0.0.1:8000
```

**Test:**
```bash
pip install pytest
VALIGIA_ENV=testing pytest -q
```
