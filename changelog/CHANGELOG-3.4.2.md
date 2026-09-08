# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.4.2 — 7 settembre 2026 — Correzione: il conteggio cambiava, i modelli no

### Corretto: premere +/- su Cabina o Stiva aggiornava il numero ma non i modelli

**Causa trovata**: lo stepper per valigia di un oggetto con modelli
condivide lo stesso aspetto (e per errore anche parte del
comportamento) di uno stepper normale — un clic attivava DUE
meccanismi insieme: uno aggiornava subito il numero mostrato tramite
il sistema pensato per oggetti SENZA modelli, l'altro apriva
correttamente la finestra di scelta modello. I due non si parlavano
tra loro, quindi il numero cambiava ma i modelli elencati nella
finestra restavano quelli di prima.

Corretto separando nettamente i due sistemi: ora solo la finestra di
scelta modello può cambiare la quantità di un oggetto con modelli.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
