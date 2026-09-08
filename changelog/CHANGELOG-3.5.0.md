# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.5.0 — 8 settembre 2026 — Pulsanti di azzeramento per residui

### Nuovo: azzera un oggetto o tutto il viaggio, in caso di numeri che non tornano

Due nuovi pulsanti, pensati come rimedio diretto se qualche numero
resta incoerente (anche a seguito di bug ormai corretti, ma i cui
effetti fossero già stati salvati):

- **Azzera questo oggetto per il viaggio** — nel pannello di dettaglio
  di un oggetto (l'icona "i" a destra della riga). Rimuove quantità in
  valigia, quantità per modello e indossato per quell'oggetto, in
  questo viaggio.
- **Azzera tutti gli oggetti di questo viaggio** — nella pagina di
  modifica del viaggio. Fa lo stesso per ogni oggetto del viaggio
  (solo i tuoi, non quelli di altri collaboratori).

In entrambi i casi, l'obiettivo e "da comprare" restano invariati:
sono scelte tue, non dati da azzerare.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
