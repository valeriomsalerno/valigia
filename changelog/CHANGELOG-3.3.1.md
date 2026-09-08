# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.3.1 — 7 settembre 2026 — Correzioni alla finestra di scelta modello

### Corretto: "massimo qui" poteva restare sbagliato senza ricaricare

Se modificavi la quantità di un modello in una valigia e poi aprivi la
finestra per un'altra valigia dello stesso oggetto, senza ricaricare
la pagina, il numero "massimo qui" poteva restare quello vecchio,
non aggiornato. Ora si aggiorna sempre correttamente, in ogni valigia,
dopo ogni salvataggio. Il testo è anche più chiaro: mostra quanti ne
possiedi in totale, quanti sono già in un'altra valigia, e quanti ne
puoi mettere in questa.

Il limite resta comunque garantito anche nel caso limite più raro (es.
un collaboratore che modifica la stessa cosa in un altro dispositivo
nello stesso momento): il server verifica sempre da capo prima di
salvare, quindi non è mai possibile superare quanti ne possiedi
davvero.

### Corretto: errore di comunicazione incomprensibile

L'impostazione dei modelli era finita per errore tra le azioni che
possono funzionare offline — ma questa richiede sempre una risposta
completa e immediata dal server per calcolare correttamente il limite
tra più valigie. Un salvataggio "in sospeso" per la connessione dava
quindi un errore poco chiaro. Ora, se manca la connessione, l'errore è
esplicito e comprensibile.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
