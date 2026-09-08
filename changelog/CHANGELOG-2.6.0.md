# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.6.0 — 4 settembre 2026 — Valigie condivise, copertina personalizzabile

### Nuovo: valigie condivise tra collaboratori di un viaggio

Puoi condividere una delle tue valigie con un altro collaboratore del
viaggio: chi la riceve può mettere le PROPRIE cose dentro, anche oggetti
che tu non hai nel tuo catalogo. Il peso e il conteggio "in valigia"
sommano automaticamente il contributo di tutti quelli che condividono
quella valigia, con un'icona dedicata che la segnala nella carta
d'imbarco. Si condivide dalla pagina "Le tue valigie" del viaggio, con
un semplice segno di spunta per ciascun collaboratore.

### Nuovo: immagine di copertina, termini di ricerca e caricamento manuale

- **Termini di ricerca personalizzati**: se la ricerca automatica basata
  sulla meta non trova l'immagine giusta, puoi indicare termini più
  precisi (es. "Torre Eiffel" invece della sola "Parigi").
- **Caricamento di una tua immagine**: puoi caricare una foto dal tuo
  computer invece di affidarti alla ricerca automatica, e trascinarla
  nel riquadro per inquadrarla esattamente come preferisci (funziona
  anche su schermi touch).

### Nuovo: navigazione tra oggetti del catalogo

Nella pagina di modifica di un oggetto, due pulsanti portano
all'oggetto precedente e successivo della STESSA categoria (nascosti
automaticamente agli estremi). "Salva" ora resta sulla pagina di
modifica invece di portarti altrove, per poter scorrere e sistemare più
oggetti in sequenza senza dover tornare ogni volta al catalogo.

Aggiunto anche un pulsante "Torna al viaggio" nella pagina di un
oggetto, quando ci si arriva da "Vai alle impostazioni dell'oggetto"
dentro un viaggio.

### Corretto: il numero "da comprare" non appariva subito

**Causa**: il pallino con il numero di oggetti da comprare, nel menu in
alto, esisteva nella pagina SOLO se al caricamento c'era già qualcosa
da comprare. Se aprivi una pagina senza nulla da comprare e poi
aggiungevi il primo oggetto alla lista della spesa, non c'era alcun
elemento da aggiornare: il pallino restava invisibile finché non
ricaricavi la pagina a mano. Ora l'elemento è sempre presente (solo
nascosto quando non serve), pronto per apparire all'istante.

### Corretto: menu utente duplicato su mobile

I pulsanti Profilo ed Esci comparivano sia nell'icona utente sia
duplicati nel menu a comparsa mobile. Ora l'icona utente in alto a
destra è l'unico punto d'accesso, sempre visibile e funzionante a
qualunque larghezza di schermo.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge le tabelle/colonne necessarie
alla condivisione delle valigie e alla copertina personalizzata, senza
alcuna perdita di dati esistenti.
