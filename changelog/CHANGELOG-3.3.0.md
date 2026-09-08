# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.3.0 — 7 settembre 2026 — Correzione critica: peso dei modelli

### Corretto: il peso di un modello non finiva mai nella valigia

**Bug serio corretto**: aggiungere un oggetto con modelli (es. camicie
di taglio diverso) non faceva mai cambiare il peso della valigia nella
carta d'imbarco. La causa: un modello portato in viaggio non era
legato a nessuna valigia specifica, quindi il suo peso non poteva
proprio entrare nel calcolo (che è sempre per valigia).

**Nuova interfaccia**: un oggetto con modelli mostra ora gli stessi
pulsanti Cabina/Stiva/Zaino di un oggetto normale — cliccando + o −
si apre una finestra dove scegli esplicitamente quale modello stai
aggiungendo o togliendo da quella valigia specifica. Il limite rispetto
a quanti ne possiedi vale ora sulla somma tra tutte le valigie, non
più per singola valigia isolata.

### Cambiato: Home ulteriormente ritoccata

- Le tre card (Lista della spesa, Catalogo, Valigie) passano
  direttamente da tre colonne a una sola, senza un passaggio
  intermedio a due.
- Nuovo ordine dei blocchi: Viaggi futuri, Lista della spesa,
  Catalogo, Valigie, Viaggi passati.

### Corretto: pulsante "Modifica" nel viaggio

Rinominato da "Modifica viaggio" a "Modifica" e non scorre più
orizzontalmente: ora tutti e tre i pulsanti (Valigie, Condividi,
Modifica) entrano comodamente anche su schermi piccoli.

### Corretto: pulsanti della Home allineati a destra su mobile

Quando il blocco dei pulsanti va a capo su una riga propria (schermi
stretti), ora resta allineato a destra invece che a sinistra.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica lega i modelli già portati in viaggio
a una valigia (la prima disponibile del proprietario), senza perdita
di dati per le righe che hanno una valigia a cui essere assegnate.
