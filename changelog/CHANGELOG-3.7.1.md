# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.7.1 — 8 settembre 2026 — Anteprima foto dei modelli, scroll preservato

### Corretto: anteprima foto assente per un oggetto CON modelli, nel viaggio

L'anteprima/zoom della foto funzionava per un oggetto semplice (senza
modelli), ma non compariva affatto aprendo la finestra di scelta del
modello per un oggetto CON modelli, dalla schermata di un viaggio —
anche quando il modello aveva davvero una foto caricata. Causa: il
filtro Jinja che alimenta quella finestra (`get_variant_modal_data`)
non includeva alcuna informazione sulla foto. Corretto in due punti:
il filtro ora espone `has_photo`/`photo_url`, e la finestra mostra una
miniatura cliccabile (stesso overlay di zoom già in uso ovunque
nell'app) quando presente.

### Corretto: la posizione di scroll si perdeva tornando da "Torna al viaggio"

Tornando alla schermata di un viaggio dalle impostazioni di un oggetto
(o di una valigia, condivisione, modifica viaggio) tramite il pulsante
"Torna al viaggio", la pagina ripartiva sempre dall'inizio, anche se
prima si era scrollato molto più in basso — perché quei link sono una
navigazione a pagina intera, non l'overlay del pannello di dettaglio.
Ora la posizione di scroll viene salvata prima di uscire dal workspace
e ripristinata automaticamente al ritorno, una sola volta.

Vedi `CONTEXT.md`, sezione 4.39, per i dettagli tecnici di entrambe le
correzioni.
