# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.5 — 8 settembre 2026 — Correzione: "Modifica tabella" non faceva nulla

### Corretto: il pulsante su Valigie e Categorie era del tutto inerte

**Causa trovata**: quando ho esteso il sistema di trascinamento colonne
a queste due pagine, ho aggiunto pulsante e maniglie ma non il file che
li fa funzionare — premerlo non faceva letteralmente nulla, nessun
separatore compariva. Corretto: ora funziona in entrambe le pagine
esattamente come nel catalogo.

### Corretto: allineamento della colonna Peso

Anche i valori nelle righe (non solo l'intestazione) tornano allineati
a sinistra come le altre colonne, su tua richiesta.

### Corretto: colonna "Oggetti" nelle Categorie allineata a sinistra

Sia l'intestazione sia i numeri nelle righe.

### Corretto: poco spazio sotto la barra con "Modifica tabella"

Ora c'è sempre un margine adeguato prima di qualunque cosa segua,
tabella inclusa.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
