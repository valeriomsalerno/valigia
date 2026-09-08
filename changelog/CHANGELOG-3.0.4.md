# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.0.4 — 6 settembre 2026 — Bordo attaccato, icone libere, tabelle

### Corretto: il bordo di categoria era staccato dalla tabella

Un margine interno lasciava uno spazio vuoto tra la linea colorata e le
righe della tabella, facendola sembrare una linea a parte invece che il
bordo della tabella stessa. Ora è sempre attaccato, sia nel catalogo
sia nel workspace di un viaggio.

### Cambiato: nessun suggerimento per le icone, solo scelta libera

Le icone per regola quantità e tipologia di valigia (Impostazioni →
Preferenze catalogo) erano proposte da un elenco limitato: ora sono un
campo di testo libero, dove scrivi il nome di qualunque icona da
lucide.dev tu preferisca, senza alcun vincolo. Le icone delle categorie
erano già così.

### Corretto: tabella delle categorie sfasata

Le colonne "Colore" e "Icona" occupavano troppo spazio rispetto al
contenuto: ora hanno una larghezza fissa e proporzionata, lasciando più
spazio al nome della categoria.

### Corretto: bordo della card sovrapposto al pulsante Archivia

In tutte le tabelle del catalogo (oggetti e categorie), un piccolo
spazio a destra impedisce ora che il bordo arrotondato della card si
sovrapponga al pulsante nell'ultima colonna.

### Cambiato: icona del menu Catalogo

Sostituita con un'icona di libreria, più rappresentativa.

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.
