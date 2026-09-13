# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.8.0 — 13 settembre 2026 — Pagina oggetto unificata, ricerca istantanea

### Novità: dettaglio e modifica di un oggetto sono ora un'unica pagina

Prima erano due pagine separate che si rimandavano continuamente
l'una all'altra — "Modifica" da una portava all'altra, "Modelli e
dettagli" dall'altra tornava alla prima — troppi click per una
singola modifica. Ora è tutto su una pagina sola: il modulo di
modifica a sinistra, i dettagli (zona pericolosa, modelli, storico nei
viaggi) a destra, che si dispongono in un'unica colonna su schermi
piccoli. La card "Automazione quantità" è sparita: ripeteva in sola
lettura campi già editabili proprio accanto, nel modulo.

### Corretto: "Salva oggetto" non riportava più dove si era prima

Cliccare "Modifica" su un oggetto e poi "Salva oggetto" lasciava sulla
pagina di modifica stessa, invece di tornare alla lista o al viaggio
da cui si era partiti. Ora torna esattamente lì, alla stessa posizione
di scorrimento di prima.

### Novità: ricerca in tempo reale nel workspace di un viaggio

Il campo di ricerca del pannello "Valigia" richiedeva di premere
Invio per vedere i risultati. Ora filtra mentre si digita, come già
succedeva nella "Lista della spesa" — e se il risultato si trova in
un'altra categoria rispetto a quella selezionata, ci si sposta
automaticamente.

### Novità: eliminazione definitiva di oggetti archiviati

Un oggetto archiviato con uno storico di viaggi passati non si poteva
eliminare definitivamente in nessun modo. Ora sì — un oggetto ancora
attivo (non archiviato) resta invece protetto finché non lo si
archivia. Aggiunto anche un pulsante di eliminazione diretto nella
lista "Vedi archiviati", senza dover aprire ogni oggetto uno per uno.

Vedi `CONTEXT.md`, sezione 4.40, per i dettagli tecnici completi.
