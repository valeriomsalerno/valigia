# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v1.0.0 — 3 settembre 2026 — Prima versione

Prima release funzionante della piattaforma, in sostituzione della
gestione precedente su Notion.

### Funzionalità principali

**Dashboard principale**
- Vista unica con tutti gli oggetti del viaggio selezionato, raggruppati per categoria.
- Colorazione immediata dello stato di ogni oggetto: verde (già in valigia),
  rosso (da comprare), giallo (da preparare), grigio (non necessario per
  questo viaggio, quantità a 0).
- Modifica "al volo" senza ricaricare la pagina: quantità per ogni
  bagaglio (steppers +/-), check "conservato" (già fatto in valigia) e
  flag "da comprare", con micro-animazioni di conferma.
- Ricerca per nome, filtro per categoria, filtro per stato (pillole cliccabili).
- Carta d'imbarco in testata con meta, date, giorni alla partenza,
  percentuale di preparazione e conteggi rapidi.
- Pannello di dettaglio (drawer laterale) per ogni oggetto: spiega
  l'automazione applicata, permette di scrivere una nota libera per quel
  viaggio e mostra lo storico d'uso negli altri viaggi.

**Catalogo (categorie, oggetti, tipi di bagaglio)**
- Categorie di oggetti completamente personalizzabili (nome, colore, icona).
- Tipi di bagaglio gestibili liberamente: di default "Valigia da stiva" e
  "Bagaglio a mano / cappelliera", ma se ne possono aggiungere altri
  (zaino, trolley extra…) e attivarli solo sui viaggi che li usano.
- Oggetti di catalogo con tre regole di automazione della quantità:
  - **Manuale**: quantità impostata a mano ogni volta.
  - **Fissa**: sempre lo stesso numero (es. iPhone, patente → 1).
  - **Per giorno**: giorni di viaggio + una scorta extra (es. calzini,
    mutande → giorni + 1).
- Archiviazione (nascondere senza perdere lo storico) o eliminazione
  definitiva (solo se l'oggetto non è mai stato usato in nessun viaggio).
- Un nuovo oggetto di catalogo compare automaticamente in tutti i viaggi
  già esistenti, con la quantità calcolata secondo la sua regola.

**Viaggi**
- Creazione di più viaggi, ciascuno con meta, date di partenza/ritorno
  (i "giorni di viaggio" si calcolano automaticamente dalle date) e note.
- Ogni viaggio ha le proprie borse attive e le proprie quantità per
  oggetto, completamente indipendenti dagli altri viaggi.
- Opzione "copia dall'ultimo viaggio" alla creazione di un nuovo viaggio:
  eredita quantità, note e "da comprare" (il check "conservato" riparte
  sempre da zero, dato che si riparte a fare le valigie da capo).
- Pulsante "Ricalcola automazioni": aggiorna le quantità degli oggetti a
  regola Fissa/Per giorno (utile se le date del viaggio cambiano — la
  modifica delle date lo fa già scattare in automatico).

**Lista della spesa**
- Elenco dedicato di tutti gli oggetti segnalati "da comprare" per il
  viaggio corrente, con azione rapida "Acquistato" per toglierli.

**Accesso e sicurezza**
- Login con utente amministratore unico (default `admin` / `admin`,
  configurabile via `.env`).
- Cambio password obbligatorio al primo accesso: nessun'altra pagina è
  raggiungibile finché la password di default non viene sostituita.
- Protezione CSRF su tutte le richieste che modificano dati.

**Importazione da Notion**
- Comando `flask import-notion <csv>` (o `python scripts/import_notion.py`)
  per importare il database "Lista" esportato da Notion: crea le
  categorie e gli oggetti di catalogo e, se indicato un viaggio di
  destinazione, anche le quantità e gli stati per quel viaggio.
- Riconoscimento automatico (con possibilità di correzione manuale) delle
  regole di automazione per gli oggetti più comuni (mutande/calze → per
  giorno; iPhone/passaporto/patente/tessera sanitaria → fissa 1).

**Grafica**
- Identità visiva ispirata ai documenti di viaggio: carta d'imbarco
  perforata per il riepilogo del viaggio, etichette da bagaglio per le
  categorie, palette blu notte / ottone / avorio, font Fraunces (titoli)
  + Inter (corpo).
- Completamente responsive: utilizzabile da Mac, iPhone e iPad.
- Installabile come app dalla schermata Home su iOS/iPadOS (manifest PWA
  + icone dedicate).

**Infrastruttura**
- App Flask containerizzata con Docker, pensata per essere esposta tramite
  Cloudflare Tunnel su `127.0.0.1:4825`.
- Database SQLite persistente su volume Docker (`./data`).
- Suite di test automatici (`pytest`) che copre le automazioni di
  quantità, la sincronizzazione catalogo/viaggi e un percorso end-to-end
  attraverso tutte le pagine principali e le API.

### Limitazioni note / idee per versioni future
- Il flag "da comprare" è per-viaggio (non un possesso globale
  dell'oggetto): se un oggetto manca a prescindere dal viaggio, va
  rispuntato ad ogni nuovo viaggio. Può diventare un'impostazione globale
  in una versione futura, se utile nell'uso reale.
- Nessuna gestione multi-utente: l'app è pensata per un solo
  amministratore.
- Nessuna migrazione database automatica (Flask-Migrate): eventuali
  cambi di schema futuri andranno gestiti manualmente (vedi CONTEXT.md).
- Nessun upload di foto per gli oggetti.
- Nessun ordinamento/trascinamento manuale delle categorie dall'interfaccia
  (il campo esiste nel database ma va impostato via script/DB).

---

*Changelog precedenti: nessuno (questa è la prima versione). Le versioni
future troveranno qui l'elenco delle release precedenti — vedi
`changelog/README.md`.*
