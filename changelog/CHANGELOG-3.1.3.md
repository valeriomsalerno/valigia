# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.1.3 — 7 settembre 2026 — Correzione trascinamento e tabelle

### Corretto: il blocco trascinato appariva staccato dal puntatore

Più in basso nella pagina si iniziava a trascinare, più il blocco
appariva distante dal puntatore invece di seguirlo esattamente. Il
trascinamento ora segue il puntatore con precisione, a qualunque
altezza della pagina.

### Corretto: spaziatura irregolare nel menu mobile

I pulsanti "Catalogo" e "Impostazioni" avevano un'altezza e un bordo
diversi dagli altri link una volta impilati nel menu a comparsa su
mobile. Ora hanno lo stesso aspetto degli altri.

### Corretto: la stellina della valigia preferita spostata

Nella pagina "Le tue valigie", la stellina che segnala la valigia
attiva automaticamente sui nuovi viaggi è ora accanto al nome della
marca, invece di stare accanto alla tipologia (dove la spingeva fuori
centro).

### Migliorato: tabella del catalogo oggetti ribilanciata

Più spazio alla colonna "Nome", molto meno alla colonna "Peso" (il cui
contenuto è sempre breve). Le intestazioni delle colonne non vengono
più troncate quando lo spazio è stretto: vanno a capo su due righe
invece di tagliarsi con "...".

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
