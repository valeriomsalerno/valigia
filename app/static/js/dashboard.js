/**
 * dashboard.js
 * ============
 * Interazioni "al volo" del workspace di un viaggio:
 *   - steppers di quantità per valigia, stepper "obiettivo", stepper
 *     "quante ne mancano da comprare" — tutti "robusti": una risposta
 *     del server superata da una più recente viene ignorata, e un
 *     salvataggio fallito ripristina l'ultimo valore confermato invece
 *     di lasciare sullo schermo un numero che in realtà non è stato
 *     salvato (bug reale corretto in questa versione, vedi CHANGELOG)
 *   - stato (colore della riga) interamente automatico, in base
 *     all'obiettivo e alla somma nelle valigie — niente più check manuale
 *   - avviso quando la somma nelle valigie supera l'obiettivo
 *   - lista della spesa aggiornata all'istante, senza ricaricare la pagina
 *   - switch per nascondere gli oggetti già "in valigia" (verdi)
 *   - riordino trascinabile degli oggetti dentro ciascuna categoria
 *   - schede principali Valigia / Lista della spesa (client-side)
 *   - sotto-schede per categoria dentro il pannello Valigia
 *   - apertura del pannello di dettaglio di un oggetto
 *
 * Tutte le chiamate di scrittura passano da window.apiFetch (app.js), che
 * aggiunge automaticamente il token CSRF e non lascia mai un fallimento
 * di rete passare inosservato.
 */

function updateHeaderStats(stats) {
  if (!stats) return;
  const set = (sel, value) => {
    document.querySelectorAll(sel).forEach((el) => (el.textContent = value));
  };
  set("[data-stat=conservati]", stats.conservati);
  set("[data-stat=da_comprare]", stats.da_comprare);
  set("[data-stat=da_preparare]", stats.da_preparare);
  set("[data-stat=totale]", stats.totale);
  set("[data-stat=percentuale]", stats.percentuale_pronta + "%");

  const bar = document.querySelector("[data-progress-fill]");
  if (bar) bar.style.width = stats.percentuale_pronta + "%";

  (stats.luggages || []).forEach((lug) => {
    document
      .querySelectorAll(`[data-packed-luggage="${lug.trip_luggage_id}"]`)
      .forEach((el) => (el.textContent = lug.packed_qty));
    document
      .querySelectorAll(`[data-weight-luggage="${lug.trip_luggage_id}"]`)
      .forEach((el) => (el.textContent = (lug.total_weight_grams / 1000).toFixed(2).replace(".", ",") + " kg"));
  });

  const navBadge = document.querySelector("[data-nav-shopping-badge]");
  if (navBadge) {
    if (stats.da_comprare > 0) {
      navBadge.textContent = stats.da_comprare;
      navBadge.style.display = "inline-flex";
    } else {
      navBadge.style.display = "none";
    }
  }

  // Stesso pallino, ma sulla scheda "Lista della spesa" DENTRO il
  // viaggio (bug reale corretto: prima non esisteva nemmeno nel DOM se
  // il conteggio era 0 al caricamento, quindi non si aggiornava mai
  // senza ricaricare la pagina a mano — stesso identico problema già
  // risolto per il pallino nel menu in alto, ma non applicato qui).
  const tabBadge = document.querySelector("[data-main-tab-shopping-badge]");
  if (tabBadge) {
    if (stats.da_comprare > 0) {
      tabBadge.textContent = stats.da_comprare;
      tabBadge.style.display = "inline-flex";
    } else {
      tabBadge.style.display = "none";
    }
  }
}

/** Applica alla riga lo stato/etichetta/avviso restituiti dal server dopo un salvataggio. */
function applyRowUpdate(row, payload) {
  if (!row) return;
  row.dataset.status = payload.status;
  row.dataset.overflow = payload.is_overflowing ? "true" : "false";
  if (payload.indossato_qty !== undefined) {
    row.dataset.worn = payload.indossato_qty > 0 ? "true" : "false";
  }
  const label = row.querySelector("[data-status-label]");
  if (label) label.textContent = payload.status_label;

  const missingStepper = row.querySelector(".missing-stepper");
  if (missingStepper) {
    missingStepper.dataset.active = payload.missing_qty > 0 ? "true" : "false";
    const input = missingStepper.querySelector("input");
    if (input) input.value = payload.missing_qty;
  }

  applyHideCompletedToRow(row);
}

/**
 * Inizializza un gruppo di stepper (+/- e campo numerico) protetto da:
 *  - "sequence guard": se, per via della rete, una risposta più vecchia
 *    arriva dopo una più recente, viene IGNORATA — non sovrascrive mai
 *    un valore più aggiornato;
 *  - ripristino automatico dell'ultimo valore CONFERMATO dal server in
 *    caso di errore, così un salvataggio fallito non lascia mai un
 *    numero sullo schermo che in realtà non è stato salvato;
 *  - notifica visibile (toast) se un salvataggio non riesce.
 */
