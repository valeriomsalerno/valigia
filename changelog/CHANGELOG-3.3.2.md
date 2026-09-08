# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.3.2 — 7 settembre 2026 — Correzione critica di produzione

### Corretto: errore del server nel salvare un modello in una valigia

**Causa trovata dai log di produzione**: la versione precedente aveva
aggiunto la possibilità di legare un modello a una valigia specifica,
ma una regola più vecchia del database (che permetteva un solo
modello per oggetto, senza contare la valigia) era rimasta attiva —
SQLite non permette di rimuoverla con un semplice aggiornamento della
tabella, serviva ricostruirla da zero. Il sintomo: salvare lo stesso
modello in una seconda valigia falliva con un errore del server (500),
percepito come "un errore di comunicazione senza motivo apparente".

Aggiunto anche un test dedicato che riproduce esattamente lo schema di
un database già esistente (non uno creato da zero) per verificare
questo genere di problema in futuro, prima che arrivi in produzione.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica ricostruisce la tabella con la regola
corretta, senza alcuna perdita dei modelli già salvati nei tuoi viaggi.
