# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.0.0 — 3 settembre 2026 — Multi-utente, condivisione, valigie fisiche

Versione maggiore: introduce il multi-utente e diversi miglioramenti
richiesti dopo il primo utilizzo reale della v1.0.0.

> **⚠️ Aggiornamento dalla v1.0.0**: lo schema del database è cambiato in
> modo sostanziale (il catalogo non è più globale ma di ogni utente).
> Prima di avviare questa versione, **elimina il file
> `data/valigia.db`** (o spostalo altrove come backup): al riavvio verrà
> ricreato da zero con l'utente amministratore e il catalogo di base
> precaricato. Non esiste una migrazione automatica dei dati della v1.

### Correzioni

- **Risolto il menu "Catalogo" che non si apriva**: la barra di
  navigazione aveva `overflow-x: auto`, che per specifica CSS forzava
  anche `overflow-y` a tagliare (nascondere) il menu a tendina appena
  sotto. Ora la barra va semplicemente a capo su schermi stretti, senza
  tagliare nulla.
- **Corrette le etichette dei bagagli troncate** ("VALIGI", "BAGAGL"
  nella dashboard): ogni tipo di bagaglio ha ora un campo dedicato
  "etichetta breve" (default "Stiva" / "Cabina"), modificabile in
  qualsiasi momento dal Catalogo, invece di un troncamento automatico del
  nome.
- **Sostituiti gli apostrofi usati come accenti** (es. "gia'", "perche'")
  con i veri caratteri accentati UTF-8 in tutto il codice e nell'interfaccia,
  per una corretta resa in italiano, inglese e francese.

### Multi-utente

- L'amministratore può creare altri utenti dalla nuova sezione **Utenti**
  (nome utente + password iniziale + ruolo). Ogni nuovo utente riceve
  subito il proprio catalogo personale, precaricato automaticamente dal
  catalogo di base.
- **Il catalogo è personale**: categorie, oggetti e tipi di bagaglio
  appartengono a un utente specifico. Due utenti possono avere una
  categoria con lo stesso nome senza alcun conflitto: sono righe
  separate. Modificare il proprio catalogo non tocca mai quello di altri
  utenti.
- **Catalogo di base precaricato**: lo stesso export Notion di partenza è
  ora incorporato nell'app e importato automaticamente nel catalogo di
  ogni nuovo utente. È anche disponibile un pulsante "Importa catalogo di
  base" nella pagina Oggetti per arricchire il proprio catalogo in
  qualsiasi momento (non duplica oggetti già presenti).
- **Condivisione dei viaggi**: il proprietario di un viaggio può
  condividerlo con altri utenti dalla pagina "Condividi". Chi riceve la
  condivisione può vedere il viaggio e modificarne gli oggetti (quantità,
  conservato, da comprare) ma non la struttura (date, meta, bagagli,
  eliminazione), che resta riservata al proprietario.
- L'amministratore può disattivare un utente (non può più accedere) e
  reimpostargli la password in qualsiasi momento.

### Acquisti: quantità invece di sì/no

- Il vecchio interruttore booleano "da comprare" è stato sostituito da un
  **numero di unità mancanti**: non è più tutto o niente, puoi indicare
  che ti mancano 2 boxer su 13 invece di segnarli tutti da comprare.
- La dashboard mostra uno stepper dedicato (icona carrello) accanto a
  ogni oggetto per impostare rapidamente quante unità mancano.
- La lista della spesa ora mostra, per ogni oggetto, quante unità
  servono in totale, quante ne possiedi già e quante ne mancano, con la
  possibilità di correggere il numero direttamente da lì.

### Sezione Valigie (borse fisiche)

- Nuova sezione **Valigie** per censire le borse che possiedi davvero:
  marca, nome/modello, peso a vuoto (kg) e capacità interna (litri).
- Dalla pagina "Bagagli" di un viaggio puoi collegare ciascun bagaglio
  attivo (es. "Valigia da stiva") alla valigia fisica che stai
  effettivamente usando per quel viaggio.

### Peso degli oggetti

- Ogni oggetto di catalogo può avere un peso per unità, in grammi. Nella
  vista di dettaglio di un oggetto in un viaggio viene mostrato anche il
  peso totale delle unità previste per quel viaggio.
- Tutti i numeri decimali (pesi, capacità) sono mostrati con la virgola
  come separatore, in stile italiano.

### Carta d'imbarco

- **Immagine di copertina automatica**: alla creazione (o modifica della
  meta) di un viaggio, l'app cerca su Wikipedia una foto rappresentativa
  della destinazione e la usa come sfondo della carta d'imbarco. Non
  richiede alcuna chiave API. Se la ricerca non trova nulla (o il server
  non ha accesso a internet), viene semplicemente mostrato lo sfondo di
  default, senza errori. Puoi anche richiedere una nuova ricerca a mano
  dalla pagina di modifica del viaggio.
- **Conteggio parziale per bagaglio**: oltre ai conteggi generali, la
  carta d'imbarco mostra ora quante unità sono già state messe in
  valigia separatamente per ciascun bagaglio attivo (es. "In valigia —
  Stiva: 8", "In valigia — Cabina: 3").

### Altre modifiche tecniche

- Nuovi modelli dati: `TripShare` (condivisione), `Luggage` (valigie
  fisiche); nuovi campi: `User.role`/`active`, `BagType.short_label`,
  `Item.weight_grams`, `Luggage.*`, `Trip.cover_image_url`,
  `TripItem.missing_qty` (sostituisce il precedente `da_comprare`
  booleano).
- Nuovi comandi CLI: `flask list-users` (elenca gli utenti e i loro ID);
  `flask import-notion` ora richiede `--user-id` (ogni utente ha un
  catalogo separato).
- Suite di test estesa con verifiche specifiche di isolamento tra
  cataloghi di utenti diversi e di corretto funzionamento della
  condivisione dei viaggi.

### Limitazioni note / idee per versioni future

- La condivisione di un viaggio è "tutto o niente" (chi la riceve può
  modificare tutti gli oggetti): non ci sono ruoli di sola lettura.
- L'immagine di copertina non è caricabile manualmente (solo ricerca
  automatica su Wikipedia o nessuna immagine).
- Nessuna migrazione automatica dello schema database (vedi CONTEXT.md,
  sezione 8): ogni cambio di schema futuro richiede un intervento manuale
  o, in caso di cambi radicali come questo, un database nuovo.
