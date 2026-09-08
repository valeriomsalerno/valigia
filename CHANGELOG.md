# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.1 — 8 settembre 2026 — Correzione critica: il trascinamento non salvava mai

### Corretto: la larghezza delle colonne non si poteva davvero regolare

**Causa trovata**: il modo in cui misuravo dove si trovava il bordo di
una colonna non funzionava mai, in nessun browser — ogni tentativo di
trascinamento calcolava una larghezza vicina allo zero, che veniva
sempre rifiutata. Non era un problema occasionale: la funzione, così
com'era, non poteva funzionare in nessun caso. Riscritta da capo con
un metodo di misurazione affidabile.

Anche il bordo da trascinare ora si vede sempre, non solo passandoci
sopra con il mouse per caso.

### Cambiato: catalogo pubblico spostato in una pagina dedicata

Come richiesto: le spunte "pubblico" non compaiono più nelle pagine
principali del catalogo. Vivono ora solo in una nuova pagina,
raggiungibile dal menu Impostazioni → "Configura catalogo pubblico"
(visibile solo agli account amministratore) — un elenco semplice di
nomi con la sola spunta, senza altre informazioni.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
