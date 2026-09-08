# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.7 — 6 settembre 2026 — Tabella catalogo ricostruita da zero

### Corretto: la tabella del catalogo oggetti non entrava nella pagina

**Causa vera**: le larghezze delle colonne mischiavano percentuali e
pixel fissi — la parte in pixel non si restringe mai su uno schermo
stretto, quindi la tabella traboccava sempre, indipendentemente da
quale colonna venisse ristretta. Ricostruita da zero con SOLO
percentuali per tutte le colonne (Nome, la più larga, poi Regola
quantità, poi Valigia predefinita, poi Peso, poi le azioni): ora la
tabella si restringe sempre in proporzione e non richiede mai
scorrimento orizzontale, né su desktop né su mobile.

### Corretto: campo icona nella pagina Categorie a larghezza fissa

Ora riempie tutta la colonna, invece di avere una larghezza fissa
scollegata da quella della colonna.

### Cambiato: rimossa l'etichetta di categoria dalle tabelle di un viaggio

Il nome della categoria sopra ogni tabella (visibile selezionando
"Tutti") resta solo nel catalogo; nel workspace di un viaggio non
compare più.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
