# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.8.0 — 6 settembre 2026 — Catalogo di base personalizzabile, rifiniture

### Nuovo: puoi personalizzare il catalogo di base

Un amministratore può ora curare il proprio catalogo (aggiungere,
modificare, rimuovere oggetti con tutte le loro impostazioni: regola
quantità, peso, tipologia di valigia predefinita) e poi promuoverlo a
nuovo "catalogo di base" con un pulsante ("Esporta come catalogo di
base", nella pagina Catalogo). Da quel momento, ogni nuovo utente e chi
preme "Importa catalogo di base" riceverà QUESTO catalogo, con tutte le
impostazioni preservate — non solo nome e categoria come nel catalogo
originale. Un pulsante "Ripristina originale" annulla la
personalizzazione, tornando al catalogo di base imbustato con l'app.
La personalizzazione è salvata nella cartella dati persistente, quindi
sopravvive agli aggiornamenti dell'app.

### Corretto e migliorato: diversi ritocchi visivi

- **Nome e peso delle valigie nella carta d'imbarco**: ora su righe
  separate per tutte le valigie, invece di condividere la stessa riga
  (il nome si tagliava se troppo lungo).
- **Rimossa la linea tratteggiata verticale** decorativa nel riquadro
  delle statistiche.
- **Icona aereo** per il pulsante "Viaggi" nel menu e "Tutti i viaggi",
  al posto della mappa.
- **Allineamento del riquadro "giorni alla partenza"**: numero e testo
  ora centrati correttamente l'uno rispetto all'altro.
- **Corretto**: il testo nei sotto-menu diventava illeggibile al passaggio
  del mouse, in tutti i menu a tendina del sito.
- **Pulsanti Modifica/Elimina con sfondo scuro** sulle card dei viaggi,
  per restare leggibili sopra una foto di copertina.
- **Icona cartella aperta** per il pulsante "Apri" di un viaggio.
- **Voce "Tutti"** aggiunta all'inizio delle schede per categoria (nel
  catalogo e nel workspace di un viaggio), per vedere tutte le
  categorie insieme invece di una alla volta.

### Nessuna azione richiesta per aggiornare

Solo interfaccia e una nuova funzione facoltativa: nessuna modifica
allo schema del database.
