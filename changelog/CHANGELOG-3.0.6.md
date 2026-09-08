# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.6 — 6 settembre 2026 — Bordo di categoria arrotondato correttamente

### Corretto: il bordo di categoria aveva ancora gli angoli squadrati

La barra colorata introdotta nella versione precedente risolveva il
distacco dalla curva, ma restava squadrata agli angoli: l'arrotondamento
visibile apparteneva a un elemento diverso (più interno) da quello a
cui la barra era agganciata. Corretto dando l'arrotondamento
direttamente all'elemento giusto: ora la barra segue la stessa forma
del contenuto a cui è accanto, in ogni pagina.

### Corretto: tabella del catalogo oggetti ancora troppo larga

La colonna "Valigia predefinita" occupava più spazio del necessario,
lasciando poco margine per i pulsanti dell'ultima colonna. Ristretta a
una larghezza proporzionata.

### Corretto: tabella delle categorie, ulteriore aggiustamento

Ancora più spazio alla colonna "Icona", ancora meno a "Nome".

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
