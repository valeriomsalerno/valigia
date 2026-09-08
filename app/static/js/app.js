/**
 * app.js
 * ======
 * Comportamenti globali condivisi da tutte le pagine:
 *   - inizializzazione delle icone Lucide
 *   - helper per chiamate fetch() con il token CSRF già impostato
 *   - apertura/chiusura del menu utente nella barra di navigazione
 *   - notifica "toast" per segnalare errori di salvataggio
 */

// Token CSRF letto dal tag <meta> generato in base.html, usato da tutte le
// chiamate fetch() che modificano dati (vedi dashboard.js).
window.CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || "";

/**
 * Wrapper attorno a fetch() che imposta automaticamente Content-Type JSON
 * e l'header CSRF richiesto da Flask-WTF per le richieste non GET.
 *
 * IMPORTANTE: non lascia MAI la Promise "rifiutata" (rejected): un errore
 * di rete o una risposta non-JSON (es. una pagina di errore HTML) vengono
 * convertiti in un normale `{ ok: false, error: "..." }`, così chi chiama
 * questa funzione può sempre gestire l'esito con un solo `.then()`, senza
 * rischiare che un fallimento passi completamente inosservato (bug reale:
 * un valore inserito in uno stepper poteva sembrare salvato mentre la
 * richiesta era in realtà fallita in silenzio — vedi CHANGELOG).
 */
window.apiFetch = function apiFetch(url, options = {}) {
  const opts = Object.assign({}, options);
  opts.headers = Object.assign(
    {
      "Content-Type": "application/json",
      "X-CSRFToken": window.CSRF_TOKEN,
    },
    options.headers || {}
  );
  return fetch(url, opts)
    .then((res) =>
      res.json().catch(() => ({ ok: false, error: "Risposta del server non valida." }))
    )
    .catch(() => {
      // A differenza di una risposta del server che rifiuta l'azione
      // (dati non validi, permessi, ecc. — arriva comunque come JSON,
      // gestita sopra), qui `fetch` stesso non è nemmeno arrivato a
      // destinazione: quasi sempre significa "sei offline". Per le
      // azioni che lo supportano (vedi offline.js), la mettiamo in coda
      // invece di segnalare subito un fallimento.
      if (window.offlineQueue && window.offlineQueue.isEligible(url)) {
        return window.offlineQueue.enqueue(url, opts);
      }
      return { ok: false, error: "Errore di rete: controlla la connessione e riprova." };
    });
};

/**
 * Piccola notifica temporanea in basso, per segnalare in modo visibile
 * (mai più silenzioso) che un salvataggio non è andato a buon fine.
 */
window.showToast = function showToast(message, kind = "error") {
  let wrap = document.querySelector("[data-toast-wrap]");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.setAttribute("data-toast-wrap", "");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
  }
  const toast = document.createElement("div");
  toast.className = `toast toast--${kind}`;
  toast.textContent = message;
  wrap.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("visible"));
  setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
};

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

/**
 * Gestione generica dei menu a tendina (menu utente, menu "Catalogo").
 * Markup atteso:
 *   <div class="dropdown" data-dropdown>
 *     <button data-dropdown-toggle>...</button>
 *     <div class="dropdown-menu" data-dropdown-menu>...</div>
 *   </div>
 */
function initDropdowns() {
  const dropdowns = document.querySelectorAll("[data-dropdown]");
  const closeAllSubmenus = () => {
    document.querySelectorAll("[data-submenu].open").forEach((s) => s.classList.remove("open"));
    document.querySelectorAll("[data-submenu-toggle].open").forEach((b) => b.classList.remove("open"));
  };

  dropdowns.forEach((dropdown) => {
    const toggle = dropdown.querySelector("[data-dropdown-toggle]");
    const menu = dropdown.querySelector("[data-dropdown-menu]");
    if (!toggle || !menu) return;

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains("open");
      dropdowns.forEach((d) => d.querySelector("[data-dropdown-menu]")?.classList.remove("open"));
      closeAllSubmenus();
      menu.classList.toggle("open", !isOpen);
    });
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-dropdown]")) {
      document.querySelectorAll("[data-dropdown-menu]").forEach((m) => m.classList.remove("open"));
      closeAllSubmenus();
    }
  });
}

