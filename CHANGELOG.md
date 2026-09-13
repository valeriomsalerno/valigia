# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.11.1 — 13 settembre 2026 — Icone Lab corrette, Safari e "Nome oggetto"

### Corretto: le icone "Lab" (es. luggage-cabin, shorts-boxer) non apparivano

Un errore nel modo in cui erano salvate internamente le 357 icone
"Lab" impediva a Lucide di trovarle. Ora funzionano correttamente.

### Corretto: Safari suggeriva ancora "Compilazione automatica" su "Nome oggetto"

Il tentativo precedente non era sufficiente per Safari. Cambiato
anche l'attributo che identifica il campo, oltre a rafforzare la
disattivazione dei suggerimenti automatici della tastiera.

Vedi `CONTEXT.md`, sezione 4.46, per i dettagli tecnici completi.
