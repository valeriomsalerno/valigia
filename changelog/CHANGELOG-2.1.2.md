# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.1.2 — 3 settembre 2026 — Correzione: errore Home/Viaggi per valigia eliminata

Versione correttiva, individuata grazie ai log reali forniti dall'utente
(`docker compose logs`), che hanno mostrato l'errore esatto:
`AttributeError: 'NoneType' object has no attribute 'tipologia'`.

### Corretto: errore aprendo Home o Viaggi dopo aver eliminato una valigia

**Causa reale**: eliminare una valigia (sezione Valigie) che era ancora
attiva in un viaggio non controllava questo caso: la riga che collega
quella valigia al viaggio restava "orfana" (con un riferimento a una
valigia ormai inesistente). SQLite non applica di default i vincoli di
integrità referenziale, quindi il problema passava inosservato al
momento dell'eliminazione — per poi far comparire l'errore ogni volta
che si apriva la Home o l'elenco Viaggi, cercando di leggere i dettagli
di quella valigia ormai sparita.

**Soluzione, su tre livelli**:
1. **Causa radice**: eliminare una valigia ora rimuove automaticamente
   anche i riferimenti ad essa in tutti i viaggi in cui era attiva (e le
   relative quantità), invece di lasciarli "orfani". Il messaggio di
   conferma prima dell'eliminazione lo segnala esplicitamente.
2. **Rete di sicurezza**: anche in presenza di un eventuale altro caso
   simile non ancora previsto, l'app ora ignora automaticamente i
   riferimenti a valigie inesistenti invece di bloccarsi con un errore.
3. **Riparazione automatica dei dati già interessati**: al primo avvio,
   un passaggio di pulizia rimuove in autonomia eventuali riferimenti
   già orfani presenti nel database — **non serve alcun intervento
   manuale**, l'aggiornamento ripara da solo la situazione.

Riprodotto fedelmente in un ambiente di test (stesso identico stato del
database, con una valigia eliminata ma ancora referenziata) e verificato
che, dopo l'aggiornamento, Home e Viaggi tornano a funzionare
correttamente e i dati validi restano intatti.

### Nessuna azione richiesta per aggiornare

La riparazione dei dati avviene automaticamente al primo avvio di questa
versione, come parte del normale sistema di migrazioni (vedi CONTEXT.md,
sezione 8).
