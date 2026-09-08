# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.1.0 — 7 settembre 2026 — Tabelle davvero responsive, ordinamento separato

### Nuovo: tutte le tabelle dell'app ora si adattano davvero al mobile

Dopo diversi tentativi di correggere solo le larghezze delle colonne
(mai risolutivi fino in fondo, perché i pulsanti hanno una dimensione
minima che nessuna percentuale stretta può rispettare su schermi
piccoli), la soluzione definitiva: sotto una certa larghezza, ogni riga
di una tabella diventa una scheda verticale con etichetta e valore
affiancati, invece di colonne compresse. Applicato a tutte le tabelle
dell'app — catalogo oggetti, categorie, valigie, valigie del viaggio,
utenti, condivisione, backup, modelli di un oggetto.

### Nuovo: ordinamento del catalogo separato da quello dei singoli viaggi

**Corretto un bug reale**: riordinare gli oggetti dentro un viaggio
cambiava prima l'ordine anche nel catalogo e in tutti gli altri
viaggi (un unico campo condiviso). Ora un nuovo viaggio eredita
l'ordine attuale del catalogo come punto di partenza, ma da lì in poi
resta libero: riordinare dentro un viaggio non tocca più né il
catalogo né altri viaggi. Il catalogo ha ora i propri pulsanti per
spostare un oggetto su o giù dentro la sua categoria.

### Nuovo: collegamento diretto al tuo prossimo viaggio

Nel menu in alto, un collegamento porta direttamente al viaggio più
vicino alla partenza (se ne hai uno non ancora concluso).

### Cambiato: l'avviso delle modifiche offline non copre più il menu

Sostituito con un piccolo pallino numerato accanto al logo: il
dettaglio compare in un popover al tocco, senza più rendere il menu
inutilizzabile su mobile.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge il campo di ordinamento per
viaggio, ereditando l'ordine attuale del catalogo per tutti i viaggi
già esistenti — nessuna perdita di dati.

---

**Nota**: il riordino delle voci del menu in alto dalle impostazioni,
richiesto insieme al resto di questa lista, non è ancora stato
implementato — arriverà in una prossima versione.
