# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.1.1 — 3 settembre 2026 — Correzioni: pagina non disponibile, numeri decimali

Versione correttiva, nata da due segnalazioni precise: un errore
"Qualcosa è andato storto" cliccando su Home o Viaggi, e l'impossibilità
di salvare il nome di una valigia scrivendo il peso con la virgola.

### Corretto: errore intermittente aprendo Home o Viaggi

**Causa probabile**: SQLite, nella sua modalità di funzionamento di
default, blocca le operazioni di LETTURA quando c'è una SCRITTURA in
corso sullo stesso database. Con più worker gunicorn attivi (come da
`entrypoint.sh`), aprire la Home o l'elenco Viaggi mentre un'altra
richiesta stava ancora salvando una modifica (es. la modifica di una
valigia) poteva quindi fallire con un errore generico.

**Soluzione**: attivata la modalità **WAL** (Write-Ahead Logging) di
SQLite, che permette letture concorrenti anche mentre è in corso una
scrittura, più un margine di attesa (`busy_timeout`) per i rari casi di
contesa residua. Verificato con un test di carico reale: 120 richieste
di lettura e scrittura lanciate in parallelo su 3 worker, zero errori
(prima di questa correzione, questo tipo di test non era nemmeno
possibile eseguirlo in modo affidabile). Aggiornata di conseguenza anche
la procedura di ripristino da backup, che ora ripulisce anche gli
eventuali file di supporto della modalità WAL rimasti dal database
precedente, per evitare rischi di corruzione dei dati appena ripristinati.

### Corretto: le modifiche a una valigia (o a un oggetto) potevano non
### salvarsi SENZA alcun errore visibile

**Causa**: i campi numerici decimali (peso, capacità) accettavano SOLO il
punto come separatore decimale ("3.2"), in contraddizione con come
questi stessi numeri vengono MOSTRATI nell'app (con la virgola, stile
italiano). Chi scriveva "2,5" per abitudine (o seguendo la convenzione
internazionale corretta: punto per le migliaia, virgola per i decimali)
falliva la validazione — e quel fallimento non veniva mostrato da
nessuna parte: il modulo tornava silenziosamente alla stessa pagina,
dando l'impressione che il nome (o qualunque altro campo) "non si
salvasse".

**Soluzione, secondo la convenzione internazionale corretta** (non una
semplice tolleranza punto-o-virgola):
- Nei campi peso e capacità, **il punto è sempre il separatore delle
  migliaia** e **la virgola è sempre quella dei decimali** — es. "1.500"
  significa milleecinquecento, "1.500,25" significa milleecinquecento
  virgola venticinque.
- Anche i numeri già salvati si ripresentano nel modulo secondo questa
  stessa convenzione quando li riapri per modificarli, così ridigitare
  senza cambiare quel campo non corrompe mai più il valore.
- Aggiunta la visualizzazione dell'errore per OGNI campo dei moduli
  Valigia e Oggetto: se in futuro capita un altro problema di
  validazione, comparirà sempre un messaggio chiaro, invece di un
  fallimento silenzioso.
- La visualizzazione dei numeri nell'app (liste, dettagli) ora raggruppa
  anch'essa le migliaia con il punto, in modo coerente.

Riprodotto e corretto rilanciando lo scenario esatto descritto
(rinominare "Bagaglio a mano" impostando un peso con la virgola), con
verifica end-to-end anche del "giro completo" (salvare, riaprire,
risalvare senza modifiche) per essere certi che nessun valore venga mai
alterato inavvertitamente.

### Nessuna modifica al modello dati

Questa versione non tocca lo schema del database: nessuna azione
richiesta per aggiornare.
