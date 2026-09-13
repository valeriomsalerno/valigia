# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.9.1 — 13 settembre 2026 — "Torna al catalogo" non è più un "Indietro"

### Corretto: bug grave — "Torna al catalogo" si comportava come Indietro del browser

"Torna al catalogo" (e con lui "Salva oggetto" e "Annulla") seguiva
l'ultima pagina visitata invece di portare sempre nello stesso punto
prevedibile. Ora è sempre un link fisso al catalogo vero e proprio,
ancorato esattamente alla riga dell'oggetto da cui si è partiti: il
browser scorre da solo fino al punto giusto, evidenziandolo per un
istante.

Vedi `CONTEXT.md`, sezione 4.42, per i dettagli tecnici completi.