function initRobustStepper(container, { url, buildBody, onSuccess, min = 0, max = 999 }) {
  const input = container.querySelector("input");
  if (!input) return;

  let confirmedValue = input.value;
  let seq = 0;

  const send = (value) => {
    const mySeq = ++seq;
    apiFetch(url, {
      method: "POST",
      body: JSON.stringify(buildBody(value)),
    }).then((payload) => {
      if (mySeq !== seq) return; // superata da una richiesta più recente
      if (!payload.ok) {
        input.value = confirmedValue;
        showToast(payload.error || "Salvataggio non riuscito: riprova.");
        return;
      }
      if (payload.queued) {
        // Offline: il valore scritto resta (non si annulla), ma non
        // conosciamo ancora il vero stato calcolato dal server (colore,
        // statistiche, avvisi) — resta "in sospeso" finché non
        // sincronizza (vedi offline.js). Non tocchiamo confirmedValue a
        // "value" per sicurezza: se la sincronizzazione dovesse fallire
        // per un motivo non di rete, un nuovo tentativo manuale userà
        // comunque questo valore come base corretta.
        confirmedValue = value;
        container.classList.add("is-pending-sync");
        return;
      }
      container.classList.remove("is-pending-sync");
      const result = onSuccess(payload, value);
      confirmedValue = result === undefined ? value : result;
    });
  };

  container.querySelectorAll("button[data-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const delta = Number(btn.dataset.step);
      const next = Math.max(min, Math.min(max, Number(input.value || 0) + delta));
      input.value = next;
      send(next);
    });
  });

  input.addEventListener("change", () => {
    const next = Math.max(min, Math.min(max, Number(input.value || 0)));
    input.value = next;
    send(next);
  });
}

/** Applica/rimuove l'avviso "valigia sbagliata" su uno specifico stepper,
    creando o togliendo l'icona al volo (nessun reload della pagina). */
function applyMismatchWarning(stepper, isMismatched, message) {
  stepper.classList.toggle("has-mismatch", isMismatched);
  const baseTitle = stepper.dataset.baseTitle ?? stepper.title;
  stepper.dataset.baseTitle = baseTitle;

  let flag = stepper.querySelector(".mismatch-flag");
  if (isMismatched) {
    stepper.title = message ? `${baseTitle} — attenzione: ${message}` : baseTitle;
    if (!flag) {
      flag = document.createElement("i");
      flag.setAttribute("data-lucide", "alert-triangle");
      flag.className = "icon mismatch-flag";
      stepper.appendChild(flag);
      if (window.lucide) window.lucide.createIcons();
    }
  } else {
    stepper.title = baseTitle;
    if (flag) flag.remove();
  }
}

function initQuantitySteppers() {
  // ":not(.qty-stepper--variant-luggage)" è FONDAMENTALE: quello stepper
  // condivide la stessa classe base "qty-stepper" e lo stesso attributo
  // "data-trip-luggage-id" di questo selettore — senza l'esclusione,
  // ENTRAMBI i gestori si attaccavano agli stessi pulsanti +/-: uno
  // apriva correttamente la finestra di scelta modello, l'altro (questo)
  // chiamava IN PARALLELO l'endpoint sbagliato (/api/quantita, pensato
  // per oggetti SENZA modelli), aggiornando il numero mostrato senza
  // toccare i modelli veri (bug reale segnalato: "il conteggio si
  // aggiorna ma i modelli restano al numero originario").
  document.querySelectorAll(".qty-stepper[data-trip-luggage-id]:not(.qty-stepper--variant-luggage)").forEach((stepper) => {
    const tripItemId = stepper.dataset.tripItemId;
    const tripLuggageId = stepper.dataset.tripLuggageId;
    const row = stepper.closest(".item-row");

    initRobustStepper(stepper, {
      url: "/api/quantita",
      buildBody: (value) => ({
        trip_item_id: Number(tripItemId),
        trip_luggage_id: Number(tripLuggageId),
        quantity: Number(value),
      }),
      onSuccess: (payload, value) => {
        applyRowUpdate(row, payload);
        updateHeaderStats(payload.stats);
        const isMismatched = !!(payload.mismatches && payload.mismatches[tripLuggageId]);
        applyMismatchWarning(stepper, isMismatched, payload.mismatch_message);
        return payload.quantities[tripLuggageId] ?? value;
      },
    });
  });
}

/** Steppers per MODELLO specifico (oggetti con Item.has_variants, es. camicie/pantaloni di taglio diverso). */
function initTargetStepper() {
  document.querySelectorAll(".qty-stepper--target").forEach((stepper) => {
    const tripItemId = stepper.dataset.tripItemId;
    const row = stepper.closest(".item-row");

    initRobustStepper(stepper, {
      url: "/api/obiettivo",
      buildBody: (value) => ({ trip_item_id: Number(tripItemId), target_qty: value === "" ? null : Number(value) }),
      onSuccess: (payload) => {
        applyRowUpdate(row, payload);
        updateHeaderStats(payload.stats);
        return payload.target_qty ?? "";
      },
    });
  });
}

function initMissingStepper() {
  document.querySelectorAll(".missing-stepper").forEach((stepper) => {
    const tripItemId = stepper.dataset.tripItemId;
    const row = stepper.closest(".item-row");

    initRobustStepper(stepper, {
      url: "/api/mancante",
      buildBody: (value) => ({ trip_item_id: Number(tripItemId), missing_qty: Number(value) }),
      onSuccess: (payload, value) => {
        applyRowUpdate(row, payload);
        updateHeaderStats(payload.stats);
        refreshShoppingPanel();
        return payload.missing_qty ?? value;
      },
    });
  });
}

/** Stepper "indosso direttamente" — quante unità, non un semplice sì/no
    (non si possono indossare 13 paia di boxer contemporaneamente). */
function initWornStepper() {
  document.querySelectorAll(".qty-stepper--worn").forEach((stepper) => {
    const tripItemId = stepper.dataset.tripItemId;
    const row = stepper.closest(".item-row");

    initRobustStepper(stepper, {
      url: "/api/indossato",
      buildBody: (value) => ({ trip_item_id: Number(tripItemId), quantity: Number(value) }),
      onSuccess: (payload, value) => {
        applyRowUpdate(row, payload);
        updateHeaderStats(payload.stats);
        return payload.indossato_qty ?? value;
      },
    });
  });
}

