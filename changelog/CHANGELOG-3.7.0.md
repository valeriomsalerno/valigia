# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.7.0 — 8 settembre 2026 — Foto per oggetti e modelli

### Corretto: nessun modo di aggiungere modelli a un oggetto appena creato

Creare un nuovo oggetto portava alla lista del catalogo — "Modelli e
dettagli" compare solo per un oggetto già esistente, quindi bisognava
prima salvare, ritrovarlo nella lista, riaprirlo in modifica. Ora,
dopo il salvataggio, si arriva direttamente alla pagina di modifica
dello stesso oggetto appena creato, dove "Modelli e dettagli" è già
disponibile.

### Nuovo: una foto per ogni oggetto o modello

- Nella pagina di un oggetto (e per ciascun modello, nella pagina
  "Modelli e dettagli"): un pulsante per caricare una foto, dal telefono
  (fotocamera o libreria) o dal computer.
- Piccola anteprima ovunque l'oggetto compare — nel catalogo e nella
  schermata del viaggio.
- Cliccando l'anteprima, la foto si apre a schermo intero (chiudibile
  toccando fuori, il pulsante di chiusura, o il tasto Esc).
- Eliminare un oggetto o un modello rimuove anche la sua foto.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge i campi necessari, senza
alcuna perdita di dati.
