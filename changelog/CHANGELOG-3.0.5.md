# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.5 — 6 settembre 2026 — Bordo di categoria risolto alla radice

### Corretto: il bordo di categoria era ancora staccato

Trovata finalmente la causa vera: un bordo colorato su un elemento con
angoli arrotondati non segue la curva dell'angolo, lasciando sempre un
piccolo vuoto proprio lì, a prescindere da qualunque margine interno.
Sostituito con una tecnica diversa (una barra colorata "incollata" al
bordo reale, non un bordo vero e proprio): ora resta sempre attaccato
al contenuto, in ogni condizione.

### Corretto: molte tabelle dell'app erano più strette del loro contenuto

**Causa**: una regola pensata solo per la tabella del catalogo oggetti
(colonne a larghezza fissa) era stata scritta in un punto che si
applicava a OGNI tabella dell'app — Utenti, Valigie, Condivisione,
Backup, Modelli di un oggetto — forzandole tutte dentro proporzioni
non pensate per loro. Corretto: solo la tabella del catalogo oggetti
ha colonne a larghezza fissa; tutte le altre si adattano di nuovo
liberamente al proprio contenuto, com'è giusto che sia.

### Corretto: tabella del catalogo oggetti troppo larga per la pagina

La colonna "Peso" occupava più spazio del necessario, facendo
traboccare l'intera tabella. Ristretta a una larghezza proporzionata
al suo contenuto (sempre breve).

### Corretto: tabella delle categorie, colonna Nome/Icona

La colonna "Icona" è più larga, quella "Nome" più contenuta — meno
spazio sprecato, più leggibilità.

### Corretto: lo switch icone/testo non rispettava la scelta esplicita

Impostare "sempre icone" o "sempre testo" (Impostazioni → Preferenze
catalogo) non cambiava nulla, restava sempre legato alla larghezza
dello schermo. Corretto: una scelta esplicita vince sempre.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
