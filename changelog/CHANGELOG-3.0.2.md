# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.2 — 6 settembre 2026 — Icone personalizzabili, correzioni

### Corretto: si poteva portare più unità di un modello di quante possedute

Impostando ad esempio 2 camicie bianche possedute, ora non è più
possibile segnare di portartene 3 in valigia: lo stepper si ferma al
posseduto, e un messaggio chiaro spiega perché.

### Corretto: bordo colorato per categoria nel workspace di un viaggio

Ripristinato: bordo sinistro colorato per categoria e sfumato colorato
per stato di ciascun oggetto convivono, come nel catalogo — erano stati
rimossi per un malinteso nella versione precedente.

### Corretto: il bordo della card sovrapposto al pulsante Archivia

Su schermi stretti, la tabella del catalogo può risultare più larga
della card che la contiene: ora scorre orizzontalmente invece di
tagliare via il pulsante.

### Nuovo: icone al posto del testo nelle colonne del catalogo

Da Impostazioni → Preferenze catalogo, puoi scegliere se le colonne
"Regola quantità", "Valigia predefinita" e "Peso" mostrino icone o
testo (automatico: icone su mobile, testo su desktop), e quale icona
usare per ciascuna regola quantità e tipologia di valigia, con
anteprima immediata.

### Migliorato: più chiaro come attivare i modelli di un oggetto

Dalla pagina di modifica di un oggetto, un pulsante "Modelli e
dettagli" porta dritto alla sezione giusta, con un suggerimento
esplicito nel campo peso (diverso se l'oggetto è nuovo o già
esistente); nel catalogo, un'iconcina segnala quali oggetti hanno già
dei modelli definiti.

### Cambiato: preparazione per l'uso offline solo su richiesta

Il precaricamento automatico dei viaggi (ad ogni apertura di Home o
Viaggi) è stato rimosso: consumava dati e batteria anche quando non
serviva. Al suo posto, un pulsante "Prepara per l'uso offline" in Home
precarica tutte le pagine principali in un colpo solo, con conferma di
quante ne sono state salvate.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge le preferenze del catalogo,
senza alcuna perdita di dati esistenti.