function initDetailPanel() {
  const overlay = document.querySelector("[data-detail-overlay]");
  const panel = document.querySelector("[data-detail-panel]");
  const inner = document.querySelector("[data-detail-panel-inner]");
  if (!overlay || !panel || !inner) return;

  const tripId = panel.dataset.tripId;

  const closePanel = () => {
    overlay.classList.remove("open");
    panel.classList.remove("open");
  };

  overlay.addEventListener("click", closePanel);
  panel.addEventListener("click", (e) => {
    if (e.target.closest("[data-detail-close]")) closePanel();
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".info-btn, .item-name-btn");
    if (!btn) return;
    const row = btn.closest(".item-row");
    if (!row) return;
    const tripItemId = row.dataset.tripItemId;
    inner.innerHTML = '<p class="text-muted">Caricamento…</p>';
    overlay.classList.add("open");
    panel.classList.add("open");

    fetch(`/viaggi/${tripId}/dettaglio/${tripItemId}`)
      .then((res) => (res.ok ? res.text() : Promise.reject()))
      .then((html) => {
        inner.innerHTML = html;
        if (window.lucide) window.lucide.createIcons();
      })
      .catch(() => {
        inner.innerHTML = '<p class="text-muted">Non è stato possibile caricare i dettagli. Riprova.</p>';
      });
  });

  inner.addEventListener("click", (e) => {
    const saveBtn = e.target.closest("[data-save-note]");
    if (!saveBtn) return;
    const tripItemId = saveBtn.dataset.tripItemId;
    const textarea = inner.querySelector("[data-note-field]");
    const feedback = inner.querySelector("[data-note-feedback]");

    apiFetch("/api/nota", {
      method: "POST",
      body: JSON.stringify({ trip_item_id: Number(tripItemId), note: textarea.value }),
    }).then((payload) => {
      if (feedback) {
        feedback.textContent = payload.ok ? "Nota salvata." : "Errore nel salvataggio.";
        setTimeout(() => (feedback.textContent = ""), 2500);
      }
    });
  });

  inner.addEventListener("change", (e) => {
    const select = e.target.closest("[data-reassign-buyer]");
    if (!select) return;
    apiFetch("/api/assegna-acquisto", {
      method: "POST",
      body: JSON.stringify({
        trip_item_id: Number(select.dataset.reassignBuyer),
        assigned_buyer_id: select.value || null,
      }),
    }).then((payload) => {
      if (!payload.ok) {
        showToast(payload.error || "Riassegnazione non riuscita: riprova.");
        return;
      }
      refreshShoppingPanel();
    });
  });
}

/** Schede principali Valigia / Lista della spesa, senza ricaricare la pagina. */
function initMainTabs() {
  const tabsWrap = document.querySelector("[data-main-tabs]");
  if (!tabsWrap) return;

  const buttons = tabsWrap.querySelectorAll("[data-main-tab-btn]");
  const panels = document.querySelectorAll("[data-main-tab-panel]");

  const activate = (name) => {
    buttons.forEach((b) => b.classList.toggle("active", b.dataset.mainTabBtn === name));
    panels.forEach((p) => p.classList.toggle("is-hidden", p.dataset.mainTabPanel !== name));
  };

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      activate(btn.dataset.mainTabBtn);
      history.replaceState(null, "", btn.dataset.mainTabBtn === "spesa" ? "#spesa" : " ");
    });
  });

  if (window.location.hash === "#spesa") activate("spesa");
}

/** Sotto-schede per categoria dentro il pannello Valigia. */
function initCategoryTabs() {
  const tabsWrap = document.querySelector("[data-category-tabs]");
  if (!tabsWrap) return;

  const buttons = tabsWrap.querySelectorAll("[data-category-tab]");
  const panels = document.querySelectorAll("[data-category-panel]");

  // "Tutti" è la scheda attiva di default al caricamento della pagina.
  const initialActive = tabsWrap.querySelector(".category-tab.active");
  document.body.dataset.viewingAllCategories =
    initialActive && initialActive.dataset.categoryTab === "all" ? "true" : "false";

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.categoryTab;
      buttons.forEach((b) => b.classList.toggle("active", b === btn));
      panels.forEach((p) => p.classList.toggle("is-hidden", id !== "all" && p.dataset.categoryPanel !== id));
      // Il nome della categoria sopra ogni tabella si vede solo quando
      // sono visibili PIÙ categorie insieme ("Tutti"): con una sola
      // categoria attiva sarebbe ridondante (la scheda lo dice già).
      document.body.dataset.viewingAllCategories = id === "all" ? "true" : "false";
    });
  });
}

/* =============================================================================
   Lista della spesa: aggiornamento live (senza ricaricare la pagina)
   ============================================================================= */
function refreshShoppingPanel() {
  const tabsWrap = document.querySelector("[data-main-tabs]");
  const list = document.querySelector("[data-shopping-panel-list]");
  const tripId = tabsWrap ? tabsWrap.dataset.tripId : null;
  if (!list || !tripId) return;

  fetch(`/viaggi/${tripId}/spesa-frammento`)
    .then((res) => (res.ok ? res.text() : Promise.reject()))
    .then((html) => {
      list.innerHTML = html;
      if (window.lucide) window.lucide.createIcons();
      applyShoppingSearchFilter(); // riapplica un'eventuale ricerca già in corso
    })
    .catch(() => {
      // Un mancato aggiornamento del frammento non è critico: alla
      // prossima apertura della scheda i dati saranno comunque corretti
      // (il server è sempre la fonte di verità).
    });
}

/** Ricerca client-side, come nel pannello Valigia: filtra le righe della
    lista della spesa per nome, senza bisogno del server. */
