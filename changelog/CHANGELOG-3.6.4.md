# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.4 — 8 settembre 2026 — Modifica tabella estesa, uscita solo manuale

### Corretto: la modalità modifica si chiudeva da sola dopo un trascinamento

Ora resta attiva finché non premi tu "Fine modifica" — puoi regolare
più colonne una dopo l'altra senza doverla riattivare ogni volta.

### Corretto: intestazione "Peso" allineata a destra per errore

Solo i numeri nelle righe restano allineati a destra (per staccarli
dalla colonna precedente); l'intestazione della colonna torna
allineata a sinistra come le altre.

### Nuovo: "Modifica tabella" anche per Valigie e Categorie

Lo stesso sistema di trascinamento a mano, salvataggio automatico e
modalità modifica è ora disponibile anche in queste due pagine, non
solo nel catalogo degli oggetti.

### Nuovo: il pulsante si nasconde da solo su mobile in modalità icone

Se la vista è impostata su "automatico" e lo schermo è stretto
abbastanza da mostrare le icone al posto del testo, "Modifica tabella"
sparisce (regolare colonne che in quel momento non mostrano testo non
avrebbe alcun effetto visibile). Torna a comparire su schermi larghi
o con la vista impostata esplicitamente su "solo testo".

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
