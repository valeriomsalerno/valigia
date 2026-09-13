# Verifiche manuali JS (non parte della suite pytest)

Questa cartella contiene script Node/jsdom usati per verificare a mano
comportamenti lato client che la suite pytest non può testare (nessun
motore JS reale nei test Python). Non sono automatizzati in CI: vanno
eseguiti manualmente quando si tocca la logica corrispondente.

## verify_workspace_scroll_restore.js

Verifica `initWorkspaceScrollRestore()` in `app/static/js/dashboard.js`
(ripristino della posizione di scroll nel workspace di un viaggio dopo
essere tornati da una pagina di impostazioni, es. "Torna al viaggio"
dalle impostazioni di un oggetto).

Richiede `jsdom` (`npm install jsdom` in una cartella scratch, non nel
progetto: non è una dipendenza dell'app). Esecuzione:

```bash
node verify_workspace_scroll_restore.js
```

Atteso:
- Nessun valore salvato in precedenza → `window.scrollTo` NON viene
  chiamato (il comportamento resta quello di sempre: scroll in cima).
- Valore salvato in precedenza (es. 1234) → `window.scrollTo` viene
  chiamato con quel valore, e la chiave in sessionStorage viene
  rimossa subito dopo (ripristino "una tantum").
- In entrambi i casi, l'evento `beforeunload` salva lo scroll corrente
  in sessionStorage, pronto per il prossimo ritorno alla pagina.

## verify_item_search_filter.js

Verifica `applyItemSearchFilter()`/`initItemSearch()` in
`app/static/js/dashboard.js` (ricerca in tempo reale nel pannello
Valigia del workspace di un viaggio).

Esecuzione:

```bash
node verify_item_search_filter.js
```

Atteso:
- Digitando un testo, le righe che non corrispondono vengono nascoste
  (`is-hidden-by-search`), e una categoria che non ha più risultati
  visibili viene nascosta interamente.
- Se il risultato si trova in una categoria diversa da quella
  attualmente selezionata, la scheda passa automaticamente a "Tutti"
  (altrimenti sembrerebbe "nessun risultato" pur esistendo altrove).
- Svuotando la ricerca, tutto torna visibile come prima.

## verify_generic_scroll_restore.js

Verifica `initGenericScrollRestore()` in `app/static/js/dashboard.js`
(ripristino scroll per QUALSIASI pagina — tipicamente il catalogo
oggetti — dopo un giro "Modifica" -> "Salva oggetto", introdotto
insieme all'unificazione delle pagine dettaglio/modifica dell'oggetto).

Esecuzione:

```bash
node verify_generic_scroll_restore.js
```

Atteso:
- Chiave in sessionStorage basata sull'URL COMPLETO (percorso +
  querystring): pagine con querystring diversa (es. `?archiviati=1`)
  non si "vedono" a vicenda.
- Sul workspace di un viaggio (marcatore `[data-main-tabs]` nel DOM)
  il meccanismo generico si disattiva del tutto: quella pagina ha il
  proprio meccanismo dedicato, per-viaggio (vedi
  verify_workspace_scroll_restore.js).

## verify_lucide_lab_patch.js

Verifica il monkey-patch di `lucide.createIcons()` in `base.html`
(unisce le 357 icone "Lab" di `lucide-lab.js` al set principale, per
qualunque chiamata esistente o futura a `createIcons()` senza
argomenti) usando il VERO bundle UMD di lucide (scaricato dal
registro npm, non un mock) — è stato proprio testando contro il bundle
reale, non contro un mock semplificato, che si è scoperto il bug delle
chiavi in kebab-case invece che PascalCase (vedi il commento in cima a
`lucide-lab.js`). Richiede il file `real-lucide.js` (il bundle UMD
scaricato con `npm pack lucide` — non incluso nel repository, va
riscaricato se si rigenera questa verifica) accanto a questo script.

Esecuzione:

```bash
node verify_lucide_lab_patch.js
```

Atteso: un'icona del set principale e una icona "Lab" vengono
entrambe trovate; un nome inventato resta non trovato (comportamento
invariato per un nome sbagliato).
