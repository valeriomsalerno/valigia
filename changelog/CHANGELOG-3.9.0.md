# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.9.0 — 13 settembre 2026 — Ordine categorie, "Indossa", Ricalcola completo

### Novità: le categorie si possono riordinare a mano

Mancava la possibilità di trascinare le categorie per riordinarle,
unico caso rimasto senza. Ora si trascinano in "Categorie" esattamente
come gli oggetti — e il nuovo ordine si vede subito sia nel catalogo
sia nella schermata di ogni viaggio.

### Novità: "Indossa" come posizione predefinita di un oggetto

Il campo "Tipologia di valigia predefinita" di un oggetto è diventato
"Posizione predefinita" e include ora anche "Indossa", per gli oggetti
che si portano addosso invece che in valigia (una giacca pesante, gli
occhiali). Se lo segni come indossato conta già come pronto; se invece
lo metti in una valigia vera, ricevi un avviso.

### Corretto: "Ricalcola" non aggiornava tutto quello che poteva

Il pulsante "Ricalcola" nella schermata di un viaggio aggiornava solo
le quantità automatiche. Ora aggiunge anche gli oggetti nuovi che hai
messo nel catalogo, rimuove quelli che hai archiviato nel frattempo, e
riallinea l'ordine degli oggetti a quello del catalogo.

### Verificato: eliminare un oggetto vale solo per te

Controllo esplicito su richiesta: eliminare un oggetto dal catalogo
elimina solo per chi lo fa, mai per gli altri collaboratori di un
viaggio condiviso — confermato con un test dedicato, nessuna modifica
necessaria perché il comportamento era già corretto.

Vedi `CONTEXT.md`, sezione 4.41, per i dettagli tecnici completi.