// Sottomenu ad accordion dentro un dropdown (es. Impostazioni nel menu
// utente): si apre/chiude IN LINEA, senza toccare o chiudere il
// dropdown che lo contiene (a differenza di un [data-dropdown]
// annidato, che verrebbe chiuso dalla logica sopra pensata per un solo
// livello — per questo è un meccanismo volutamente separato).
function initDropdownSubmenus() {
  document.querySelectorAll("[data-submenu-toggle]").forEach((btn) => {
    const submenu = btn.nextElementSibling;
    if (!submenu || !submenu.hasAttribute("data-submenu")) return;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = submenu.classList.contains("open");
      submenu.classList.toggle("open", !isOpen);
      btn.classList.toggle("open", !isOpen);
    });
  });
}

// Invia automaticamente il form del selettore viaggio al cambio selezione.
function initTripSwitcher() {
  const select = document.querySelector("[data-trip-switcher]");
  if (!select) return;
  select.addEventListener("change", () => {
    select.closest("form").submit();
  });
}

/**
 * Menu di navigazione mobile a comparsa (hamburger). Sopra la soglia
 * di 860px il pulsante è nascosto via CSS e questo codice non ha effetto.
 */
function initMobileNavToggle() {
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-topnav]");
  if (!toggle || !nav) return;

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    nav.classList.toggle("open");
  });

  // Chiude il pannello quando si tocca un link (la navigazione avviene comunque).
  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => nav.classList.remove("open"));
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-topnav]") && !e.target.closest("[data-nav-toggle]")) {
      nav.classList.remove("open");
    }
  });
}

/**
 * Precarica in background la pagina di ogni viaggio elencato in questa
 * pagina (Home, Tutti i viaggi), così il service worker le mette in
 * cache automaticamente (vedi app/__init__.py::_register_service_worker)
 * e restano consultabili offline anche se non le hai aperte
 * singolarmente di recente — non serve più "aver già aperto il
 * viaggio" per vederlo offline (bug segnalato).
 *
 * Volutamente delicato: solo se online, un piccolo ritardo per non
 * competere con il caricamento della pagina corrente, e le richieste
 * in sequenza (non tutte insieme) per non sovraccaricare il server.
 */
/**
 * Precarica ESPLICITAMENTE (su richiesta dell'utente, mai da sola) le
 * pagine principali dell'app nella cache del service worker, per l'uso
 * offline. Prima partiva in automatico ogni volta che si apriva Home o
 * Viaggi — cambiato su richiesta esplicita: un precaricamento
 * automatico e silenzioso consuma dati e batteria anche quando non
 * serve (es. si sta solo controllando velocemente qualcosa, non ci si
 * sta preparando per un volo).
 */
function prepareOfflineCache(button, statusEl) {
  if (!navigator.onLine) {
    statusEl.textContent = "Sei offline: connettiti prima di preparare le pagine.";
    return;
  }
  button.disabled = true;
  statusEl.textContent = "Preparo l'elenco delle pagine…";

  fetch("/api/pagine-offline")
    .then((res) => res.json())
    .then((payload) => {
      if (!payload.ok || !payload.urls || !payload.urls.length) {
        statusEl.textContent = "Non ci sono pagine da preparare.";
        button.disabled = false;
        return;
      }
      const urls = payload.urls;
      let done = 0;
      statusEl.textContent = `Scarico 0 di ${urls.length}…`;

      urls
        .reduce(
          (chain, url) =>
            chain.then(() =>
              fetch(url)
                .catch(() => {}) // una singola pagina non raggiungibile non deve fermare le altre
                .finally(() => {
                  done += 1;
                  statusEl.textContent = `Scarico ${done} di ${urls.length}…`;
                })
            ),
          Promise.resolve()
        )
        .then(() => {
          statusEl.textContent = `Fatto: ${urls.length} pagine salvate per l'uso offline.`;
          button.disabled = false;
        });
    })
    .catch(() => {
      statusEl.textContent = "Errore durante la preparazione. Riprova.";
      button.disabled = false;
    });
}

function initOfflinePrepareButton() {
  const button = document.querySelector("[data-prepare-offline-btn]");
  const statusEl = document.querySelector("[data-prepare-offline-status]");
  if (!button || !statusEl) return;
  button.addEventListener("click", () => prepareOfflineCache(button, statusEl));
}

document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  initDropdowns();
  initDropdownSubmenus();
  initTripSwitcher();
  initMobileNavToggle();
  initOfflinePrepareButton();
});
