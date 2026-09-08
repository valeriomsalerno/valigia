# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.4.1 — 7 settembre 2026 — Correzione: numeri fuori conteggio per modelli eliminati

### Corretto: stepper e obiettivo con numeri che non corrispondevano a nulla

**Causa trovata**: eliminare (o sostituire) un modello dal catalogo
lasciava le sue quantità già portate in viaggio agganciate nel
database — invisibili in qualunque finestra di scelta modello (che
elenca solo i modelli ancora esistenti), ma contate comunque nel
totale. Sintomo: uno stepper poteva mostrare un numero mentre la
finestra elencava ogni modello a zero, e l'obiettivo poteva risultare
"superato" anche quando la somma visibile era ben sotto il limite.

È lo stesso tipo di problema corretto nella versione 3.3.3, ma
sull'altro lato del collegamento (il modello, non la valigia). Dopo
averlo trovato una seconda volta, è stato fatto un controllo su
*tutte* le altre relazioni del genere presenti nell'app: non ne sono
emerse altre.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica ripulisce eventuali quantità rimaste
agganciate a modelli non più esistenti, senza toccare nient'altro.
