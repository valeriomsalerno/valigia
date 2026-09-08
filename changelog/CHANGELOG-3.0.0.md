# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.0 — 6 settembre 2026 — Funzionamento offline, modelli per oggetto

### Nuovo: puoi continuare a preparare la valigia senza connessione

Le modifiche più frequenti mentre si prepara un viaggio — quantità
nelle valigie, obiettivo, unità da comprare, quantità indossata,
quantità per modello — ora funzionano anche senza rete (es. in aereo):
vengono salvate sul telefono e sincronizzate da sole non appena torna
la connessione. Mentre una modifica è in sospeso, un piccolo indicatore
(bordo tratteggiato) lo segnala; un banner in alto mostra quante
modifiche sono ancora in attesa.

**Limiti da conoscere**:
- Solo le azioni sopra elencate funzionano offline: condividere un
  viaggio, gestire gli utenti, crearne uno nuovo o caricare un'immagine
  richiedono ancora una connessione attiva.
- Su iOS, la sincronizzazione riparte quando riapri l'app con
  connessione, non mentre è chiusa in background (Safari non supporta
  la sincronizzazione automatica "in background" come Chrome/Android).
- Se un'altra persona ha modificato la stessa cosa nel frattempo (es.
  una valigia condivisa), vince l'ultima modifica sincronizzata: nessun
  tentativo di unire le due.

Le pagine dei viaggi già aperti restano inoltre consultabili offline
(anche senza aver preparato nulla in anticipo), grazie a una cache che
si aggiorna da sola man mano che navighi, senza bisogno di alcuna
configurazione.

### Nuovo: modelli per un oggetto (es. camicie, pantaloni)

Per gli oggetti che hai in più varianti diverse tra loro, ora puoi
definire dei "modelli" (dalla pagina dell'oggetto): un nome
descrittivo, il peso specifico e quanti ne possiedi. Se un oggetto ha
almeno un modello, preparalo per un viaggio chiede quanti ne porti di
CIASCUN modello (invece di un generico conteggio totale), con calcolo
del peso specifico per modello.

**Nota**: per contenere la complessità, i modelli non si assegnano a
una valigia specifica (solo "quanti ne porti", non "in quale valigia")
— il loro peso comparirà quindi nel totale dell'oggetto ma non nel
dettaglio per singola valigia della carta d'imbarco.

### Migliorato: diverse rifiniture visive

- Colori di stato (In valigia/Da comprare/Da preparare/Non necessario)
  più marcati, con la sfumatura più evidente di prima.
- Colonna "Nome" uniforme in tutte le tabelle del catalogo, più spazio
  tra una tabella e l'altra.
- Le tabelle per categoria mostrano il proprio nome quando sono visibili
  insieme (scheda "Tutti"), con un accento colorato coerente.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge le tabelle necessarie ai
modelli, senza alcuna perdita di dati esistenti.
