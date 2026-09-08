# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.7 — 8 settembre 2026 — Il catalogo di base ora è quello vero

### Nuovo: il catalogo curato è imbustato nel codice

Da questa versione, `app/seed_data/catalogo_base.json` contiene
davvero il catalogo scelto — 5 categorie, 17 oggetti (inclusi i
Pantaloni con i loro 6 modelli specifici), e le due valigie reali.
D'ora in poi, ogni installazione fatta da zero da questo repository
riceve questo catalogo, non più quello generico originale. Verificato
avviando un'installazione completamente nuova: categorie, oggetti,
modelli e valigie sono tutti presenti correttamente.

### Corretto: un nuovo utente poteva ritrovarsi con valigie doppie

Le due valigie generiche di partenza venivano create sempre, prima di
importare il catalogo di base — quando quel catalogo include le
proprie valigie (come ora), questo produceva quattro valigie invece
di due. Corretto: le due generiche si creano solo se il catalogo
importato non ne porta già.

### Nessuna azione richiesta per aggiornare

Riguarda solo i NUOVI utenti creati da questo momento in poi (e le
nuove installazioni fatte da zero); il tuo account esistente e i tuoi
dati non vengono toccati in alcun modo.