function applyShoppingSearchFilter() {
  const input = document.querySelector("[data-shopping-search]");
  const list = document.querySelector("[data-shopping-panel-list]");
  if (!input || !list) return;
  const query = input.value.trim().toLowerCase();

  list.querySelectorAll(".shopping-row").forEach((row) => {
    const name = (row.querySelector(".name")?.textContent || "").toLowerCase();
    row.classList.toggle("is-hidden-by-search", query !== "" && !name.includes(query));
  });

  // Nasconde anche il gruppo per acquirente se, dopo il filtro, non ha più righe visibili.
  list.querySelectorAll(".category-section").forEach((section) => {
    const hasVisible = Array.from(section.querySelectorAll(".shopping-row")).some(
      (row) => !row.classList.contains("is-hidden-by-search")
    );
    section.classList.toggle("is-hidden-by-search", !hasVisible);
  });
}

function initShoppingSearch() {
  const input = document.querySelector("[data-shopping-search]");
  if (!input) return;
  input.addEventListener("input", applyShoppingSearchFilter);
}

/** Pulsante "Acquistato" e riassegnazione dentro il pannello Lista della
    spesa: delega sul contenitore, così sopravvive ai refresh del frammento. */
function initShoppingPanelActions() {
  const panel = document.querySelector('[data-main-tab-panel="spesa"]');
  if (!panel) return;

  panel.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-mark-purchased]");
    if (!btn) return;
    const tripItemId = Number(btn.dataset.markPurchased);
    btn.disabled = true;

    apiFetch("/api/mancante", {
      method: "POST",
      body: JSON.stringify({ trip_item_id: tripItemId, missing_qty: 0 }),
    }).then((payload) => {
      btn.disabled = false;
      if (!payload.ok) {
        showToast(payload.error || "Operazione non riuscita: riprova.");
        return;
      }
      updateHeaderStats(payload.stats);
      const row = document.querySelector(`.item-row[data-trip-item-id="${tripItemId}"]`);
      if (row) applyRowUpdate(row, payload);
      refreshShoppingPanel();
    });
  });

  panel.addEventListener("change", (e) => {
    const select = e.target.closest("[data-reassign-buyer]");
    if (!select) return;
    apiFetch("/api/assegna-acquisto", {
      method: "POST",
      body: JSON.stringify({
        trip_item_id: Number(select.dataset.reassignBuyer),
        assigned_buyer_id: select.value || null,
      }),
    }).then((payload) => {
      if (!payload.ok) {
        showToast(payload.error || "Riassegnazione non riuscita: riprova.");
        return;
      }
      refreshShoppingPanel();
    });
  });
}

/* =============================================================================
   Switch "nascondi già in valigia" / "nascondi non necessari"
   ============================================================================= */
function applyHideCompletedToRow(row) {
  const hideCompleted = document.querySelector("[data-hide-completed]");
  const hideUnnecessary = document.querySelector("[data-hide-unnecessary]");
  const shouldHide =
    (hideCompleted && hideCompleted.checked && row.dataset.status === "conservato") ||
    (hideUnnecessary && hideUnnecessary.checked && row.dataset.status === "non_necessario");
  row.classList.toggle("is-hidden-completed", shouldHide);
}

function initHideCompletedToggle() {
  const toggles = document.querySelectorAll("[data-hide-completed], [data-hide-unnecessary]");
  if (!toggles.length) return;

  const apply = () => {
    document.querySelectorAll(".item-row").forEach(applyHideCompletedToRow);
  };

  toggles.forEach((toggle) => toggle.addEventListener("change", apply));
  apply();
}

/* =============================================================================
   Riordino trascinabile degli oggetti dentro una categoria (Pointer Events:
   stessa API per mouse, touch e penna, funziona anche su iOS/iPadOS).
   Spostare in un'ALTRA categoria resta possibile solo dal Catalogo.
   ============================================================================= */
/**
 * Riordino generico per trascinamento (tocco/mouse), usato da:
 * - lista oggetti nel workspace di un viaggio (righe .item-row)
 * - tabella oggetti del catalogo (righe <tr>)
 * - liste di riordino nelle impostazioni (righe <li>)
 * Un'unica implementazione condivisa invece di una per ciascun
 * contesto: stessa sensazione al tocco ovunque nell'app, un solo
 * punto da correggere se serve un aggiustamento in futuro.
 *
 * @param {string} containerSelector - contenitori (es. ".item-list[data-reorderable]")
 * @param {string} rowSelector - selettore delle righe trascinabili DENTRO il contenitore
 * @param {string} handleSelector - selettore della maniglia di trascinamento DENTRO ogni riga
 * @param {(rows: Element[]) => void} onDrop - richiamata a rilascio avvenuto, con le righe nel NUOVO ordine
 */
