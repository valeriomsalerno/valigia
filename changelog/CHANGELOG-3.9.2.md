# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.9.2 — 13 settembre 2026 — Tre rifiniture sulla pagina di un oggetto

### Corretto: spaziatura tra "Modelli" e la frase informativa accanto

Il titolo e la descrizione a fianco erano troppo vicini, specialmente
quando la descrizione andava a capo.

### Novità: pulsanti di salvataggio anche in alto

"Salva oggetto", "Salva e vai al successivo" e "Annulla" comparivano
solo in fondo al modulo — con un modulo lungo, bisognava scorrere
fino in fondo solo per salvare. Ora ci sono anche in alto.

### Corretto: il browser suggeriva di compilare "Nome oggetto" come dato anagrafico

Il campo "Nome oggetto" veniva talvolta riconosciuto dal browser (o da
un'estensione) come un campo anagrafico o di accesso, proponendo il
completamento automatico. Disattivato esplicitamente su tutti i campi
del modulo.

Vedi `CONTEXT.md`, sezione 4.43, per i dettagli tecnici completi.
