# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.4.0 — 7 settembre 2026 — Finestra di scelta modello riscritta da zero

### Corretto: valori sbagliati, avvisi rimasti accesi, calcoli incoerenti

**Causa trovata**: la finestra teneva traccia di "quale valigia è
aperta ora" con un solo valore condiviso, riletto anche dentro le
risposte del server arrivate in ritardo. Se nel frattempo si chiudeva
la finestra e se ne apriva un'altra per una valigia diversa, una
risposta arrivata in ritardo per la valigia precedente finiva
applicata a quella appena aperta — spiegando insieme più cose viste
tutte insieme: valori mai scelti comparsi da soli, il pulsante "−" che
non aggiornava correttamente i modelli, e l'avviso "oltre l'obiettivo"
rimasto acceso anche dopo essere rientrati nel limite consentito.

Riscritta la parte di comunicazione con il server perché ogni riga
tenga il proprio contesto fisso, indipendente da quale valigia sia
aperta al momento in cui la risposta arriva, con un doppio controllo
contro le risposte fuori ordine (sia per singolo modello sia per
l'intero oggetto).

### Corretto: il pulsante "+" poteva finire fuori dallo schermo

Con una descrizione del modello lunga, lo stepper (incluso il
pulsante per aggiungere) poteva essere spinto fuori dal bordo della
finestra. La riga ora impila l'etichetta sopra e lo stepper sotto,
sempre interamente visibile a qualunque lunghezza di testo.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
