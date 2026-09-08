# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.7.1 — 4 settembre 2026 — Correzione: pallino lista della spesa nel viaggio

Versione correttiva: lo stesso identico bug del pallino "da comprare",
già risolto in passato per il menu in alto, era presente anche nella
scheda "Lista della spesa" dentro il workspace di un viaggio, mai
corretto lì.

### Corretto: il pallino non appariva subito e sembrava rotto

**Causa, in due parti**:
1. Lo stile di quel pallino specifico impostava SOLO il colore rosso,
   senza forma, dimensione o centratura del testo — appariva come un
   sottile trattino verticale invece che un cerchietto con il numero.
2. L'elemento esisteva nella pagina SOLO se il conteggio era già
   maggiore di zero al caricamento: aggiungendo il primo oggetto da
   comprare, il pallino non c'era ancora da aggiornare, e restava
   invisibile finché non si ricaricava la pagina a mano.

**Soluzione**: tutte le dimensioni/forma di questo tipo di pallino ora
vivono in un'UNICA regola di stile condivisa, usata sia dal menu in alto
sia da questa scheda (e da qualunque altro punto dell'app che ne avrà
bisogno in futuro, senza doverle reinventare). L'elemento è sempre
presente nella pagina (solo nascosto quando non serve), così si aggiorna
all'istante non appena qualcosa passa "da comprare", esattamente come
già succede nel menu in alto.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
