# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.4.0 — 4 settembre 2026 — Distribuzione sempre manuale, indosso a quantità, catalogo a schede

Versione nata da un uso reale approfondito, con due bug che sembravano
di isolamento tra utenti (e invece non lo erano) e diverse richieste di
miglioramento mirate.

### Corretto: le unità da acquistare restavano bloccate a 1

**Causa**: il numero "da comprare" era limitato al valore già presente
nelle valigie (con un minimo di 1) — se non avevi ancora messo nulla in
una valigia per quell'oggetto, restavi bloccato a 1, qualunque numero
scrivessi. Chi condivide il viaggio e ha già smistato qualche quantità
non se ne accorgeva, dando l'impressione (falsa) di un problema legato
all'utente. Rimosso il limite: ora si può segnare qualunque quantità da
comprare, a prescindere da cosa c'è già nelle valigie.

### Corretto: il totale "in valigia" nel riepilogo era sottostimato

**Causa**: il conteggio per ciascuna valigia sommava solo gli oggetti il
cui obiettivo era già stato raggiunto, invece di sommare semplicemente
tutto ciò che è fisicamente in quella valigia. Chi ha molti oggetti con
quantità già inserite ma obiettivo non ancora raggiunto vedeva un
totale molto più basso del reale. Ora somma sempre tutto, senza filtri.

### Cambiato: la distribuzione tra le valigie non è più automatica

L'automazione (regole Fissa/Per giorno) ora determina **solo**
l'obiettivo per il viaggio: la distribuzione tra le valigie parte
sempre da zero e va sempre compilata a mano. Prima, creando un nuovo
viaggio, gli oggetti finivano automaticamente in una valigia scelta
dal sistema in base alla "tipologia predefinita" — comportamento non
voluto, ora rimosso.

Di conseguenza, la **tipologia di valigia predefinita** di un oggetto
(nel Catalogo) cambia scopo: non pre-compila più nulla, vale per
qualunque regola quantità (non solo Fissa/Per giorno) e serve solo a
mostrare un piccolo avviso se quell'oggetto finisce in una valigia di
tipologia diversa da quella indicata — mai un blocco, solo un
promemoria visivo.

### Nuovo: "indosso direttamente" ora è una quantità, non un sì/no

Non si possono indossare 13 paia di boxer contemporaneamente: ora si
specifica **quante** unità di un oggetto si indossano direttamente
(invece di metterle in valigia), con un piccolo stepper dedicato che si
somma alle quantità nelle valigie per raggiungere l'obiettivo.
L'etichetta di stato distingue i tre casi: **"In valigia"** (solo nelle
valigie), **"Da indossare"** (tutto indossato, niente in valigia),
**"In valigia / da indossare"** (un misto dei due).

### Nuovo: catalogo con schede per categoria

La pagina del catalogo oggetti ora usa lo stesso sistema a schede
cliccabili già presente nel workspace di un viaggio, invece di un menu
a tendina che ricaricava la pagina ad ogni cambio di categoria.

### Corretto: alcuni dettagli dell'interfaccia

- Il riepilogo per valigia nella carta d'imbarco è stato riorganizzato
  in piccole card compatte (tipologia in evidenza, nome completo e peso
  su riga secondaria): prima, con nomi commerciali lunghi, il testo
  andava a capo in modo scomposto e poco leggibile.
- La riga di pulsanti che scorre orizzontalmente su mobile ora sfuma
  visivamente l'ultimo elemento invece di tagliarlo di netto, così è
  chiaro che si può scorrere oltre.

### Cambiato: sessione più lunga

**Bug reale**: la durata del cookie "ricordami" era impostata con un
nome di configurazione che Flask-Login non legge affatto — non aveva
mai avuto alcun effetto, e senza spuntare "ricordami" la sessione
scadeva in fretta (specialmente su iOS). Corretto: ora ogni sessione
dura 180 giorni, sempre, senza dover spuntare nulla (la casella
"ricordami" è stata rimossa dal login perché non più necessaria — è
un'app ad uso familiare, non serve più sicurezza di così).

### Nuovo: sezione "Risorse del sistema" (solo amministratore)

Nella pagina Backup, un nuovo pannello mostra memoria e CPU usate dal
processo, CPU/memoria/disco della macchina, e la dimensione della
cartella dati — utile per capire a colpo d'occhio se l'app sta
consumando più del previsto.

### Nessuna azione richiesta per aggiornare

La rinomina del campo "indossato" (da sì/no a quantità) avviene
automaticamente al primo avvio, preservando i valori esistenti (un
"sì" diventa "1 indossato", un "no" diventa "0").
