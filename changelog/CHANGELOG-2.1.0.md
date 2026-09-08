# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.1.0 — 3 settembre 2026 — Valigie come unico bagaglio, liste personali, backup

Versione maggiore, nata dall'uso reale della v2.0: corregge un problema
di fondo (la lista da mettere in valigia era condivisa tra i
collaboratori di un viaggio, quando invece deve essere personale) e
riorganizza l'app attorno alle valigie fisiche.

> **Aggiornamento automatico**: da questa versione in poi, **i tuoi dati
> sopravvivono agli aggiornamenti senza bisogno di alcun intervento
> manuale**. Un sistema di migrazioni leggere (vedi sezione "Persistenza
> dei dati" più sotto) converte da solo lo schema del database al primo
> avvio, preservando tutto. Non serve più cancellare `data/valigia.db`.

### Corretto: la lista da mettere in valigia ora è davvero personale

Prima di questa versione, su un viaggio condiviso tutti i collaboratori
vedevano e modificavano LE STESSE quantità e LO STESSO check "conservato":
se una persona segnava un calzino come già in valigia, lo vedeva segnato
anche l'altro. Ora ogni collaboratore ha la propria lista indipendente,
basata sul proprio catalogo personale — modificarla non tocca in alcun
modo quella degli altri. Restano condivisi solo: meta/date/note del
viaggio, e la lista della spesa (vedi sotto).

### Le valigie sono l'unico concetto di "bagaglio"

- Sparito il vecchio catalogo separato "Tipi di bagaglio": ora esiste solo
  la sezione **Valigie**, dove censisci le tue borse reali (marca, nome,
  **tipologia**: Cabina / Stiva / Zaino, peso a vuoto, capacità).
- Nella pagina "Valigie" di ogni viaggio scegli, per nome, quali delle
  tue valigie porti con te — ogni collaboratore gestisce le proprie,
  indipendentemente dagli altri (proprio come per la lista da mettere in
  valigia).
- Le valigie attive in un viaggio vengono sempre mostrate nell'ordine
  **Cabina → Stiva → Zaino**.
- La carta d'imbarco mostra ora, per ciascuna valigia attiva, quante
  unità sono già dentro e il **peso stimato totale** (contenuto + peso a
  vuoto della valigia).

### Home page completamente rifatta, a blocchi

La schermata iniziale non è più la lista di un singolo viaggio, ma un
riepilogo a blocchi: **Viaggi futuri** (largo), **Catalogo** e
**Valigie** (affiancati, metà larghezza ciascuno), **Viaggi passati**
(largo). Ogni viaggio ha ora un proprio indirizzo permanente
(`/viaggi/<id>`), quindi si può aprire direttamente o salvare come
segnalibro.

### Il workspace di un viaggio: due pannelli, meno scorrimento

- La schermata di un viaggio è organizzata in due schede: **Valigia**
  (la tua lista personale) e **Lista della spesa** (condivisa).
- Dentro il pannello Valigia, gli oggetti sono raggruppati in
  sotto-schede per categoria (Vestiti, Bagno...): se ne vede una alla
  volta, invece di scorrere una lunga lista con tutte le categorie una
  sotto l'altra.
- Nuovo **numero "obiettivo"** per ogni oggetto in un viaggio: la
  quantità totale che ti sei prefissato per quel viaggio (di norma
  precompilata dall'automazione), separata dalla distribuzione tra le
  valigie — utile ora che le valigie possono essere più di due.

### Lista della spesa: condivisa, ma divisa per chi compra

- La lista della spesa di un viaggio condiviso mostra un sotto-pannello
  per ciascun collaboratore, con gli acquisti a lui assegnati: puoi
  assegnare (o riassegnare) l'acquisto di un oggetto mancante a un altro
  collaboratore dal pannello di dettaglio dell'oggetto.
- Il link "Lista della spesa" nel menu ora apre un elenco AGGREGATO di
  tutti i tuoi viaggi con qualcosa ancora da comprare, ordinati dal più
  vicino al più lontano — non più legato a un solo "viaggio corrente".

### Persistenza dei dati tra gli aggiornamenti

- Aggiunto un sistema di migrazioni leggere (`app/migrations.py`): ad
  ogni avvio, se il database è ancora a uno schema precedente, viene
  aggiornato automaticamente SENZA perdere dati (aggiunge tabelle/colonne
  mancanti, non cancella né sovrascrive nulla che già esiste). Per questa
  versione, converte anche i vecchi "tipi di bagaglio" in valigie vere e
  attribuisce le vecchie liste condivise al proprietario del viaggio come
  punto di partenza.
- **Nuova sezione Backup** (menu, solo amministratore): un pulsante per
  scaricare l'intero database in un solo file, e uno per ripristinarlo
  (con copia di sicurezza automatica dei dati precedenti prima di
  qualunque ripristino). Vedi il README per impostare anche backup
  automatici periodici lato server.

### Corretto: condizione di corsa nell'avvio con più worker

- Con più di un worker gunicorn attivi (`--workers 2`, come da
  `entrypoint.sh`), al primissimo avvio su un database nuovo i worker
  potevano provare a creare le stesse tabelle nello stesso istante,
  facendo fallire l'avvio di uno di loro ("table already exists"). Ora
  la creazione delle tabelle, le migrazioni e i dati iniziali sono
  protetti da un lock di file (`data/.init.lock`), così solo un worker
  alla volta tocca lo schema. Scoperto lanciando l'app con gunicorn e
  più worker attivi (i test automatici, a processo singolo, non lo
  avrebbero mai fatto emergere).

### Altre modifiche

- Ogni utente ha ora **nome e cognome** oltre al nickname di accesso:
  modificabili dal proprio profilo (menu utente in alto) o dall'admin
  per chiunque, dalla sezione Utenti.
- **Corretto un bug del calendario**: scegliendo la data di partenza, la
  data di ritorno si preimposta automaticamente una settimana dopo (e non
  si può più scegliere un ritorno precedente alla partenza), così il
  calendario si apre già nel periodo giusto invece che sul mese corrente.
- **Corretto** il campo utente del login (e dei form utente) che su
  iOS proponeva la maiuscola come primo carattere.
- **Rifatta la navigazione mobile**: ora è un menu a comparsa (hamburger)
  che non occupa più metà schermo, e le righe di pulsanti che prima
  uscivano dai bordi dello schermo ora scorrono orizzontalmente.

### Note per chi aggiorna da versioni precedenti alla v2.1.0

Le vecchie liste condivise (uniche per tutto il viaggio) vengono
attribuite automaticamente al proprietario del viaggio: se avevi
condiviso un viaggio con qualcuno, quella persona partirà con una lista
personale vuota (sincronizzata dal proprio catalogo) la prima volta che
apre il viaggio — è una conseguenza diretta e voluta del fatto che ora
ognuno ha la propria lista, non un difetto della migrazione.

### Limitazioni note / idee per versioni future

- La condivisione resta "tutto o niente" (chi la riceve può modificare
  tutta la propria lista e la lista della spesa condivisa): nessun ruolo
  di sola lettura.
- Nessun upload manuale di immagine di copertina (solo ricerca automatica
  su Wikipedia).
- Il ripristino di un backup su un container con più worker (`--workers
  2` nell'entrypoint) richiede un riavvio (`docker compose restart`) per
  essere sicuri che tutti i processi vedano i dati appena ripristinati:
  l'interfaccia lo ricorda esplicitamente dopo ogni ripristino.
