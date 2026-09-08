# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.3 — 8 settembre 2026 — Il catalogo pubblico ora può arrivare su GitHub

### Corretto: il catalogo curato non poteva mai raggiungere una nuova installazione da GitHub

Fino a questa versione, il file generato da "Configura catalogo
pubblico" viveva solo nella cartella dati della tua installazione —
mai nel codice, quindi mai su GitHub. Un push "così com'è" avrebbe
sempre dato, a chiunque clonasse il repository, il vecchio catalogo
generico originale, indipendentemente da quanto lavoro avessi fatto
con le spunte.

Ora, il file scaricato con "Scarica il file" può sostituire
direttamente il vecchio catalogo imbustato nel codice: salvalo come
`app/seed_data/catalogo_base.json` e committalo — nessuna conversione
necessaria, è già nel formato giusto. Da quel momento, chiunque installi
il progetto da zero da quel repository riceve il tuo catalogo curato,
non più quello originale. La pagina "Catalogo pubblico" ora lo spiega
direttamente, con il percorso esatto da usare.

Verificato avviando un server completamente da zero con un catalogo di
prova imbustato: il primo utente ha ricevuto correttamente quel
catalogo, non più quello originale.

### Nessuna azione richiesta per aggiornare

Solo un nuovo livello di ricerca del file, in aggiunta a quelli
esistenti: nessuna modifica allo schema del database, nessuna perdita
di dati.