function initDragReorder(containerSelector, rowSelector, handleSelector, onDrop) {
  document.querySelectorAll(containerSelector).forEach((container) => {
    let dragRow = null;
    let placeholder = null;
    let pointerId = null;

    const rowsInOrder = () => Array.from(container.querySelectorAll(rowSelector));

    const makePlaceholder = (row) => {
      const el = document.createElement(row.tagName);
      el.className = "drag-reorder-placeholder";
      el.style.height = `${row.offsetHeight}px`;
      if (row.tagName === "TR") {
        const td = document.createElement("td");
        td.colSpan = row.children.length;
        el.appendChild(td);
      }
      return el;
    };

    const onPointerMove = (e) => {
      if (dragRow === null || e.pointerId !== pointerId) return;
      e.preventDefault();
      // SPOSTAMENTO relativo dal punto di presa, non una posizione
      // assoluta: "translateY" muove l'elemento RISPETTO alla propria
      // posizione naturale, non rispetto alla finestra — usare
      // "e.clientY" da solo (una coordinata assoluta nella pagina)
      // faceva apparire il blocco sempre più lontano dal puntatore
      // quanto più in basso si trovava nella pagina (bug reale
      // segnalato: "lo vedo molto sotto al mouse").
      const deltaY = e.clientY - Number(dragRow.dataset.grabStartY);
      dragRow.style.transform = `translateY(${deltaY}px)`;

      const target = rowsInOrder().find((row) => {
        if (row === dragRow) return false;
        const box = row.getBoundingClientRect();
        return e.clientY < box.top + box.height / 2;
      });
      if (target) {
        container.insertBefore(placeholder, target);
      } else {
        container.appendChild(placeholder);
      }
    };

    const onPointerUp = (e) => {
      if (dragRow === null || e.pointerId !== pointerId) return;
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      document.removeEventListener("pointercancel", onPointerUp);

      container.insertBefore(dragRow, placeholder);
      placeholder.remove();
      dragRow.classList.remove("is-dragging");
      dragRow.style.transform = "";
      dragRow.style.width = "";

      const finishedRows = rowsInOrder();
      dragRow = null;
      pointerId = null;
      onDrop(finishedRows);
    };

    container.querySelectorAll(handleSelector).forEach((handle) => {
      handle.addEventListener("pointerdown", (e) => {
        const row = handle.closest(rowSelector);
        if (!row) return;
        e.preventDefault();

        dragRow = row;
        pointerId = e.pointerId;
        row.dataset.grabStartY = String(e.clientY);

        placeholder = makePlaceholder(row);
        row.after(placeholder);

        row.style.width = `${row.offsetWidth}px`;
        row.classList.add("is-dragging");

        document.addEventListener("pointermove", onPointerMove, { passive: false });
        document.addEventListener("pointerup", onPointerUp);
        document.addEventListener("pointercancel", onPointerUp);
      });
    });
  });
}

/**
 * Finestra di scelta del modello per gli oggetti con Item.has_variants:
 * lo stepper per valigia (identico nell'aspetto a un oggetto normale)
 * non incrementa direttamente al clic su +/- — apre questa finestra,
 * dove si sceglie ESPLICITAMENTE quale modello si sta aggiungendo o
 * togliendo. Senza questo passaggio, il peso di un modello non
 * risultava MAI legato a una valigia specifica (bug reale segnalato:
 * "il peso della valigia non cambia aggiungendo oggetti con modelli").
 */
