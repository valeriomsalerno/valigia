# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.7.0 — 4 settembre 2026 — Copertina live, valigie condivise in tempo reale

### Corretto: la ricerca dell'immagine richiedeva di salvare prima

**Causa**: il pulsante "Cerca di nuovo l'immagine" usava sempre meta e
termini di ricerca già SALVATI sul viaggio, ignorando quanto appena
scritto nei campi ma non ancora confermato con "Salva viaggio". Ora la
ricerca è immediata (senza ricaricare la pagina) e usa sempre quello che
c'è scritto nei campi in quel momento, salvandolo insieme all'immagine
trovata.

### Corretto: l'immagine caricata a mano appariva sfalsata e ingrandita

**Causa**: lo stile che applica l'immagine di sfondo era finito
sull'elemento sbagliato (il contenitore esterno della carta d'imbarco,
invece di quello interno a cui era davvero destinato) — mancava quindi
la regola che adatta l'immagine alle dimensioni del riquadro, e veniva
mostrata alla sua dimensione originale, spesso molto più grande o con
proporzioni diverse dal riquadro stesso. Corretto: ora l'immagine
caricata appare adattata correttamente, sia nella pagina di modifica sia
in quella del viaggio.

### Nuovo: ricerca nella lista della spesa del viaggio

Una barra di ricerca, come quella già presente nel pannello Valigia,
filtra gli oggetti della lista della spesa per nome.

### Nuovo: le valigie condivise si aggiornano da sole

Quantità e peso di una valigia condivisa ora si aggiornano
automaticamente ogni pochi secondi, anche quando è un ALTRO
collaboratore ad aggiungere qualcosa — prima lo si vedeva solo
ricaricando la pagina a mano. L'aggiornamento si ferma quando la scheda
del browser non è in primo piano, per non consumare risorse inutilmente.

### Nessuna azione richiesta per aggiornare

Questa versione non tocca lo schema del database.
