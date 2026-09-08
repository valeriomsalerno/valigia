# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v3.6.0 — 8 settembre 2026 — Larghezza colonne e catalogo pubblico/privato

### Nuovo: regola a mano la larghezza delle colonne del catalogo

Trascina il bordo di un'intestazione (nella tabella Oggetti, vista
testo) per regolare quanto spazio occupa ciascuna colonna. Si salva da
solo e resta come tuo default, finché non lo ritocchi di nuovo. Non
serve con le icone, dove le colonne sono già strette per definizione.

### Nuovo: scegli cosa condividere del tuo catalogo

Ogni oggetto, categoria e valigia ha ora una spunta (l'icona a forma
di globo) per includerlo nel catalogo PUBBLICO esportabile. Tutto
parte privato: scegli tu, uno per uno, cosa rendere pubblico. Da
Catalogo → Oggetti, "Esporta come catalogo di base" genera un file con
solo ciò che hai spuntato (oggetti, modelli e valigie inclusi) — poi
"Scarica il file" per portarlo dove vuoi. Ciò che non spunti resta
privato, sempre.

### Corretto: pulsanti sfumati nella pagina di un oggetto

La barra dei pulsanti in alto aveva una sfumatura pensata per lo
scorrimento su schermi piccoli, ma qui non serviva — rimossa.

### Nuovo: "Salva e vai al successivo"

Nella pagina di modifica di un oggetto, salva le modifiche e apre
subito l'oggetto successivo della stessa categoria, senza dover
tornare all'elenco ogni volta.

### Cambiato: "Modelli e dettagli" più vicino al peso

Il pulsante per gestire i modelli di un oggetto (ciascuno col proprio
peso) è ora subito sotto il campo del peso di una singola unità, per
capire più facilmente quale dei due usare.

### Corretto: colonna Peso troppo vicina a Valigia predefinita

Nella tabella degli oggetti (vista testo, sia attivi che archiviati),
la colonna del peso ora ha più respiro rispetto alla colonna
accanto.

### Nessuna azione richiesta per aggiornare

Una nuova migrazione automatica aggiunge i campi necessari, senza
alcuna perdita di dati.
