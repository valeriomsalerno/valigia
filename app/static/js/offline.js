/**
 * offline.js
 * ==========
 * Permette di continuare a modificare quantità/obiettivi/oggetti da
 * comprare/indossati anche senza connessione (es. in aereo): le azioni
 * che falliscono per un vero errore di rete (non un rifiuto del
 * server) vengono messe in coda in IndexedDB e rispedite
 * automaticamente al ritorno della connessione, IN ORDINE.
 *
 * IMPORTANTE — limiti di questo meccanismo, da conoscere:
 *
 * 1. "Ultimo scritto vince": se nel frattempo un altro utente ha
 *    modificato la STESSA cosa da un altro dispositivo (es. una valigia
 *    condivisa), la sincronizzazione riapplica comunque il valore
 *    scritto offline, sovrascrivendo quello nel frattempo salvato da
 *    altri. Nessun tentativo di "unire" le due modifiche.
 * 2. Solo le azioni più comuni durante la preparazione di una valigia
 *    sono in coda offline (quantità nelle valigie, obiettivo, unità da
 *    comprare, quantità indossata) — vedi ELIGIBLE_PATHS. Altre azioni
 *    (condivisione, gestione utenti, creare un viaggio, caricare
 *    un'immagine, ecc.) richiedono comunque una connessione attiva.
 * 3. Su iOS, Safari non supporta la Background Sync API (a differenza
 *    di Chrome/Android): la sincronizzazione riparte quando l'app
 *    TORNA IN PRIMO PIANO con connessione, non mentre è chiusa in
 *    background. In pratica: riapri l'app una volta tornato con
 *    linea/wifi e la sincronizzazione riparte da sola.
 * 4. Mentre una modifica è in coda, gli indicatori derivati (colore
 *    dello stato, statistiche della valigia, avvisi) NON si aggiornano
 *    — richiedono un calcolo che avviene solo lato server. Il valore
 *    scritto dall'utente resta comunque visibile e non si perde.
 */

(function () {
  // "/api/variante" NON è (più) qui: la finestra di scelta del modello
  // ha bisogno di una risposta COMPLETA e AGGIORNATA dal server per
  // calcolare correttamente il massimo consentito in ciascuna valigia
  // (che dipende da quanto è già allocato nelle ALTRE valigie) — un
  // salvataggio "in coda" silenzioso, con una risposta parziale, la
  // lasciava in uno stato sbagliato senza un errore chiaro (bug reale
  // segnalato: "un errore di comunicazione, ma non si capisce il
  // motivo"). Qui è meglio un errore di rete esplicito e comprensibile
  // che un salvataggio accodato ma incoerente con lo stato reale.
  const ELIGIBLE_PATHS = ["/api/quantita", "/api/obiettivo", "/api/mancante", "/api/indossato"];
  const DB_NAME = "valigia-offline";
  const DB_VERSION = 1;
  const STORE = "pending";

  function isEligible(url) {
    return ELIGIBLE_PATHS.some((p) => url.startsWith(p));
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB non disponibile in questo browser."));
        return;
      }
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function enqueue(url, opts) {
    try {
      const db = await openDb();
      const entry = {
        url,
        method: opts.method || "POST",
        body: opts.body,
        description: describeAction(url, opts.body),
        ts: Date.now(),
      };
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).add(entry);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
      updateBanner();
      // Risposta "ottimistica": non conosciamo il vero stato calcolato
      // dal server (colore, statistiche, avvisi), ma il valore scritto
      // dall'utente resta visibile — vedi initRobustStepper in
      // dashboard.js, che gestisce `queued: true` senza applicare un
      // aggiornamento completo finché non arriva la vera risposta.
      return { ok: true, queued: true };
    } catch (e) {
      return { ok: false, error: "Impossibile salvare la modifica offline su questo dispositivo." };
    }
  }

  /** Etichetta leggibile per il banner, a scopo puramente informativo. */
  function describeAction(url, bodyStr) {
    let body = {};
    try {
      body = JSON.parse(bodyStr || "{}");
    } catch (e) {
      /* ignorato */
    }
    if (url.startsWith("/api/quantita")) return `quantità (oggetto #${body.trip_item_id})`;
    if (url.startsWith("/api/obiettivo")) return `obiettivo (oggetto #${body.trip_item_id})`;
    if (url.startsWith("/api/mancante")) return `da comprare (oggetto #${body.trip_item_id})`;
    if (url.startsWith("/api/indossato")) return `indossato (oggetto #${body.trip_item_id})`;
    if (url.startsWith("/api/variante")) return `modello (oggetto #${body.trip_item_id})`;
    return "modifica";
  }

  async function getAll() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async function removeEntry(id) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).delete(id);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  async function count() {
    try {
      const all = await getAll();
      return all.length;
    } catch (e) {
      return 0;
    }
  }

  let flushing = false;

  /** Rispedisce le azioni in coda, IN ORDINE. Si ferma al primo vero errore di rete (si ritenta più tardi). */
  async function flush() {
    if (flushing) return;
    if (!navigator.onLine) return;
    flushing = true;
    let syncedAny = false;

    try {
      const items = await getAll();
      items.sort((a, b) => a.ts - b.ts);

      for (const item of items) {
        try {
          const res = await fetch(item.url, {
            method: item.method,
            headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
            body: item.body,
          });
          // Risposta arrivata (anche un rifiuto, es. dati non più
          // validi): non ha senso ritentarla all'infinito, va scartata
          // per non bloccare le voci successive in coda.
          await removeEntry(item.id);
          syncedAny = true;
        } catch (e) {
          break; // ancora offline: ferma qui, ritenta al prossimo giro
        }
      }
    } finally {
      flushing = false;
      updateBanner();
      if (syncedAny) {
        const remaining = await count();
        if (remaining === 0 && window.showToast) {
          window.showToast("Modifiche fatte offline sincronizzate.", "success");
        }
        if (window.refreshLiveStats) window.refreshLiveStats();
        if (typeof refreshShoppingPanel === "function") refreshShoppingPanel();
      }
    }
  }

  function updateBanner() {
    count().then((n) => {
      const toggle = document.querySelector("[data-offline-badge-toggle]");
      const detail = document.querySelector("[data-offline-badge-detail]");
      if (!toggle || !detail) return; // pagine senza topbar (es. login)

      if (n === 0) {
        toggle.style.display = "none";
        detail.classList.remove("open");
        return;
      }
      toggle.style.display = "inline-flex";
      toggle.textContent = String(n);
      const label = n === 1 ? "1 modifica in attesa di connessione" : `${n} modifiche in attesa di connessione`;
      toggle.setAttribute("title", label);
      toggle.setAttribute("aria-label", label);
      detail.textContent = label;
    });
  }

  document.addEventListener("click", (e) => {
    const toggle = document.querySelector("[data-offline-badge-toggle]");
    const detail = document.querySelector("[data-offline-badge-detail]");
    if (!toggle || !detail) return;
    if (e.target === toggle) {
      detail.classList.toggle("open");
    } else if (!e.target.closest("[data-offline-badge-detail]")) {
      detail.classList.remove("open");
    }
  });

  window.addEventListener("online", flush);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") flush();
  });
  // Ritenta anche periodicamente: l'evento "online" non sempre scatta
  // in modo tempestivo/affidabile su tutti i browser.
  setInterval(flush, 20000);

  document.addEventListener("DOMContentLoaded", () => {
    updateBanner();
    flush();
  });

  window.offlineQueue = { isEligible, enqueue, flush, count };
})();
