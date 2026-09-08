# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.2 — 8 settembre 2026 — Modalità modifica tabella

### Nuovo: pulsante "Modifica tabella"

I separatori tra le colonne non sono più visibili di continuo — un
nuovo pulsante "Modifica tabella" li fa comparire solo quando servono
davvero. Dopo aver salvato una nuova larghezza, la modalità si
disattiva da sola: non serve ricordarsi di chiuderla.

### Corretto: la larghezza ora vale subito per tutte le categorie

Regolare una colonna nella tabella di una categoria (es. "Vestiti")
non richiede più di ricaricare la pagina per vedere lo stesso
cambiamento anche nelle altre categorie: si applica ovunque, subito.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
