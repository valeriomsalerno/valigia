# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.3.3 — 7 settembre 2026 — Correzione: quantità di modelli "fantasma"

### Corretto: stato dell'oggetto sbagliato dopo l'eliminazione di una valigia

**Causa trovata riproducendo esattamente i numeri della segnalazione**:
eliminare una valigia ripuliva correttamente le quantità degli oggetti
normali al suo interno, ma NON quelle dei modelli (introdotti di
recente) — restavano "appese" nel database, invisibili in qualunque
stepper, ma contate comunque nel totale dell'oggetto. Risultato: un
oggetto poteva apparire "in valigia" nonostante gli stepper visibili
sommassero molto meno dell'obiettivo mostrato.

Corretto alla radice (eliminare una valigia ora ripulisce sempre tutto
il suo contenuto, modelli inclusi) e ripulita anche la conseguenza già
presente nei dati esistenti.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica ripulisce eventuali quantità di
modelli rimaste agganciate a valigie non più esistenti, senza toccare
nient'altro.
