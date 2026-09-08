# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.3.0 — 3 settembre 2026 — Correzione critica di salvataggio, oggetti indossati

Versione nata da un bug critico segnalato con i log del container
(`docker compose logs`), che questa volta hanno reso la causa
inequivocabile, e da una funzione mancante.

### Corretto: impossibile aprire o creare viaggi, aggiungere quantità

**Causa**: una colonna ormai superata dello schema del database
(`trip_item_qty.trip_bag_id`, dalla versione 1.0/2.0, sostituita da
`trip_luggage_id` fin dalla v2.1) era rimasta con un vincolo NOT NULL.
Le migrazioni automatiche di questa app, per filosofia, AGGIUNGONO
sempre colonne ma non toccano mai i vincoli di quelle esistenti (per non
rischiare mai di perdere dati) — questo però significava che quella
colonna fantasma, ormai inutilizzata dal codice, bloccava OGNI nuovo
inserimento con l'errore "NOT NULL constraint failed:
trip_item_qty.trip_bag_id". In pratica: impossibile aprire un viaggio
già esistente, crearne uno nuovo, o aggiungere una quantità in una
valigia — lo stesso identico problema alla radice di tutti e tre.

**Soluzione**: una nuova migrazione ricostruisce questa tabella con lo
schema corretto (SQLite non permette di rilassare un vincolo NOT NULL
con un semplice ALTER TABLE, va ricreata), preservando tutte le
quantità già inserite. Riprodotto fedelmente lo scenario esatto
segnalato (stesso schema di database, stessi dati) e verificato che,
dopo l'aggiornamento, aprire un viaggio esistente, crearne uno nuovo e
aggiungere quantità nelle valigie funzionino tutti correttamente.

### Nuovo: oggetti indossati direttamente (non vanno in valigia)

Alcuni vestiti o accessori (una giacca pesante, scarpe da trekking) non
si mettono in valigia: si indossano direttamente durante il viaggio.
Un nuovo pulsante (icona maglietta) su ogni oggetto lo segnala: una
volta attivato, l'oggetto conta subito come pronto (verde), a
prescindere dall'obiettivo impostato o dalle quantità nelle valigie.
"Da comprare" mantiene comunque sempre la priorità più alta: se
quell'oggetto va ancora acquistato, non risulta pronto finché non lo si
segna come acquistato.

### Nessuna azione richiesta per aggiornare

Sia la riparazione della tabella sia il nuovo campo per gli oggetti
indossati vengono applicati automaticamente al primo avvio di questa
versione, senza perdita di dati esistenti.