function initVariantModal() {
  const overlay = document.querySelector("[data-variant-modal-overlay]");
  if (!overlay) return;
  const titleEl = overlay.querySelector("[data-variant-modal-title]");
  const subtitleEl = overlay.querySelector("[data-variant-modal-subtitle]");
  const listEl = overlay.querySelector("[data-variant-modal-list]");
  let currentStepper = null;

  // Guardia di sequenza per TUTTO l'oggetto (non solo per singolo
  // modello): modificare due modelli diversi molto vicini nel tempo fa
  // partire due richieste separate, che possono tornare in ordine
  // diverso — senza questo controllo, la risposta più VECCHIA poteva
  // sovrascrivere per ultima lo stato generale dell'oggetto (colore,
  // avviso "oltre l'obiettivo") con dati ormai superati (bug reale
  // segnalato: l'avviso restava acceso anche dopo essere tornati nel
  // range consentito). Una per trip_item_id, condivisa da tutte le
  // righe/valigie di quello stesso oggetto.
  const itemSeq = new Map();
  function nextItemSeq(tripItemId) {
    const n = (itemSeq.get(tripItemId) || 0) + 1;
    itemSeq.set(tripItemId, n);
    return n;
  }
  function isLatestItemSeq(tripItemId, mySeq) {
    return itemSeq.get(tripItemId) === mySeq;
  }

  const closeModal = () => {
    overlay.style.display = "none";
    currentStepper = null;
  };
  overlay.querySelectorAll("[data-variant-modal-close]").forEach((btn) => btn.addEventListener("click", closeModal));
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  /**
   * Una riga = un modello, per LA VALIGIA che era aperta nel momento in
   * cui la finestra è stata mostrata. `stepperRef`, `tripItemId` e
   * `tripLuggageId` sono catturati QUI (parametri fissi della riga),
   * non riletti da `currentStepper` dentro la risposta del server: se
   * nel frattempo la finestra viene chiusa e riaperta per un'ALTRA
   * valigia, `currentStepper` cambia, ma una risposta arrivata in
   * ritardo per QUESTA riga deve continuare ad aggiornare la valigia a
   * cui si riferiva DAVVERO — altrimenti un salvataggio in corso su
   * "Cabina" poteva ritrovarsi applicato a "Stiva" se nel frattempo si
   * era passati all'altra finestra (bug reale segnalato: valori
   * comparivano senza che l'utente li avesse scelti).
   */
  function buildRow(v, stepperRef, tripItemId, tripLuggageId) {
    const row = document.createElement("div");
    row.className = "variant-modal-row";

    const info = document.createElement("div");
    info.className = "variant-modal-row-info";
    const strong = document.createElement("strong");
    strong.textContent = v.description;
    const span = document.createElement("span");
    info.appendChild(strong);
    info.appendChild(span);

    const stepper = document.createElement("div");
    stepper.className = "qty-stepper";
    const minusBtn = document.createElement("button");
    minusBtn.type = "button"; minusBtn.textContent = "−"; minusBtn.setAttribute("aria-label", "Diminuisci");
    const input = document.createElement("input");
    input.type = "number"; input.inputMode = "numeric"; input.min = "0"; input.readOnly = true; input.tabIndex = -1;
    input.value = String(v.qty_here);
    const plusBtn = document.createElement("button");
    plusBtn.type = "button"; plusBtn.textContent = "+"; plusBtn.setAttribute("aria-label", "Aumenta");
    stepper.appendChild(minusBtn);
    stepper.appendChild(input);
    stepper.appendChild(plusBtn);

    row.appendChild(info);
    row.appendChild(stepper);

    // "Quante ne puoi mettere QUI" dipende da quante sono già nelle
    // ALTRE valigie (v.qty_elsewhere) — si ricalcola SEMPRE con la
    // risposta del server dopo ogni salvataggio, mai lasciato "vecchio".
    function refreshLabel() {
      const maxHere = Math.max(0, v.owned_qty - v.qty_elsewhere);
      const pesoLabel = v.weight_grams ? `${v.weight_grams} g · ` : "";
      const altrove = v.qty_elsewhere > 0 ? ` (${v.qty_elsewhere} già in un'altra valigia)` : "";
      span.textContent = `${pesoLabel}possiedi ${v.owned_qty} in totale${altrove} · qui al massimo ${maxHere}`;
      minusBtn.disabled = Number(input.value) <= 0;
      plusBtn.disabled = Number(input.value) >= maxHere;
      return maxHere;
    }
    let maxHere = refreshLabel();

    // Un contatore PER RIGA: se due richieste per QUESTA stessa riga
    // sono in volo insieme (clic ripetuti veloci) e tornano in ordine
    // diverso da come sono partite, solo la risposta della richiesta
    // PIÙ RECENTE viene applicata — le altre vengono scartate in
    // silenzio (bug reale corretto: uno stato finale incoerente dopo
    // clic multipli ravvicinati).
    let requestSeq = 0;
    let pending = false;

    const send = (value) => {
      value = Math.max(0, Math.min(maxHere, value));
      if (value === Number(input.value) && !pending) return;
      input.value = String(value);
      minusBtn.disabled = true;
      plusBtn.disabled = true;

      const mySeq = ++requestSeq;
      const myItemSeq = nextItemSeq(tripItemId);
      pending = true;

      apiFetch("/api/variante", {
        method: "POST",
        body: JSON.stringify({
          trip_item_id: Number(tripItemId),
          item_variant_id: v.id,
          trip_luggage_id: Number(tripLuggageId),
          quantity: value,
        }),
      }).then((payload) => {
        if (mySeq !== requestSeq) return; // superata da un clic più recente sulla STESSA riga
        pending = false;

        if (!payload || typeof payload !== "object" || !payload.ok) {
          showToast((payload && payload.error) || "Errore di comunicazione con il server: riprova.");
          // Il valore mostrato torna a riflettere l'ultimo dato certo
          // (quanto risulta già confermato altrove, cioè v.qty_here).
          input.value = String(v.qty_here);
          refreshLabel();
          return;
        }
        if (!payload.variant_quantities) {
          showToast("Risposta incompleta dal server: ricarica la pagina per essere sicuro che tutto sia allineato.");
          return;
        }

        v.qty_here = value;

        // Il TOTALE per questo modello, in TUTTE le valigie, secondo il
        // server: da qui si ricava "qui al massimo" per QUESTA riga.
        const freshByLuggage = payload.variant_quantities[v.id] || {};
        const freshTotal = Object.values(freshByLuggage).reduce((a, b) => a + b, 0);
        v.qty_elsewhere = freshTotal - value;
        maxHere = refreshLabel();

        // Lo stato GENERALE dell'oggetto (colore, avviso "oltre
        // l'obiettivo", statistiche) si applica SOLO se questa è
        // ancora la risposta più recente per l'INTERO oggetto — non
        // solo per questa riga — altrimenti una risposta più vecchia
        // per un ALTRO modello potrebbe sovrascrivere per ultima uno
        // stato nel frattempo già aggiornato correttamente.
        if (isLatestItemSeq(tripItemId, myItemSeq)) {
          const itemRow = stepperRef.closest(".item-row");
          if (itemRow) applyRowUpdate(itemRow, payload);
          updateHeaderStats(payload.stats);

          const totals = payload.variant_luggage_totals || {};
          const mainInput = stepperRef.querySelector("input");
          if (mainInput) mainInput.value = totals[tripLuggageId] ?? 0;
        }

        // Propaga il nuovo totale a TUTTI gli stepper di questo stesso
        // oggetto — INCLUSO quello appena usato (stepperRef): il suo
        // "dataset.variants" andava aggiornato anche per SÉ STESSO,
        // non solo per gli altri, altrimenti riaprire la finestra per
        // la STESSA valigia rileggeva ancora i dati del primo
        // caricamento della pagina, mai aggiornati — un salvataggio
        // sembrava "non prendere mai" (bug reale segnalato: azzerare
        // tutto e riaprire la finestra mostrava sempre i numeri
        // vecchi). Così ogni riapertura, per QUALUNQUE valigia, parte
        // sempre dal dato più fresco noto.
        document.querySelectorAll(
          `.qty-stepper--variant-luggage[data-trip-item-id="${tripItemId}"]`
        ).forEach((sibling) => {
          try {
            const siblingVariants = JSON.parse(sibling.dataset.variants || "[]");
            const siblingLuggageId = sibling.dataset.tripLuggageId;
            const match = siblingVariants.find((sv) => sv.id === v.id);
            if (match) {
              match.qty_here = freshByLuggage[siblingLuggageId] || 0;
              match.qty_elsewhere = freshTotal - match.qty_here;
              sibling.dataset.variants = JSON.stringify(siblingVariants);
            }
          } catch (e) {
            /* ignorato: si riallinea comunque al prossimo caricamento pagina */
          }
        });
      }).catch(() => {
        if (mySeq !== requestSeq) return;
        pending = false;
        showToast("Errore di comunicazione con il server: controlla la connessione e riprova.");
        input.value = String(v.qty_here);
        refreshLabel();
      });
    };

    minusBtn.addEventListener("click", () => send(Number(input.value || 0) - 1));
    plusBtn.addEventListener("click", () => send(Number(input.value || 0) + 1));

    return row;
  }

  function renderList(variants, stepperRef, tripItemId, tripLuggageId) {
    listEl.innerHTML = "";
    if (!variants.length) {
      const empty = document.createElement("p");
      empty.className = "text-muted text-sm";
      empty.textContent = "Nessun modello definito per questo oggetto: aggiungine uno dalla pagina del catalogo.";
      listEl.appendChild(empty);
      return;
    }
    variants.forEach((v) => listEl.appendChild(buildRow(v, stepperRef, tripItemId, tripLuggageId)));
  }

  document.querySelectorAll(".variant-modal-trigger").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stepper = btn.closest(".qty-stepper--variant-luggage");
      if (!stepper) return;
      currentStepper = stepper;
      const tripItemId = stepper.dataset.tripItemId;
      const tripLuggageId = stepper.dataset.tripLuggageId;
      titleEl.textContent = stepper.dataset.itemName || "";
      subtitleEl.textContent = `In "${stepper.dataset.luggageName || ""}" — scegli quale modello aggiungere o togliere`;
      let variants = [];
      try {
        variants = JSON.parse(stepper.dataset.variants || "[]");
      } catch (e) {
        variants = [];
      }
      renderList(variants, stepper, tripItemId, tripLuggageId);
      overlay.style.display = "flex";
    });
  });
}

