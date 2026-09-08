# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.9.0 — 6 settembre 2026 — Correzione critica iOS, rifiniture catalogo

### Corretto: il menu era irraggiungibile installando l'app su iOS

**Causa**: la barra di stato di iOS era impostata come "trasparente
sovrapposta" (per un aspetto più simile a un'app nativa una volta
installata sulla schermata Home), ma la pagina non lasciava lo spazio
necessario perché il contenuto non finisse disegnato SOTTO la barra di
stato/notch — il menu in alto restava quindi nascosto dietro di essa e
non era più cliccabile. Corretto lasciando lo spazio corretto in cima
alla pagina; usando il sito da un browser normale (Safari, Chrome) non
cambia nulla, il problema riguardava solo l'app installata sulla
schermata Home.

### Migliorato: tabelle del catalogo più leggibili

- La colonna "Nome" ha ora la stessa larghezza in tutte le tabelle per
  categoria, invece di adattarsi al contenuto più lungo di ciascuna
  (che le disallineava tra loro).
- Più spazio tra la tabella di una categoria e quella successiva.
- Selezionando "Tutti", ogni tabella mostra ora il nome della propria
  categoria, con un bordo colorato coerente con quello già usato nelle
  schede sopra.

### Corretto: icone e pulsanti

- L'icona per tornare al Catalogo (dalla pagina di un oggetto) è ora un
  pacco, non più una freccia.
- Rimosso il pulsante "Nuovo viaggio" dal workspace di un viaggio (era
  fuori contesto lì).

### Nessuna azione richiesta per aggiornare

Solo interfaccia: nessuna modifica allo schema del database.

---

**Nota**: la richiesta di funzionamento offline (per l'uso in aereo o
senza connessione) è stata discussa ma non ancora implementata — vedi
la risposta in conversazione per le alternative possibili prima di
procedere.
