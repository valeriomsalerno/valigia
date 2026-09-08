# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.6 — 8 settembre 2026 — Correzione definitiva: colonna Peso

### Corretto: i valori sembravano centrati invece che a sinistra

Un rientro che avevo aggiunto per dare respiro alla colonna
precedente dava, con numeri brevi, l'illusione di un testo centrato.
Rimosso ogni trattamento speciale: la colonna Peso ora si comporta
esattamente come tutte le altre, senza alcuna regola dedicata. Lo
spazio dalla colonna precedente resta comunque adeguato grazie alla
larghezza già allargata in una versione precedente.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