/**
 * Trascinamento a mano della larghezza delle colonne (solo vista
 * testo — con le icone le colonne sono già strette per definizione,
 * regolarle non avrebbe senso). Ogni intestazione resizabile ha un
 * "col-resize-handle" sul proprio bordo destro: trascinarlo sposta
 * larghezza SOLO tra la colonna corrente e quella immediatamente a
 * destra (come un foglio di calcolo), mai le altre — così il totale
 * resta sempre 100% senza dover ricalcolare tutto ad ogni trascinamento.
 * Il risultato si salva da solo al rilascio, per tabella, e resta
 * come default finché non lo si ritocca di nuovo.
 */
/**
 * Spunta "includi nel catalogo pubblico esportabile" — presente nelle
 * tabelle di Oggetti, Categorie e Valigie, sempre con lo stesso
 * comportamento (un'unica funzione, non una per pagina).
 */
function initPublicToggles() {
  document.querySelectorAll("[data-public-toggle]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const tipo = checkbox.dataset.tipo;
      const id = Number(checkbox.dataset.id);
      const isPublic = checkbox.checked;
      checkbox.disabled = true;
      apiFetch("/api/pubblico", {
        method: "POST",
        body: JSON.stringify({ tipo, id, is_public: isPublic }),
      }).then((payload) => {
        checkbox.disabled = false;
        if (!payload || !payload.ok) {
          checkbox.checked = !isPublic; // torna indietro se non salvato
          showToast((payload && payload.error) || "Non salvato: riprova.");
        }
      }).catch(() => {
        checkbox.disabled = false;
        checkbox.checked = !isPublic;
        showToast("Errore di comunicazione con il server: controlla la connessione e riprova.");
      });
    });
  });
}

/**
 * Trascinamento a mano della larghezza delle colonne (solo vista
 * testo — con le icone le colonne sono già strette per definizione,
 * regolarle non avrebbe senso). Ogni intestazione resizabile ha un
 * "col-resize-handle" sul proprio bordo destro: trascinarlo sposta
 * larghezza SOLO tra la colonna corrente e quella immediatamente a
 * destra (come un foglio di calcolo), mai le altre — così il totale
 * resta sempre 100% senza dover ricalcolare tutto ad ogni trascinamento.
 * Il risultato si salva da solo al rilascio, per tabella, e resta
 * come default finché non lo si ritocca di nuovo.
 *
 * IMPORTANTE: la geometria si legge e si scrive SEMPRE sulle <th>
 * (mai su <col>/<colgroup>) — un elemento <col> non è renderizzato
 * come un riquadro normale e `getBoundingClientRect()` su di esso
 * torna quasi sempre {width:0} in ogni browser comune. Un tentativo
 * precedente basato su <colgroup> calcolava quindi percentuali vicine
 * a zero ad OGNI trascinamento (mai un caso limite: sempre), il
 * server le rifiutava (fuori dal range 4%-90%) e nulla veniva mai
 * salvato — bug reale segnalato ("non salva un cazzo", "si prende
 * solo un click e mostra l'errore"). Con `table-layout:fixed`,
 * impostare la larghezza sulle <th> della PRIMA riga basta a
 * controllare tutta la colonna, in ogni riga della tabella.
 */
