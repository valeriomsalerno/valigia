# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.2.0 — 3 settembre 2026 — Stato automatico, riordino, lista spesa live

Versione nata da un uso reale intenso dell'app, con due bug critici di
salvataggio segnalati ("i numeri non si aggiornano", "non trovo i valori
che avevo inserito") e una decina di richieste di miglioramento mirate.

### Corretto: salvataggi che sembravano riusciti ma non lo erano

**Causa più probabile**: se una richiesta di salvataggio falliva per un
problema di rete (frequente su mobile) o il server rispondeva con
qualcosa di diverso da JSON valido, il codice non gestiva il fallimento
in alcun modo — il numero restava visibile sullo schermo (perché
aggiornato subito, in modo "ottimista", prima ancora di sapere se il
salvataggio sarebbe riuscito) ma non veniva mai davvero salvato.
Ricaricando la pagina, quel valore spariva.

**Soluzione**: riscritta la gestione di tutte le chiamate di salvataggio
al volo (quantità, obiettivo, mancante):
- un fallimento di rete o una risposta non valida vengono ora sempre
  gestiti esplicitamente, non più ignorati in silenzio;
- se un salvataggio fallisce, il numero torna automaticamente
  all'ultimo valore CONFERMATO dal server (mai più un numero "fantasma"
  che sembra salvato ma non lo è) e compare una notifica visibile in
  basso sullo schermo;
- aggiunta una protezione contro le risposte del server che arrivano
  "fuori ordine" per via della rete (es. premendo + più volte molto
  velocemente): una risposta superata da una più recente viene ignorata,
  non sovrascrive mai un valore già più aggiornato.

### Nuovo: lo stato di un oggetto è ora interamente automatico

Non c'è più un check manuale "conservato" da spuntare a parte. Il colore
di ogni oggetto è determinato SOLO da obiettivo e quantità nelle valigie:

- **grigio** ("non necessario") — nessun obiettivo impostato per questo viaggio;
- **giallo** ("da preparare") — obiettivo impostato, ma la somma nelle
  valigie non lo raggiunge ancora;
- **verde** ("in valigia") — la somma nelle valigie ha raggiunto (o
  superato) l'obiettivo;
- **rosso** ("da comprare") — mantiene sempre la priorità più alta,
  qualunque sia lo stato delle quantità.

Se la somma nelle valigie supera l'obiettivo, la riga resta verde ma
compare un piccolo avviso ("oltre l'obiettivo") accanto agli steppers.

### Nuovo: riordino trascinabile degli oggetti

Dentro ciascuna categoria, nel workspace di un viaggio, gli oggetti si
possono ora riordinare trascinandoli (funziona anche su schermi touch,
iOS incluso). L'ordine è quello del catalogo: si riflette ovunque gli
oggetti compaiono raggruppati per categoria. Spostare un oggetto in
un'ALTRA categoria resta possibile solo dal Catalogo, non trascinandolo.
Il riordino è disponibile solo nella vista completa (senza filtri di
ricerca o di stato attivi), per evitare ambiguità.

### Nuovo: lista della spesa aggiornata all'istante

Segnare un oggetto come "da comprare" (o il contrario) aggiorna subito
il pannello Lista della spesa, senza ricaricare la pagina. Anche il
pulsante "Acquistato" ora agisce così, invece di ricaricare l'intera
pagina come prima.

**Bonus trovato per strada**: il menu per riassegnare l'acquisto a un
altro collaboratore, nella lista della spesa, non era collegato a
*nessuno script*: cambiarlo non aveva alcun effetto. Corretto.

### Nuovo: switch "nascondi già in valigia"

Nel workspace di un viaggio, un interruttore nasconde dalla vista gli
oggetti già verdi (obiettivo raggiunto), per concentrarsi su ciò che
resta da fare.

### Corretto: alcuni dettagli dell'interfaccia

- L'etichetta di ogni valigia negli steppers mostra ora solo la
  tipologia (Cabina/Stiva/Zaino) invece del nome completo della valigia,
  spesso troppo lungo per lo spazio disponibile (il nome completo resta
  visibile passandoci sopra).
- Corretta la visualizzazione dei numeri a due cifre negli steppers, che
  in alcuni casi apparivano tagliati.
- Su iOS, premere velocemente + o − più volte non attiva più
  accidentalmente lo zoom della pagina.

### Nessuna azione richiesta per aggiornare

Questa versione aggiunge un nuovo campo al catalogo (`items.sort_order`,
per il riordino manuale) tramite una migrazione automatica che non
tocca in alcun modo i dati esistenti: nessuna azione richiesta.
