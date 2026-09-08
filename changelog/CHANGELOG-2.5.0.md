# Changelog — Valigia

Questo file descrive SOLO la versione corrente. Ad ogni nuova versione, il
contenuto di questo file viene prima copiato in `changelog/CHANGELOG-<versione
precedente>.md` (invariato, come archivio storico) e poi sostituito con le
note della nuova versione. Vedi `changelog/README.md` per la convenzione
completa e `CONTEXT.md` per lo stato tecnico dettagliato del progetto.

---

## v2.5.0 — 4 settembre 2026 — Avviso dinamico, valigie distinguibili, menu Impostazioni

### Corretto: l'avviso "valigia sbagliata" non compariva mai

**Causa**: era calcolato solo lato server, dentro il template della
pagina — compariva quindi solo dopo un ricaricamento completo, mai
dopo una modifica al volo di uno stepper (il modo normale in cui si usa
l'app). Ora la risposta della chiamata che salva la quantità include
questa informazione, e l'icona di avviso compare/scompare
immediatamente, senza bisogno di ricaricare nulla.

### Nuovo: due o più valigie della stessa tipologia sono ora distinguibili

Se hai due valigie da cabina attive nello stesso viaggio, prima gli
steppers mostravano la stessa identica etichetta "Cabina" per entrambe
— l'unico modo per distinguerle era il tocco prolungato (hover), quasi
inutilizzabile su schermi touch. Ora, solo quando serve (cioè quando
c'è davvero un doppione), l'etichetta include anche un riferimento alla
valigia specifica: "Cabina · Rimowa", "Cabina · Samsonite". Se ne hai
una sola di un tipo, l'etichetta resta semplice come prima.

### Nuovo: menu di navigazione semplificato, sezione "Impostazioni"

Il menu in alto aveva troppe voci dirette. Riorganizzato così:
- **Valigie** è entrata nel menu a tendina **Catalogo** (insieme a
  Categorie e Oggetti): dal Catalogo gestisci tutto ciò che possiedi
  (oggetti, categorie, valigie fisiche).
- **Utenti**, **Backup** e **Cambia password** non sono più voci dirette
  in cima: ora vivono in un unico nuovo menu a tendina **Impostazioni**,
  insieme alla nuova pagina **Statistiche** (le informazioni su
  CPU/memoria/disco, prima dentro la pagina Backup, ora hanno una
  propria voce dedicata).

### Nessuna azione richiesta per aggiornare

Questa versione non tocca lo schema del database: solo interfaccia e
organizzazione del menu.
