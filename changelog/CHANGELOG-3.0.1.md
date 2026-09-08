# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.1 — 6 settembre 2026 — Correzioni su bordo doppio, modelli, mobile, offline

### Corretto: doppia linea colorata nel workspace di un viaggio

**Causa**: ogni riga di un oggetto ha già un proprio bordo colorato in
base allo stato (verde/rosso/giallo/grigio); il bordo colorato di
categoria, pensato per il catalogo (dove le righe non hanno un proprio
colore), veniva applicato ANCHE lì, creando due linee verticali
scollegate invece di una sola. Corretto: il bordo di categoria resta
solo nel catalogo, dove ha senso.

### Migliorato: più facile trovare e usare i modelli di un oggetto

Non era chiaro da dove attivare i "modelli" (introdotti nella versione
precedente per oggetti come camicie/pantaloni di taglio diverso). Ora,
dalla pagina di modifica di un oggetto, un pulsante "Modelli e
dettagli" porta dritto alla sezione giusta; nel campo peso compare un
suggerimento esplicito, diverso se l'oggetto è nuovo (i modelli si
aggiungono solo dopo il primo salvataggio) o già esistente; nel
catalogo, un'iconcina accanto al nome segnala quali oggetti hanno già
dei modelli definiti.

### Corretto: il pulsante "Archivia" spariva su mobile

Su schermi stretti, la colonna delle azioni (Modifica/Archivia) poteva
diventare troppo stretta per i pulsanti, e uno spariva tagliato invece
di restare visibile. Corretto con una larghezza sempre garantita per
quella colonna.

### Migliorato: funzionamento offline più chiaro e più utile

- Aprire offline un viaggio mai visitato prima mostrava silenziosamente
  la Home al posto della pagina richiesta (sembrava un link "rotto").
  Ora compare una spiegazione chiara: quella pagina non è ancora
  disponibile offline, va aperta almeno una volta online.
- I tuoi viaggi vengono ora precaricati automaticamente in background
  ogni volta che apri la Home o l'elenco Viaggi con la rete attiva:
  risultano quindi consultabili offline anche se non li hai aperti
  singolarmente di recente.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
