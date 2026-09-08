# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.0.1 — 3 settembre 2026 — Numero di versione visibile

Piccola versione correttiva, nata da una domanda molto concreta: "come
faccio a controllare che l'app sia aggiornata?". Prima di questa
versione non c'era alcun modo di saperlo guardando il browser.

### Novità

- **Numero di versione sempre visibile**: in fondo a ogni pagina (anche
  nella schermata di login, quindi controllabile SENZA fare accesso)
  compare ora "Valigia v2.0.1". Da qui in avanti, dopo ogni
  `docker compose up -d --build`, puoi verificare a colpo d'occhio se il
  container è stato davvero ricostruito con l'ultima versione.
- **Cache-busting dei file statici**: il foglio di stile e gli script
  JavaScript vengono richiesti con `?v=2.0.1` in coda all'indirizzo.
  Cambiando il numero di versione ad ogni release, browser e — cosa
  importante se usi Cloudflare davanti al tunnel — anche la cache di
  Cloudflare non mostreranno più CSS/JS vecchi dopo un aggiornamento.

### Come verificare che un aggiornamento sia andato a buon fine

1. Controlla il numero in fondo alla pagina di login: deve corrispondere
   alla versione che hai appena installato (vedi cima di questo file).
2. Se è ancora quello vecchio, quasi sempre la causa è una di queste:
   - il container non è stato ricostruito per davvero: usa
     `docker compose up -d --build` (non basta `docker compose up -d` o
     `restart`, che riusano l'immagine già costruita);
   - il vecchio `data/valigia.db` non è stato eliminato prima
     dell'aggiornamento alla v2.0.0 (vedi changelog di quella versione):
     con uno schema incompatibile l'app può comportarsi in modo
     imprevedibile;
   - il browser (o Cloudflare) sta ancora mostrando una pagina in cache:
     prova un refresh forzato (Ctrl+Shift+R / Cmd+Shift+R) e, se usi
     Cloudflare con il proxy attivo (nuvoletta arancione), uno
     "svuota cache" dal pannello Cloudflare per il tuo dominio.

### Nessuna modifica al modello dati

Questa versione non tocca lo schema del database: se vieni dalla
v2.0.0 NON serve eliminare `data/valigia.db`.
