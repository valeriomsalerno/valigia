# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.4.3 — 7 settembre 2026 — Correzione: il salvataggio "non prendeva mai"

### Corretto: riaprendo la finestra i numeri vecchi non sparivano mai

**Causa trovata**: dopo aver salvato un cambiamento, il codice
aggiornava i dati "freschi" per tutte le ALTRE valigie dello stesso
oggetto, ma per un errore escludeva esplicitamente la valigia da cui
il salvataggio era partito. Il server accettava e salvava
correttamente ogni modifica (confermato dai log), ma chiudere e
riaprire la finestra per la stessa valigia mostrava sempre i numeri
del primissimo caricamento della pagina, mai aggiornati — dando
l'impressione che nessun salvataggio avesse mai effetto.

Se hai numeri che ti sembrano sbagliati per un oggetto con modelli,
ricarica la pagina del viaggio una volta aggiornato: da questo momento
in poi la finestra resta sempre coerente con quanto salvato, anche
riaprendola più volte senza ricaricare la pagina.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
