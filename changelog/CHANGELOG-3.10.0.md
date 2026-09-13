# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.10.0 — 13 settembre 2026 — Foto non ritagliate, icona per oggetti senza foto

### Corretto: la foto di un oggetto veniva ritagliata per riempire lo spazio

La foto di un oggetto o di un modello riempiva il riquadro dedicato
ritagliando le parti che non ci stavano. Ora l'immagine intera resta
sempre visibile, adattandosi senza deformarsi — vale anche per le
foto già caricate in precedenza, nessuna azione necessaria.

### Novità: icona per gli oggetti senza foto

Quando un oggetto non ha una foto caricata, ora puoi assegnargli
un'icona a scelta libera dal set [Lucide](https://lucide.dev/icons/) —
comparirà al posto della foto ovunque nell'app (catalogo, schermata di
un viaggio). La foto, quando presente, ha sempre la precedenza.

Vedi `CONTEXT.md`, sezione 4.44, per i dettagli tecnici completi.
