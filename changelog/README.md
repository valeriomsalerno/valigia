# Archivio changelog

Questa cartella conserva i changelog delle versioni **precedenti** a
quella attuale. Il changelog della versione in uso si trova sempre in
`CHANGELOG.md` nella cartella principale del progetto.

## Convenzione (da seguire ad ogni nuova versione)

Quando si rilascia una nuova versione dell'app:

1. **Prima di modificare nulla**, copia il `CHANGELOG.md` attuale (quello
   della versione che si sta per sostituire) in questa cartella,
   rinominandolo con il numero di versione a cui si riferisce:

   ```
   changelog/CHANGELOG-1.0.0.md
   ```

2. **Non modificare mai** un file già presente in questa cartella: sono
   uno storico immutabile.

3. Solo a questo punto, riscrivi `CHANGELOG.md` nella root con le note
   della nuova versione (puoi usare la vecchia voce come riferimento di
   formato — vedi la struttura in `CHANGELOG.md`).

4. Aggiorna anche `CONTEXT.md` nella root con lo stato tecnico aggiornato
   (nuove funzionalità, decisioni prese, eventuali migrazioni dati da
   fare a mano).

## Indice delle versioni archiviate

- **[CHANGELOG-3.6.0.md](CHANGELOG-3.6.0.md)** — 8 settembre 2026. Larghezza colonne salvabile, catalogo pubblico/privato, correzioni pagina oggetto.
- **[CHANGELOG-3.5.0.md](CHANGELOG-3.5.0.md)** — 8 settembre 2026. Pulsanti di azzeramento per singolo oggetto e per tutto il viaggio.
- **[CHANGELOG-3.4.3.md](CHANGELOG-3.4.3.md)** — 7 settembre 2026. Correzione salvataggio che non si rifletteva riaprendo la finestra modelli.
- **[CHANGELOG-3.4.2.md](CHANGELOG-3.4.2.md)** — 7 settembre 2026. Correzione doppio gestore sui pulsanti +/- degli stepper con modelli.
- **[CHANGELOG-3.4.1.md](CHANGELOG-3.4.1.md)** — 7 settembre 2026. Correzione stepper e obiettivo fuori conteggio per modelli eliminati.
- **[CHANGELOG-3.4.0.md](CHANGELOG-3.4.0.md)** — 7 settembre 2026. Finestra di scelta modello riscritta da zero, race condition risolta.
- **[CHANGELOG-3.3.3.md](CHANGELOG-3.3.3.md)** — 7 settembre 2026. Correzione quantità di modelli orfane dopo eliminazione valigia.
- **[CHANGELOG-3.3.2.md](CHANGELOG-3.3.2.md)** — 7 settembre 2026. Correzione critica di produzione, vincolo database che impediva di salvare i modelli.
- **[CHANGELOG-3.3.1.md](CHANGELOG-3.3.1.md)** — 7 settembre 2026. Correzione massimo qui e comunicazione col server nella finestra modelli.
- **[CHANGELOG-3.3.0.md](CHANGELOG-3.3.0.md)** — 7 settembre 2026. Correzione critica peso dei modelli, finestra di scelta modello, home e menu ritoccati.
- **[CHANGELOG-3.2.0.md](CHANGELOG-3.2.0.md)** — 7 settembre 2026. Menu snellito con Impostazioni nel menu utente, Home ritoccata, allineamento pulsanti, torna al viaggio.
- **[CHANGELOG-3.1.3.md](CHANGELOG-3.1.3.md)** — 7 settembre 2026. Correzione trascinamento, spaziatura menu mobile, stellina valigie, tabella catalogo ribilanciata.
- **[CHANGELOG-3.1.2.md](CHANGELOG-3.1.2.md)** — 7 settembre 2026. Riordino sempre per trascinamento, mai a pulsanti su/giù.
- **[CHANGELOG-3.1.1.md](CHANGELOG-3.1.1.md)** — 7 settembre 2026. Ordine personale delle voci del menu e del sottomenu Catalogo.
- **[CHANGELOG-3.1.0.md](CHANGELOG-3.1.0.md)** — 7 settembre 2026. Tabelle responsive su tutta l'app, ordinamento separato catalogo/viaggio, viaggio più vicino nel menu, banner offline come pallino.
- **[CHANGELOG-3.0.7.md](CHANGELOG-3.0.7.md)** — 6 settembre 2026. Tabella catalogo oggetti ricostruita con percentuali, campo icona a larghezza piena, heading rimossa dal viaggio.
- **[CHANGELOG-3.0.6.md](CHANGELOG-3.0.6.md)** — 6 settembre 2026. Bordo di categoria arrotondato correttamente, colonne tabella oggetti/categorie.
- **[CHANGELOG-3.0.5.md](CHANGELOG-3.0.5.md)** — 6 settembre 2026. Bordo di categoria risolto alla radice (barra posizionata invece di border-left), tabelle non più forzate globalmente.
- **[CHANGELOG-3.0.4.md](CHANGELOG-3.0.4.md)** — 6 settembre 2026. Bordo attaccato alla tabella, icone libere per il catalogo, tabelle categorie.
- **[CHANGELOG-3.0.3.md](CHANGELOG-3.0.3.md)** — 6 settembre 2026. Correzione definitiva: un solo bordo di categoria (rimosso il bordo doppio per riga).
- **[CHANGELOG-3.0.2.md](CHANGELOG-3.0.2.md)** — 6 settembre 2026. Icone personalizzabili del catalogo, validazione modelli, pulsante offline manuale.
- **[CHANGELOG-3.0.1.md](CHANGELOG-3.0.1.md)** — 6 settembre 2026. Correzione doppio bordo, scopribilità modelli, pulsante archivia mobile, offline migliorato.
- **[CHANGELOG-3.0.0.md](CHANGELOG-3.0.0.md)** — 6 settembre 2026. Funzionamento offline, modelli per oggetto (camicie/pantaloni con varianti), rifiniture visive.
- **[CHANGELOG-2.9.0.md](CHANGELOG-2.9.0.md)** — 6 settembre 2026. Correzione critica iOS (menu irraggiungibile), rifiniture tabelle/categorie del catalogo.
- **[CHANGELOG-2.8.0.md](CHANGELOG-2.8.0.md)** — 6 settembre 2026. Catalogo di base personalizzabile, rifiniture visive multiple.
- **[CHANGELOG-2.7.1.md](CHANGELOG-2.7.1.md)** — 4 settembre 2026. Correzione: pallino "da comprare" sulla scheda Lista della spesa del viaggio.
- **[CHANGELOG-2.7.0.md](CHANGELOG-2.7.0.md)** — 4 settembre 2026. Ricerca copertina live, correzione immagine caricata sfalsata, ricerca nella lista della spesa, aggiornamento in tempo reale delle valigie condivise.
- **[CHANGELOG-2.6.0.md](CHANGELOG-2.6.0.md)** — 4 settembre 2026. Valigie condivise tra collaboratori, copertina personalizzabile (termini di ricerca, caricamento con posizionamento), navigazione tra oggetti del catalogo.
- **[CHANGELOG-2.5.0.md](CHANGELOG-2.5.0.md)** — 4 settembre 2026. Avviso dinamico valigia sbagliata, distinzione valigie stesso tipo, menu Impostazioni.
- **[CHANGELOG-2.4.0.md](CHANGELOG-2.4.0.md)** — 4 settembre 2026. Distribuzione tra valigie sempre manuale, "indosso" a quantità, catalogo a schede, sessione lunga, statistiche di sistema.
- **[CHANGELOG-2.3.0.md](CHANGELOG-2.3.0.md)** — 3 settembre 2026. Correzione critica trip_bag_id (impossibile aprire/creare viaggi), nuova funzione oggetti indossati.
- **[CHANGELOG-2.2.0.md](CHANGELOG-2.2.0.md)** — 3 settembre 2026. Stato automatico, riordino trascinabile, lista della spesa live, correzioni critiche di salvataggio (steppers robusti).
- **[CHANGELOG-2.1.2.md](CHANGELOG-2.1.2.md)** — 3 settembre 2026. Correzione errore Home/Viaggi per valigia eliminata, con riparazione automatica dei dati.
- **[CHANGELOG-2.1.1.md](CHANGELOG-2.1.1.md)** — 3 settembre 2026. Concorrenza SQLite (modalità WAL), convenzione corretta dei numeri decimali (punto=migliaia, virgola=decimali).
- **[CHANGELOG-2.1.0.md](CHANGELOG-2.1.0.md)** — 3 settembre 2026. Valigie tipizzate (cabina/stiva/zaino), liste di imballaggio personali per utente, lista della spesa condivisa per acquirente, home a blocchi, backup/ripristino, migrazioni automatiche.
- **[CHANGELOG-2.0.1.md](CHANGELOG-2.0.1.md)** — 3 settembre 2026. Numero di versione visibile in app, cache-busting dei file statici.
- **[CHANGELOG-2.0.0.md](CHANGELOG-2.0.0.md)** — 3 settembre 2026. Multi-utente, condivisione viaggi, valigie fisiche, pesi, quantità mancante gestibile, immagine di copertina automatica.
- **[CHANGELOG-1.0.0.md](CHANGELOG-1.0.0.md)** — 3 settembre 2026. Prima versione: dashboard, catalogo, viaggi, automazioni quantità, import Notion, login singolo amministratore.
