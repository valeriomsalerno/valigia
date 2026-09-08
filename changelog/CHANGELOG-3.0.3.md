# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.3 — 6 settembre 2026 — Correzione definitiva: un solo bordo di categoria

Versione correttiva: nel workspace di un viaggio, ogni riga di un
oggetto aveva ancora un proprio piccolo bordo colorato per stato,
oltre allo sfondo sfumato — creando una seconda linea colorata che
competeva visivamente con l'unico bordo che deve esserci, quello di
categoria. Corretto: ora l'unica linea di bordo è quella di categoria;
lo stato di ciascun oggetto resta segnalato solo dallo sfondo sfumato,
mai da un bordo proprio.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