function initColumnResize() {
  document.querySelectorAll("table[data-resizable-table]").forEach((table) => {
    const wrapper = table.closest("[data-column-style]");
    // Con le icone attive non si trascina nulla: le maniglie restano
    // presenti nel markup ma inerti (nessun listener), per semplicità.
    if (wrapper && wrapper.dataset.columnStyle === "icons") return;

    const tableKey = table.dataset.resizableTable;
    const headerRow = table.querySelector("thead tr");
    if (!headerRow) return;
    const ths = Array.from(headerRow.children);

    const pctWidth = (el) => {
      const rect = el.getBoundingClientRect();
      const tableWidthPx = table.getBoundingClientRect().width;
      return tableWidthPx > 0 ? (rect.width / tableWidthPx) * 100 : 0;
    };

    table.querySelectorAll(".col-resize-handle").forEach((handle) => {
      const colIndex = Number(handle.dataset.colIndex);
      const currentTh = ths[colIndex];
      const nextTh = ths[colIndex + 1];
      if (!currentTh || !nextTh) return;

      let startX = 0;
      let startCurrentPct = 0;
      let startNextPct = 0;
      let dragging = false;

      handle.addEventListener("pointerdown", (e) => {
        // Punto di partenza SEMPRE dalla larghezza REALE renderizzata
        // in questo momento (che sia il default CSS o una larghezza
        // già salvata in precedenza) — mai da un valore "presunto".
        startCurrentPct = pctWidth(currentTh);
        startNextPct = pctWidth(nextTh);
        startX = e.clientX;
        dragging = true;
        handle.setPointerCapture(e.pointerId);
        handle.classList.add("is-resizing");
        e.preventDefault();
      });

      handle.addEventListener("pointermove", (e) => {
        if (!dragging || !handle.hasPointerCapture(e.pointerId)) return;
        const tableWidthPx = table.getBoundingClientRect().width;
        if (tableWidthPx <= 0) return;
        const deltaPct = ((e.clientX - startX) / tableWidthPx) * 100;
        const minPct = 4;
        let newCurrent = startCurrentPct + deltaPct;
        let newNext = startNextPct - deltaPct;
        if (newCurrent < minPct) { newNext -= (minPct - newCurrent); newCurrent = minPct; }
        if (newNext < minPct) { newCurrent -= (minPct - newNext); newNext = minPct; }
        currentTh.style.width = newCurrent + "%";
        nextTh.style.width = newNext + "%";
      });

      const finishDrag = (e) => {
        if (!dragging || !handle.hasPointerCapture(e.pointerId)) return;
        dragging = false;
        handle.releasePointerCapture(e.pointerId);
        handle.classList.remove("is-resizing");

        // Tutte le colonne resizabili (mai la prima, il trascina-riordina,
        // che resta fissa) vanno salvate insieme: sono le <th> da
        // ths[1] in poi, lette ORA dalla loro larghezza REALE renderizzata
        // (che sia stata appena cambiata o no, dato che il trascinamento
        // sposta sempre e solo DUE colonne, mai tutte).
        const widths = ths.slice(1).map((th) => pctWidth(th));
        apiFetch("/api/colonne-larghezza", {
          method: "POST",
          body: JSON.stringify({ table: tableKey, widths }),
        }).then((payload) => {
          if (!payload || !payload.ok) {
            showToast((payload && payload.error) || "Larghezza non salvata: riprova.");
          }
        }).catch(() => {
          showToast("Larghezza non salvata: controlla la connessione e riprova.");
        });
      };
      handle.addEventListener("pointerup", finishDrag);
      handle.addEventListener("pointercancel", finishDrag);
    });
  });
}

function initItemReordering() {
  initDragReorder(".item-list[data-reorderable]", ".item-row", ".drag-handle", (rows) => {
    const orderedTripItemIds = rows.map((row) => Number(row.dataset.tripItemId));
    apiFetch("/api/riordina-oggetti-viaggio", {
      method: "POST",
      body: JSON.stringify({ trip_item_ids: orderedTripItemIds }),
    }).then((payload) => {
      if (!payload.ok) showToast(payload.error || "Riordino non salvato: riprova.");
    });
  });
}

/**
 * Aggiorna periodicamente SOLO le statistiche (quantità/peso per
 * valigia) del workspace: serve soprattutto per le valigie CONDIVISE,
 * il cui contenuto può cambiare per mano di un altro collaboratore
 * senza che il proprio browser abbia modo di saperlo altrimenti. Si
 * ferma quando la scheda non è visibile, per non consumare risorse
 * inutilmente in background.
 */
function initLiveStatsPolling() {
  const tabsWrap = document.querySelector("[data-main-tabs]");
  const tripId = tabsWrap ? tabsWrap.dataset.tripId : null;
  if (!tripId) return;

  const POLL_MS = 8000;

  const poll = () => {
    if (document.visibilityState !== "visible") return;
    fetch(`/viaggi/${tripId}/stats-live`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((payload) => {
        if (payload.ok) updateHeaderStats(payload.stats);
      })
      .catch(() => {});
  };

  // Esposta globalmente: dopo una sincronizzazione riuscita delle
  // modifiche fatte offline (vedi offline.js), i numeri mostrati vanno
  // aggiornati subito con quelli reali del server, non solo al prossimo
  // giro di polling.
  window.refreshLiveStats = poll;

  setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") poll(); // aggiorna subito al ritorno sulla scheda
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initQuantitySteppers();
  initVariantModal();
  initTargetStepper();
  initMissingStepper();
  initWornStepper();
  initDetailPanel();
  initMainTabs();
  initCategoryTabs();
  initShoppingPanelActions();
  initShoppingSearch();
  initHideCompletedToggle();
  initLiveStatsPolling();
  initItemReordering();
  initCatalogItemReordering();
  initColumnResize();
  initPublicToggles();
});

/**
 * Sposta un oggetto su/giù di una posizione DENTRO la sua categoria, nel
 * catalogo (Item.sort_order). A differenza del trascinamento nel
 * workspace di un viaggio (che cambia SOLO TripItem.sort_order per
 * quel viaggio), questo cambia l'ordine del catalogo — che i NUOVI
 * viaggi erediteranno da qui in poi (vedi sync_trip_items).
 */
/**
 * Sposta un oggetto DENTRO la sua categoria, nel catalogo
 * (Item.sort_order), trascinando la riga tramite la maniglia. A
 * differenza del trascinamento nel workspace di un viaggio (che
 * cambia SOLO TripItem.sort_order per quel viaggio), questo cambia
 * l'ordine del catalogo — che i NUOVI viaggi erediteranno da qui in
 * poi (vedi sync_trip_items).
 */
function initCatalogItemReordering() {
  initDragReorder("[data-reorderable-catalog]", "tr", ".drag-handle", (rows) => {
    const orderedItemIds = rows.map((row) => Number(row.dataset.itemId));
    apiFetch("/api/riordina-oggetti", {
      method: "POST",
      body: JSON.stringify({ item_ids: orderedItemIds }),
    }).then((payload) => {
      if (!payload.ok) showToast(payload.error || "Riordino non salvato: riprova.");
    });
  });
}
