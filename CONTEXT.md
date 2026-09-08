# CONTEXT.md — Stato del progetto "Valigia"

> **Questo file serve a ripristinare il contesto in una nuova chat.** Se stai
> leggendo questo file come Claude (o altro assistente) all'inizio di una
> nuova conversazione: leggilo TUTTO prima di scrivere codice. Contiene le
> decisioni già prese e il perché, non solo l'elenco delle funzionalità.

**Versione corrente: v3.6.1** (rilasciata 8 settembre 2026). Changelog
completo in `CHANGELOG.md`; versioni precedenti in `changelog/`.

---

## 1. Cos'è questo progetto

Un gestore di "cosa mettere in valigia" per i viaggi, multi-utente (es.
una famiglia). Ogni utente ha il proprio catalogo di oggetti e le proprie
valigie fisiche; i viaggi si possono condividere selettivamente.

Concetti chiave:
- **Catalogo** (Category + Item): personale per utente.
- **Valigia** (`Luggage`): una borsa FISICA che possiedi — marca, nome,
  **tipologia fissa** (cabina/stiva/zaino), peso a vuoto, capacità.
  È l'UNICO concetto di "bagaglio" nell'app (non esiste più un catalogo
  separato di "tipi di bagaglio" astratti come nella v2.0).
- **Viaggio** (`Trip`): meta, date, note — impostazioni CONDIVISE (una
  sola versione), modificabili solo dal proprietario.
- **Lista da mettere in valigia** (`TripItem` + `TripItemQty`):
  **PERSONALE per ogni utente**, anche su un viaggio condiviso. Vedi
  sezione 4 per il motivo e il meccanismo esatto.
- **Lista della spesa**: le stesse righe `TripItem` con `missing_qty >
  0`, ma aggregate e mostrate a TUTTI i collaboratori del viaggio,
  raggruppate per chi è assegnato a comprarle.

## 2. Stack tecnico (invariato dalla v2.0)

Flask 3 + SQLite/Flask-SQLAlchemy + Flask-Login + Flask-WTF. Nessun
framework frontend (Jinja2 + JS vanilla). Gunicorn in Docker. Icone
Lucide via CDN. Immagine di copertina via API pubblica di Wikipedia
(`urllib`, nessuna dipendenza nuova, nessuna chiave richiesta).

**Novità v2.1**: sistema di migrazioni leggere fatto in casa (vedi
sezione 8) — NON è Flask-Migrate/Alembic, è basato su SQL diretto e una
tabella `schema_meta` che ricorda l'ultima migrazione applicata.

## 3. Architettura del codice

```
valigia/
├── app/
│   ├── __init__.py        # application factory, seed admin, migrazioni, filtri Jinja
│   ├── access.py          # admin_required, get_accessible_trip_or_403
│   ├── config.py          # configurazione + APP_VERSION (da aggiornare ad ogni release)
│   ├── extensions.py      # db / login_manager / csrf
│   ├── models.py          # TUTTI i modelli (vedi sezione 4)
│   ├── migrations.py      # migrazioni leggere, applicate ad ogni avvio (vedi sezione 8)
│   ├── forms.py           # WTForms
│   ├── utils.py           # automazioni, sync PERSONALE, statistiche/peso, lista spesa condivisa
│   ├── importer.py        # importazione catalogo di base / CSV Notion (per utente)
│   ├── cli.py              # flask reset-admin-password / import-notion / list-users
│   ├── seed_data/catalogo_base.csv
│   ├── auth/routes.py      # login, logout, cambio password
│   ├── dashboard/routes.py # home a blocchi ("/") + lista della spesa aggregata
│   ├── trips/routes.py     # viaggi, WORKSPACE (/viaggi/<id>), condivisione, valigie del viaggio
│   ├── catalog/routes.py   # categorie, oggetti — scoped per owner_id
│   ├── luggage/routes.py   # sezione Valigie (l'UNICO catalogo di bagagli)
│   ├── users/routes.py     # gestione utenti + profilo (nome completo/nickname)
│   ├── backup/routes.py    # esportazione/ripristino dell'intero database (solo admin)
│   ├── settings/routes.py  # sezione Impostazioni: statistiche CPU/memoria/disco (solo admin) — utenti/backup/cambio password restano nei rispettivi blueprint, il menu li raggruppa
│   ├── api/routes.py       # endpoint JSON: quantita, stato, mancante, obiettivo, assegna-acquisto, nota
│   ├── templates/
│   └── static/
├── scripts/
├── tests/
│   ├── test_smoke.py        # automazioni, sync, isolamento multi-utente, lista spesa per acquirente
│   ├── test_walkthrough.py  # HTTP end-to-end con DUE utenti (isolamento reale via richieste vere)
│   ├── test_migration.py    # verifica che un vecchio DB v2.0 migri SENZA perdita di dati
│   └── test_backup.py       # esportazione/ripristino/validazione file
├── data/                    # volume Docker: valigia.db + backups/ (copie di sicurezza automatiche)
├── changelog/
└── ...
```

## 4. Modello dati e decisioni difficili

Vedi `app/models.py` per i dettagli campo-per-campo. Qui le decisioni
NON ovvie, specialmente quelle della v2.1:

### Perché la lista da mettere in valigia è personale, non più condivisa

Nella v2.0, un viaggio condiviso aveva UN SOLO set di `TripItem`
(quantità, "conservato"): due collaboratori vedevano/modificavano le
STESSE righe — se uno spuntava un calzino come "in valigia", lo vedeva
spuntato anche l'altro. Bug segnalato dall'uso reale ("se un utente
modifica la quantità di un oggetto, anche l'altro utente se la ritrova
modificata... non va bene").

**Soluzione**: `TripItem.item_id` fa sempre riferimento a un `Item` del
catalogo DI CHI STA COMPILANDO quella riga (`TripItem.user_id`), MAI del
proprietario del viaggio. Dato che ogni utente ha il proprio catalogo
(righe `Item` completamente separate, anche con lo stesso nome), la
separazione tra le liste di due collaboratori è **automatica e
strutturale**: non serve nemmeno un controllo esplicito, perché
`item_id` punta fisicamente a righe diverse nel database. Il vincolo
`UniqueConstraint(trip_id, item_id)` su `trip_items` resta valido senza
bisogno di includere `user_id`, perché `item_id` già identifica
univocamente sia l'oggetto SIA il suo proprietario.

Conseguenza pratica: `sync_trip_items(trip, user)` va chiamata per OGNI
utente che apre un viaggio (proprietario o condiviso), non solo per il
proprietario — succede automaticamente ad ogni apertura di
`/viaggi/<id>` (vedi `trips/routes.py::workspace`).

### Perché anche le valigie attive in un viaggio sono personali

Stesso ragionamento: `TripLuggage.luggage_id` fa riferimento a una
`Luggage` (valigia fisica) che appartiene sempre a un utente specifico
(`Luggage.owner_id`). Due collaboratori scelgono le PROPRIE valigie per
lo stesso viaggio, indipendentemente — sensato nella realtà (due persone
diverse portano borse diverse). `TripLuggage.user_id` è denormalizzato
dal proprietario della `Luggage` per query più semplici, ma la vera
fonte di verità è `luggage.owner_id`.

### Perché "BagType" è sparito e cosa lo sostituisce

Nella v2.0 esisteva un catalogo separato "tipi di bagaglio" (astratto,
es. "Valigia da stiva") PIÙ un catalogo di valigie fisiche opzionale. La
v2.1 li unisce: `Luggage` ha un campo `tipologia` (cabina/stiva/zaino,
vedi `LuggageType`) che è l'informazione "a cosa serve", mentre
nome/marca/peso/capacità restano quelli della borsa reale. Non scegli
più un "tipo di bagaglio" astratto per un viaggio: scegli DIRETTAMENTE
quale tua valigia porti (`trips/routes.py::manage_luggage`).

`Item.default_luggage_type` (stringa: 'cabina'/'stiva'/'zaino'/None)
sostituisce il vecchio `default_bag_type_id`: l'automazione ora punta a
una TIPOLOGIA, non più a un bagaglio specifico (che non avrebbe senso
dato che la valigia specifica si sceglie per ogni viaggio).

### Lista della spesa: condivisa ma assegnabile

`TripItem.missing_qty` resta sulla riga PERSONALE di chi l'ha segnalata,
ma `TripItem.assigned_buyer_id` (nullable, un altro collaboratore del
viaggio) permette di dire "questo lo compra Anna anche se l'ho segnalato
io". `trip_shopping_summary(trip)` in `app/utils.py` aggrega TUTTE le
righe con `missing_qty > 0` di TUTTI i collaboratori, raggruppate per
acquirente effettivo (`assigned_buyer_id` se impostato, altrimenti
`user_id`). Un sotto-pannello per collaboratore nel workspace.

### Il campo "obiettivo" (`target_qty`)

Aggiunto perché il numero totale "di quante unità servono" era prima
solo un valore CALCOLATO (somma delle quantità per bagaglio), senza un
riferimento esplicito mentre si distribuiva tra più valigie (ora
possono essere più di 2: cabina + stiva + zaino). `target_qty` è un
numero libero, editabile, pre-compilato dall'automazione ma NON
vincolante: la somma delle quantità nelle valigie può anche non
coincidere, è solo un promemoria.

### Colori di stato — riscritti alla v2.2, estesi alla v2.3

`TripItem.status`, priorità (in quest'ordine):
1. `missing_qty > 0` → rosso "da comprare" (sempre, a prescindere dal resto)
2. `indossato` → verde "in valigia" (v2.3: lo si indossa direttamente,
   non serve alcun obiettivo/quantità nelle valigie)
3. `target_qty` non impostato o 0 → grigio "non necessario"
4. `total_qty >= target_qty` → verde "in valigia"
5. altrimenti → giallo "da preparare"

Interamente automatico dalla v2.2 (vedi sezione 4.5): il vecchio campo
`conservato` (check manuale) NON influisce più sullo stato, resta in
tabella solo per compatibilità con dati storici.

## 4.5. Stato automatico, robustezza JS, riordino (v2.2.0)

### Stato interamente automatico (niente più check manuale)

Dalla v2.2, `TripItem.status` (vedi `app/models.py`) NON dipende più dal
campo `conservato` (rimasto in tabella, per compatibilità con dati
storici, ma inutilizzato): è calcolato solo da `missing_qty` e dal
rapporto `total_qty` (somma nelle valigie) vs `target_qty` (obiettivo).
**Se aggiungi un nuovo criterio di stato, modificalo SOLO in
`TripItem.status` — non reintrodurre logica di stato altrove (route,
template, JS): tutto il resto legge sempre questa unica proprietà.**

### Il pattern "stepper robusto" (app/static/js/dashboard.js)

Ogni stepper (quantità, obiettivo, mancante) passa da
`initRobustStepper()`, che garantisce due cose SEMPRE, per qualunque
nuovo stepper tu aggiunga in futuro:
1. **Sequence guard**: ad ogni invio viene assegnato un numero
   progressivo; una risposta che arriva quando NON è più l'ultima
   richiesta in corso viene scartata. Necessario perché la rete non
   garantisce l'ordine di arrivo delle risposte, specialmente su mobile.
2. **Ripristino su fallimento**: se `payload.ok` è falso, il campo
   torna all'ultimo valore CONFERMATO dal server (mai un valore
   "ottimistico" lasciato a schermo). Vedi il bug reale corretto in
   questa versione, sezione CHANGELOG.

**Qualunque nuovo controllo "al volo" che salva un valore DEVE passare
da `initRobustStepper()` (o comunque implementare le stesse due
garanzie), altrimenti si rischia di reintrodurre lo stesso bug.**

A monte di tutto questo, `window.apiFetch` (app.js) non lascia MAI una
Promise "rifiutata": un errore di rete o una risposta non-JSON vengono
convertiti in `{ ok: false, error: "..." }`. Se in futuro aggiungi
qualunque chiamata `fetch()` che NON passa da `apiFetch`, perdi questa
garanzia — non farlo.

### Riordino manuale (drag&drop) con Pointer Events, non HTML5 DnD

`initItemReordering()` usa l'API **Pointer Events**
(`pointerdown`/`pointermove`/`pointerup`), NON l'HTML5 Drag and Drop
nativo: quest'ultimo funziona male o per niente su iOS/iPadOS Safari,
mentre Pointer Events è supportato in modo uniforme da mouse, touch e
penna. `Item.sort_order` è un campo di CATALOGO (non per-viaggio):
riordinare in un viaggio riordina l'oggetto ovunque compaia raggruppato
per categoria (catalogo incluso). L'endpoint `/api/riordina-oggetti`
rifiuta un riordino che mischia categorie diverse (si può spostare un
oggetto in un'altra categoria SOLO dal Catalogo, mai trascinando).

### Lista della spesa: pattern "frammento" per l'aggiornamento live

`trips/_shopping_panel.html` è un partial usato SIA dentro
`trips/workspace.html` (rendering iniziale) SIA dalla route
`GET /viaggi/<id>/spesa-frammento` (`trips/routes.py::shopping_panel_fragment`),
che ritorna SOLO quel frammento HTML. `refreshShoppingPanel()` in
dashboard.js lo richiama e sostituisce il contenuto del pannello ogni
volta che qualcosa cambia `missing_qty` (stepper "mancante" o pulsante
"Acquistato", ora anch'esso AJAX invece di un form classico). **Se
cambi il markup della lista della spesa, cambialo SOLO nel partial**:
altrimenti i due punti di rendering (iniziale e live) divergono.

## 4.6. Distribuzione sempre manuale, indossato a quantità (v2.4.0)

### La distribuzione tra le valigie non è MAI automatica

Regola fondamentale, violata per errore nelle versioni precedenti e
corretta in questa: `sync_trip_items` e `recompute_automatic_quantities`
(in `app/utils.py`) calcolano **solo** `TripItem.target_qty`.
`TripItemQty.quantity` (quanto va in CIASCUNA valigia) parte SEMPRE da
zero e va SEMPRE compilato a mano dall'utente — mai dedotto
dall'automazione, nemmeno quando `Item.default_luggage_type` è
impostato. **Se in futuro tocchi queste due funzioni, non reintrodurre
mai una scrittura su TripItemQty basata sulla regola quantità
dell'oggetto** (l'unica eccezione legittima è la copia da un viaggio
precedente via `copy_from_trip`, che copia scelte GIÀ fatte a mano
dall'utente in quel viaggio, non un calcolo automatico).

### `Item.default_luggage_type`: solo un avviso, mai un'azione

Da questa versione, questo campo NON sceglie né pre-compila più nulla:
serve solo a mostrare un avviso (`TripItem.has_luggage_mismatch()`,
classe CSS `.has-mismatch`) se l'oggetto finisce in una valigia di
tipologia diversa da quella indicata. Vale per QUALUNQUE regola
quantità (Manuale inclusa), non solo Fissa/Per giorno.

### "Indossato" è una quantità (`indossato_qty`), non un booleano

Si può indossare direttamente più di un'unità di un oggetto (es. 2
maglioni), ma non un numero arbitrario senza senso: da qui la scelta di
uno stepper di quantità invece di un semplice sì/no della v2.3. Conta
insieme a `total_qty` (somma nelle valigie) per raggiungere l'obiettivo
— vedi `TripItem.total_ready_qty = total_qty + indossato_qty`, usata da
`status`/`owned_qty`/`is_overflowing` al posto del solo `total_qty`.
`TripItem.status_label` (property, non più un dizionario esterno
`STATUS_LABELS[status]`) distingue tre varianti del verde: "In valigia"
(solo nelle valigie), "Da indossare" (tutto indossato), "In valigia /
da indossare" (misto) — **se aggiungi un nuovo punto di rendering dello
stato, usa sempre `ti.status_label`, mai un dizionario locale**, per
non perdere questa distinzione (successo già due volte nei template
prima di essere unificato qui).

### Lezione ripetuta: le chiavi di dizionario Jinja non possono
### chiamarsi come i metodi builtin di `dict`

**Secondo bug identico in questa serie di versioni**: un dizionario
Python con chiave `"items"` (o `"keys"`, `"values"`, ecc.) acceduto in
Jinja come `oggetto.items` risolve silenziosamente al METODO builtin
`dict.items`, non al valore della chiave — nessun errore finché non lo
si prova a iterare o a chiamarci `| length` sopra, dove fallisce con un
errore criptico ("no len()" o simile). Il primo caso (giugno, la lista
della spesa) è documentato nel CHANGELOG v2.1.1; il secondo (questa
versione, il catalogo raggruppato per categoria) è stato preso e
corretto prima della consegna. **Prima di scrivere `for x in
dizionario.items` o `dizionario.items | qualcosa` in un template,
verifica SEMPRE che la chiave non si chiami `items`, `keys`, `values`,
`get`, `update` — usa un nome più specifico (es. `catalog_items`,
`missing_items`, `trip_items`).**

### I due bug "funziona solo per un altro utente"

Segnalati come probabili problemi di isolamento tra collaboratori, in
realtà erano entrambi limiti di design che colpivano in modo diverso
utenti con dati diversi (vedi le due voci "Corretto" in cima al
CHANGELOG di questa versione). **Utile promemoria**: prima di sospettare
una fuga di dati tra utenti, verifica se il comportamento dipende dallo
STATO DEI DATI di quell'utente specifico (quanti oggetti ha, quali
obiettivi/quantità ha già impostato) piuttosto che dall'identità
dell'utente in sé.

## 4.7. Menu "Impostazioni" e avviso dinamico (v2.5.0)

**Il menu "Impostazioni" è solo una raggruppazione visiva** (dropdown in
`base.html`, stesso pattern di "Catalogo"): NON è un blueprint che
possiede la logica di Utenti/Backup/Cambio password — quelle restano
nei rispettivi blueprint (`users`, `backup`, `auth`). `app/settings/`
esiste solo per la pagina Statistiche (`/impostazioni/statistiche`),
l'unica funzionalità realmente nuova di questa versione. **Se aggiungi
una nuova pagina "di sistema" in futuro, valuta se le serve un
blueprint proprio o se basta linkarla dal dropdown Impostazioni.**

`db_file_path()` (prima `_db_file_path()` privata di `backup/routes.py`)
è stata spostata in `app/utils.py` perché ora serve a due blueprint
(`backup` e `settings`). **Se in futuro un terzo blueprint ha bisogno
del percorso del database, importalo da lì, non duplicarlo di nuovo.**

**L'avviso "valigia sbagliata" (`has_luggage_mismatch`) deve essere
SIA server-side (rendering iniziale in `workspace.html`) SIA nella
risposta JSON di `/api/quantita` (`_trip_item_payload`'s `mismatches`/
`mismatch_message`)**: la pagina si carica la prima volta dal server,
ma quasi tutte le modifiche successive avvengono via AJAX senza reload
— qualunque informazione mostrata in pagina che possa cambiare in
seguito a un'azione dell'utente deve essere presente in ENTRAMBI i posti,
altrimenti resta "congelata" al valore del caricamento iniziale fino al
prossimo refresh manuale (bug reale corretto in questa versione).## 5. Identità visiva e mobile

Concept "documenti di viaggio" invariato (vedi CSS, variabili colore in
cima al file). **Novità v2.1 rilevanti per non regredire**:
- La barra di navigazione su schermi ≤860px diventa un menu hamburger
  (`.nav-toggle` + `[data-topnav].open`): NON deve mai tornare a un
  `flex-wrap` che fa crescere l'altezza della topbar (era il bug degli
  screenshot iniziali).
- Le righe di pulsanti azione (es. Valigie/Condividi/Modifica) usano
  `.action-scroll` (overflow-x scrollabile) invece di andare a capo o
  tagliarsi ai bordi.
- Il workspace di un viaggio usa `.main-tabs`/`.main-tab-panel` (Valigia
  / Lista della spesa) e `.category-tabs`/`.category-panel` (sotto-schede
  per categoria dentro il pannello Valigia) — entrambi client-side
  (nessun reload), vedi `dashboard.js::initMainTabs`/`initCategoryTabs`.
- **Tutti** i pulsanti/controlli touch hanno `touch-action: manipulation`
  (vedi cima di style.css): NON rimuoverlo — senza, tap ripetuti
  ravvicinati (es. sugli steppers +/-) attivano lo zoom nativo di Safari
  su iOS, bug reale segnalato. Qualunque NUOVO elemento cliccabile
  aggiunto in futuro va incluso in quel selettore comune.

## 4.8. Valigie condivise, copertina personalizzabile (v2.6.0)

### Valigie condivise: come funziona a livello di modello

`TripLuggageShare` collega una `TripLuggage` (di proprietà di un utente,
tramite `luggage.owner_id`) a UN ALTRO utente del viaggio
(`shared_with_user_id`). **Punto chiave**: `TripLuggage.is_usable_by(user_id)`
ritorna vero sia per il proprietario SIA per chi ha ricevuto la
condivisione — e `user_trip_luggages(trip, user)` (usata per gli
steppers nel workspace) usa PROPRIO questo metodo per decidere quali
valigie mostrare. Questo significa che è diventata una funzione più
ampia di "le mie valigie" a "le valigie che POSSO usare": **se aggiungi
un nuovo punto che deve mostrare SOLO le valigie di proprietà
dell'utente (es. `trips/routes.py::manage_luggage`, la pagina "Le tue
valigie"), NON usare `user_trip_luggages()` — filtra direttamente su
`tl.user_id == user.id`**, altrimenti vedrai comparire anche le valigie
altrui condivise, fuori contesto (bug che ho dovuto correggere mentre
implementavo questa funzione).

Il peso/conteggio di una valigia condivisa somma il contributo di TUTTI
gli utenti (`trip_stats()` in `utils.py` interroga `TripItemQty` per
`trip_luggage_id` SENZA filtrare per `user_id`, apposta): dato che una
valigia NON condivisa può fisicamente avere righe `TripItemQty` solo dal
suo proprietario (nessun altro potrebbe averla mai vista come
utilizzabile), questa query "ampia" è corretta e sicura anche per le
valigie non condivise, senza bisogno di un `if is_shared` esplicito.

`/api/quantita` verifica l'accesso con `trip_luggage.is_usable_by(current_user.id)`
(non più solo `trip_luggage.user_id == current_user.id`): un
collaboratore può quindi impostare quantità dei PROPRI TripItem su una
valigia condivisa con lui, anche se non ne è proprietario. Non serve
alcun backfill quando si crea una nuova condivisione: `/api/quantita`
crea la riga `TripItemQty` al volo se non esiste ancora (comportamento
preesistente, riutilizzato).

### Copertina del viaggio: upload, posizione, termini di ricerca

`Trip.cover_image_is_upload` distingue un'immagine caricata a mano da
una trovata automaticamente su Wikipedia: **la ricerca automatica non
tocca MAI una copertina caricata a mano** (vedi il controllo in
`trips/routes.py::edit`), anche se cambiano meta o termini di ricerca —
altrimenti un aggiornamento involontario dei campi del viaggio
sovrascriverebbe la foto scelta dall'utente.

I file caricati vivono in `DATA_DIR / "cover-uploads" / "trip_<id>.<ext>"`
(fuori da `static/`, quindi non pubblicamente indovinabili: serviti solo
tramite `trips.cover_image_file`, che verifica l'accesso al viaggio come
qualunque altra pagina). **Se elimini un viaggio o sostituisci la sua
copertina, richiama sempre `_delete_uploaded_cover_file(trip)`** per non
lasciare file orfani sul disco (fatto sia in `delete()` sia prima di
salvare un nuovo upload).

`Trip.cover_image_position` è una stringa CSS `background-position`
pronta all'uso (es. "25.5% 70.2%"), aggiornata via drag Pointer Events
lato client (`trips/form.html`) e salvata via `/viaggi/<id>/copertina/posizione`.
**Va applicata ovunque compaia un'anteprima della copertina** (workspace,
elenco viaggi, dashboard, form di modifica): sono 4 punti distinti nei
template, tienili sincronizzati se cambi questo meccanismo.

## 4.12. iOS "aggiungi a Home": lo spazio per la barra di stato (v2.9.0)

**Bug critico corretto**: `apple-mobile-web-app-status-bar-style:
black-translucent` (in base.html) fa disegnare la pagina FIN SOTTO la
barra di stato/notch quando l'app è installata sulla schermata Home di
iOS (per un aspetto più simile a un'app nativa) — ma questo richiede che
sia LA PAGINA STESSA a lasciare lo spazio necessario in cima, altrimenti
qualunque elemento fisso/sticky in alto (qui: `.topbar`, con dentro il
menu) finisce nascosto dietro la barra di stato e diventa non
cliccabile. La correzione è `padding-top: env(safe-area-inset-top)` su
`.topbar`: vale 0 in un browser normale (quindi non cambia nulla lì),
ma su iOS installata restituisce l'altezza reale della barra di stato.
**Se in futuro aggiungi un altro elemento fisso/sticky che deve
comparire vicino al bordo SUPERIORE dello schermo (non dentro
`.topbar`), applica lo stesso `env(safe-area-inset-top)`** — e
viceversa `env(safe-area-inset-bottom)` per elementi vicino al bordo
INFERIORE (già fatto per `.toast-wrap`, per via dell'indicatore Home
in basso sugli iPhone senza tasto Home fisico).

## 4.11. Catalogo di base personalizzabile (v2.8.0)

`app/importer.py` distingue ora TRE percorsi: `BASE_CATALOG_PATH`
(CSV originale, imbustato col codice, in sola lettura), il catalogo
PERSONALIZZATO (`_custom_base_catalog_path()`, JSON in `DATA_DIR` —
cartella dati PERSISTENTE, sopravvive agli aggiornamenti dell'immagine
Docker), usato invece del CSV se presente. **Perché JSON e non CSV per
la personalizzazione**: il formato CSV Notion-style non porta regola
quantità/peso/tipologia predefinita (`import_notion_csv` li INDOVINA
dal nome via `KNOWN_PER_DAY_ITEMS`/`KNOWN_FIXED_ITEMS`), quindi non
basta per "promuovere" un catalogo già rifinito con quelle impostazioni
— il JSON le porta esplicitamente, senza indovinare nulla.

`export_catalog_as_base(owner)` e `_import_base_catalog_json()` sono
volutamente SEMPLICI (get-or-create per nome+categoria, stesso pattern
di `import_notion_csv`): se in futuro il modello `Item` guadagna nuovi
campi rilevanti per il catalogo di base, aggiungili in ENTRAMBE le
funzioni (serializzazione in export, lettura in import) o andranno persi
nel giro di esportazione/importazione.

**Le route `catalog.export_base`/`catalog.reset_base` sono
`@admin_required`**: promuovere un catalogo a "base per tutti" è
un'azione che riguarda l'intera installazione, non il singolo utente.

## 4.10. Pallini "da comprare": una regola condivisa, non una a caso (v2.7.1)

**Bug ripetuto una seconda volta**: il pallino rosso col conteggio "da
comprare" ha DUE punti di comparsa (menu in alto, scheda "Lista della
spesa" dentro un viaggio). Il primo era stato corretto (v2.6.0): sempre
presente nel DOM (nascosto via `display:none` quando il conteggio è 0,
mai assente del tutto), per poter essere aggiornato da JS senza
ricaricare la pagina. Il secondo punto NON aveva ricevuto la stessa
correzione, ed inoltre aveva una regola di stile locale incompleta
(solo `background`, senza dimensioni) invece di condividere quella del
primo.

**Corretto strutturalmente**: tutte le dimensioni/forma di QUALUNQUE
pallino di questo tipo vivono ora in un'unica regola base `.badge-count`
in style.css (non più `.topnav .badge-count` / `.main-tab .badge-count`
separate) — **se in futuro serve un pallino simile in un terzo punto,
usa la classe `badge-count` da sola, senza scrivere una nuova regola
"locale" che reinventa (o peggio, reinventa a metà) le dimensioni**. Lato
markup, applica sempre lo stesso pattern per QUALUNQUE badge il cui
conteggio può cambiare via JS senza ricaricare la pagina: l'elemento
va SEMPRE renderizzato nel DOM (mai dentro un `{% if conteggio %}` che
lo fa sparire del tutto), nascosto solo con uno stile inline quando il
conteggio è zero.

## 4.9. Correzioni copertina e aggiornamenti live (v2.7.0)

**Bug reale — background-image sull'elemento sbagliato**: la regola CSS
`.boarding-pass.has-cover .bp-main { background-size: cover; }` è
sempre stata scritta per `.bp-main` (il contenitore INTERNO, quello col
testo), ma lo stile in linea con `background-image`/`background-position`
era finito su `.boarding-pass` (il contenitore ESTERNO, che include
anche la colonna delle statistiche a destra) — un semplice
disallineamento tra dove viene APPLICATA l'immagine e dove la regola
CSS si aspetta di trovarla. Risultato: nessun `background-size`
applicato all'elemento giusto, quindi l'immagine appariva alla sua
dimensione originale (spesso molto più grande/con proporzioni diverse
dal riquadro), sembrando "zoomata e sfalsata". **Lezione**: quando una
regola CSS `.classe-A .classe-B { ... }` esiste già, lo stile in linea
correlato (background-image, ecc.) va sempre applicato ALLA STESSA
classe (`.classe-B`), mai a un antenato o discendente diverso — sembra
ovvio ma è un errore facile da fare quando si copia/sposta markup tra
sessioni di sviluppo diverse (esattamente cosa è successo qui).

**Ricerca immagine "live"**: `trips.refresh_cover` ora accetta
`{destination, search_terms}` nel BODY della richiesta (JSON) invece di
leggerli SEMPRE dal database — fondamentale perché l'utente può aver
scritto qualcosa nel modulo senza ancora premuto "Salva viaggio". Se in
futuro aggiungi un'altra azione che dipende da campi di un modulo NON
ancora salvato, applica lo stesso principio: leggi il valore dal DOM
lato client e mandalo esplicitamente, non fare affidamento su cosa c'è
già salvato lato server.

**Polling per le valigie condivise**: `GET /viaggi/<id>/stats-live`
(solo le statistiche, niente HTML) + `initLiveStatsPolling()` in
dashboard.js, ogni 8 secondi, in pausa quando `document.visibilityState
!== "visible"`. È un polling deliberatamente semplice (non WebSocket/SSE):
per un'app di uso familiare con pochi utenti contemporanei è più che
sufficiente, e non richiede nuova infrastruttura. **Se in futuro serve
un aggiornamento live di qualcos'altro di condiviso tra utenti, valuta
prima se un polling leggero come questo basta, prima di introdurre
WebSocket/SSE.**

## 4.13. Modifiche offline (coda locale + sincronizzazione)

**Perché questo approccio e non altri**: discussi con l'utente tre
alternative (cache sola-lettura; coda locale con sync differita;
architettura "offline-first" con database locale) — scelta la coda
locale come compromesso tra valore reale e sforzo di implementazione.
**Limite consapevole e accettato**: solo un sottoinsieme di azioni è
in coda offline (vedi `ELIGIBLE_PATHS` in `static/js/offline.js`:
`/api/quantita`, `/api/obiettivo`, `/api/mancante`, `/api/indossato`,
`/api/variante` — le quattro/cinque azioni più frequenti mentre si
prepara una valigia). Condivisione, gestione utenti, creare un
viaggio, caricare un'immagine restano a corta connessione: **prima di
aggiungere un nuovo endpoint alla lista `ELIGIBLE_PATHS`, verifica che
la sua risposta JSON contenga già tutto il necessario per un
aggiornamento "ottimistico" della UI** (vedi sotto), altrimenti
l'utente vedrà un valore accettato ma nessun feedback visivo fino alla
sincronizzazione.

**iOS non supporta la Background Sync API** (differenza nota rispetto
a Chrome/Android): la sincronizzazione NON riparte da sola se l'app è
chiusa in background — riparte quando l'app torna in PRIMO PIANO con
connessione (`visibilitychange` + evento `online` + retry periodico
ogni 20s, vedi `offline.js`). Documentato esplicitamente nei commenti
del file e va tenuto a mente per qualunque nuova funzione offline.

**Aggiornamento "ottimistico" volutamente parziale**: `apiFetch` (in
`app.js`) distingue un vero errore di rete (fetch stesso fallisce, es.
offline) da un rifiuto esplicito del server (risposta JSON con
`ok:false`, es. validazione). Solo il primo caso finisce in coda. Una
volta in coda, `initRobustStepper` (dashboard.js) TIENE il valore
scritto dall'utente (non lo annulla) ma NON simula lo stato calcolato
dal server (colore, statistiche aggregate, avvisi di valigia
sbagliata) — richiederebbe reimplementare in JS tutta la logica di
stato che oggi vive solo in Python (`TripItem.status`,
`has_luggage_mismatch`, `trip_stats`), rischiando derive tra le due
implementazioni nel tempo. La riga resta visivamente "in sospeso"
(bordo tratteggiato ambra, classe `.is-pending-sync`) finché non
arriva la vera risposta dal server alla sincronizzazione.

**"Ultimo scritto vince"**: nessun tentativo di unire conflitti se nel
frattempo un altro utente ha modificato la stessa cosa (rilevante
soprattutto per le valigie condivise). Se in futuro serve gestire i
conflitti, andrebbe innanzitutto capito COSA deve succedere quando due
modifiche in conflitto arrivano — non è stato implementato perché non
ha una risposta ovvia, non per dimenticanza.

Il service worker (`app/__init__.py::_register_service_worker`,
servito da `/sw.js`, non da `/static/`) si occupa SOLO della
consultazione offline delle pagine già visitate (cache "man mano che
si naviga", nessuna lista di file da tenere aggiornata a mano) — non
tocca MAI le richieste di scrittura, quelle restano di competenza di
apiFetch + la coda. La sua cache è legata a `APP_VERSION`
(`app/config.py`): si invalida da sola ad ogni nuova versione, niente
da fare manualmente ad ogni rilascio.

**Aggiornamento v3.0.1 — pagina di fallback + precaricamento**: una
navigazione verso una pagina MAI messa in cache prima ora mostra
`/offline-non-disponibile` (route pubblica, senza `@login_required`:
va sempre raggiungibile, anche prima di un login, perché viene messa
in cache all'INSTALLAZIONE del service worker) invece di sostituire
silenziosamente con la Home (bug reale: sembrava un link "rotto", non
un limite chiaro). **Se cambi questa route, ricontrolla che resti
raggiungibile SENZA autenticazione**, altrimenti il fallback stesso
fallirebbe offline.

`warmTripCache()` in `static/js/app.js` mitiga il limite di fondo
("si vede offline solo ciò che è già stato aperto online"):
quando sei online e apri Home/Tutti i viaggi, precarica in
BACKGROUND (in sequenza, con un piccolo ritardo, per non competere con
la pagina corrente né sovraccaricare il server) ogni link
`/viaggi/<id>` trovato in pagina — il service worker li mette in cache
come effetto collaterale della richiesta, nessuna logica dedicata
serve lato server. **Se aggiungi un'altra pagina che elenca link
importanti da rendere disponibili offline, valuta se estendere questa
stessa funzione (matching su un pattern URL diverso) invece di scrivere
un meccanismo di precaricamento parallelo.**

## 4.16. Tabelle responsive, ordinamento separato, viaggio più vicino (v3.1.0)

**Tabelle responsive: risolto alla radice, non più a colpi di
larghezze**. Dopo vari tentativi falliti di tarare percentuali/pixel
per far entrare le tabelle su mobile (il problema di fondo: i pulsanti
hanno una larghezza minima che nessuna percentuale stretta può
rispettare), la soluzione è stata cambiare interamente STRATEGIA: sotto
i 680px, ogni riga di una tabella con classe `responsive-stack`
diventa una scheda verticale (etichetta a sinistra, valore a destra),
tramite `content: attr(data-label)` sui `<td>` — non serve più
scegliere larghezze di colonna per il mobile, il problema è strutturale,
non di tuning. **Ogni nuova tabella `simple-table` va SEMPRE dotata di
questa classe + `data-label` sui `<td>` che ne hanno bisogno** (il
primo e l'ultimo, di norma nome e azioni, non ne hanno bisogno per
default — la classe li esenta automaticamente dall'etichetta).
`table.catalog-items-table` mantiene le proprie percentuali fisse SOLO
per il layout desktop (sopra i 680px); sotto quella soglia,
`responsive-stack` prende il sopravvento e le percentuali non contano
più.

**Ordinamento: due campi distinti, non uno condiviso**. Prima
esisteva SOLO `Item.sort_order` (catalogo), e il trascinamento nel
workspace di un viaggio lo modificava DIRETTAMENTE — un cambiamento in
UN viaggio si propagava a TUTTI gli altri viaggi e al catalogo (bug
reale, mai notato prima perché nessuno aveva ancora provato a
riordinare in due viaggi diversi). Aggiunto `TripItem.sort_order`,
inizializzato dal valore CORRENTE di `Item.sort_order` al momento
della creazione (in `sync_trip_items`) e poi completamente
indipendente. **Due endpoint distinti, non uno condizionale**:
`/api/riordina-oggetti` (Item.sort_order, dal catalogo, con pulsanti
su/giù) e `/api/riordina-oggetti-viaggio` (TripItem.sort_order, dal
trascinamento nel workspace) — tenerli separati rende esplicito e
verificabile QUALE ordine si sta cambiando, invece di dedurlo da un
parametro opzionale.

**Perché pulsanti su/giù nel catalogo e non il trascinamento**: il
trascinamento del workspace (`initItemReordering` in dashboard.js) è
pensato per righe `.item-row` con `display:flex` — su una vera
`<table>` (il catalogo), applicare lo stesso meccanismo di trascinamento
(basato su `transform:translateY` durante il drag) è meno affidabile
sulle righe `<tr>`, che si comportano diversamente in un contesto di
tabella. I pulsanti su/giù (`initCatalogItemReordering`) evitano questo
rischio, funzionano identicamente sia nel layout a tabella (desktop)
sia in quello a schede (`responsive-stack`, mobile) senza bisogno di
alcun adattamento per il touch.

## 4.31. `<col>` non ha geometria: perché il trascinamento non salvava mai (v3.6.1)

**Causa esatta**: la v3.6.0 misurava/scriveva la larghezza sugli
elementi `<col>` dentro `<colgroup>` — ma un `<col>` non è
renderizzato come un riquadro normale nel DOM: `getBoundingClientRect()`
su di esso torna `{width:0}` in ogni browser comune (Chrome, Safari,
Firefox), SEMPRE, non in un caso limite. Risultato: ogni tentativo di
trascinamento calcolava percentuali vicine allo zero, il server le
rifiutava correttamente (fuori dal range 4%-90%), e nulla veniva mai
salvato — il che spiegava insieme "non salva", "si prende solo un
clic e mostra l'errore" (bug reale segnalato con parole dure, a ragione:
la funzione era completamente inutilizzabile, non solo imperfetta).
**Corretto spostando OGNI misurazione/scrittura di geometria dalle
`<col>` alle `<th>`** (che hanno sempre geometria reale) — grazie a
`table-layout:fixed`, impostare la larghezza sulle `<th>` della prima
riga controlla comunque l'intera colonna in ogni riga della tabella,
esattamente come un `<colgroup>` avrebbe dovuto fare ma senza il
problema di misurazione. **Lezione per il futuro: mai usare
`getBoundingClientRect()` su un `<col>` o un `<colgroup>` per NESSUN
motivo — sono elementi "di intenzione" per il browser, non riquadri
renderizzati, e la loro geometria letta da JS non è affidabile.**

**Maniglia resa visibile di default**, non solo al passaggio del
mouse: un bordo che si vede solo dopo averlo già trovato per caso non
è un bordo trascinabile in pratica (bug reale segnalato, "non si vede
il bordo").

**Catalogo pubblico riorganizzato su richiesta esplicita**: le spunte
sono sparite dalle pagine principali del catalogo (Oggetti, Categorie,
Valigie) — vivono ORA SOLO in una pagina dedicata
(`/impostazioni/catalogo-pubblico`, solo admin), un elenco spoglio di
nomi + spunta, senza altre informazioni. Le vecchie route
`catalog.export_base`/`download_base`/`reset_base` sono state RIMOSSE
(non solo nascoste) e sostituite dalle loro controparti in
`settings_bp`, raggiungibili solo dal collegamento "Configura catalogo
pubblico" nel menu Impostazioni (visibile solo agli admin).


**Larghezza colonne a mano, solo per il catalogo oggetti per ora**:
`User.table_column_widths_json` (dizionario `{chiave_tabella: [percentuali]}`)
+ un `<colgroup>` con `<col>` per colonna (l'unico modo pulito per
sovrascrivere le percentuali CSS di default PER UTENTE, dato che le
regole `nth-child` sono statiche) + una maniglia (`.col-resize-handle`)
sul bordo destro di ogni intestazione ridimensionabile.
**Trascinare sposta larghezza SOLO tra la colonna corrente e quella
immediatamente a destra** (come un foglio di calcolo) — mai
ridistribuita su tutte, altrimenti ogni trascinamento richiederebbe
ricalcolare l'intera riga. L'endpoint `/api/colonne-larghezza` accetta
solo chiavi da un elenco esplicito (`_COLUMN_WIDTH_TABLES`), non
qualunque stringa: evita che il campo JSON si riempia di chiavi
arbitrarie nel tempo. **Pensato per essere esteso ad altre tabelle in
futuro seguendo lo stesso schema** (nuova chiave nell'elenco, nuovo
`<colgroup>`+maniglie nel template corrispondente) — implementato per
ora solo sul catalogo oggetti, l'unico esplicitamente segnalato.

**Catalogo pubblico/privato — un sistema che si aggancia a codice
GIÀ ESISTENTE ma mai completato**: `export_catalog_as_base()` e
`import_base_catalog_for_user()` esistevano già (persistono un
catalogo di base personalizzato in `DATA_DIR/catalogo_base.json`, usato
per ogni nuovo utente) — ma la funzione di export prendeva TUTTO il
catalogo dell'admin, senza modo di escludere nulla, e non era
raggiungibile da nessuna UI collegata a spunte selettive. Aggiunto
`is_public` (default `False`) su `Category`/`Item`/`Luggage`, un
endpoint unico `/api/pubblico` (un solo `tipo` tra
oggetto/categoria/valigia, non tre endpoint separati) per la spunta, e
filtrato l'export per usare SOLO ciò che è spuntato. **Esteso anche
l'IMPORT per gestire modelli (ItemVariant) e valigie**, che prima non
venivano portati nel catalogo di base per niente (solo categorie e
oggetti) — un salto di qualità rispetto a prima, non solo un filtro in
più.

**Un oggetto pubblico con la categoria NON pubblica non deve sparire
nel nulla**: `export_catalog_as_base` promuove automaticamente ANCHE la
categoria (aggiungendola all'export) se contiene almeno un oggetto
spuntato — comportamento più prevedibile che scartare silenziosamente
l'oggetto per mancanza della sua categoria nell'export.

**Il file esportato resta scaricabile** (`/catalogo/oggetti/catalogo-base/scarica`,
`send_file`) apposta per poter essere portato fuori dall'app (su
GitHub, nella cartella `app/seed_data/`) — a differenza del resto del
catalogo di base personalizzato, che vive SOLO in `DATA_DIR` (mai
committato, per la separazione tra codice e dati che regge tutta
l'architettura Docker di questo progetto).

**Un bug commesso e trovato subito con la verifica dal vivo**:
`toggle_public` usava `Item`/`Category`/`Luggage` senza il rispettivo
`from app.models import` locale all'interno della funzione (pattern
già usato altrove nel file, ma dimenticato qui) — un `NameError` a
runtime, non rilevato dai test automatici scritti PRIMA (che
chiamavano `export_catalog_as_base` direttamente in Python, MAI
attraverso l'endpoint HTTP). **Lezione ribadita ancora una volta**: un
nuovo endpoint API richiede SEMPRE un test che lo chiami DAVVERO
tramite il client HTTP (`client.post(...)`), non solo un test della
funzione interna che finisce per richiamare — sono percorsi di codice
diversi, e gli errori di import locali si vedono SOLO passando dalla
route reale.


**Scelta deliberata: rimedio pratico, non un'ennesima caccia alla
causa esatta**. Dopo diversi bug reali già trovati e corretti sulla
gestione delle quantità (cascade mancanti, finestra che non
aggiornava sé stessa), potevano comunque restare residui in database
già esistenti creati DURANTE il periodo in cui quei bug erano attivi
— dati tecnicamente "validi" (nessun vincolo violato) ma che non
corrispondono più a nulla di intenzionale da parte dell'utente. Invece
di continuare a inseguire un'origine precisa caso per caso, due
pulsanti permettono un rimedio diretto e sempre disponibile:
`reset_trip_item` (un oggetto, dal pannello di dettaglio) e
`reset_all_trip_items` (tutti gli oggetti del viaggio, dalla pagina di
modifica).

**Cosa viene azzerato e cosa no, e perché**: quantità per valigia
(`TripItemQty`), quantità per modello in OGNI valigia
(`TripItemVariantQty`), e indossato — MAI l'obiettivo (`target_qty`)
né "da comprare" (`missing_qty`), che sono SCELTE dell'utente, non
dati "da riempire" durante la preparazione. Azzerare anche quelli
sarebbe stato più aggressivo del necessario e avrebbe cancellato
informazioni intenzionali insieme ai residui indesiderati.

**Implementazione volutamente "pesante" (submit di form classico, mai
AJAX)**: entrambi i pulsanti fanno un POST tradizionale con redirect,
NON una chiamata JS che aggiorna lo stato in pagina — data la serie di
bug di sincronizzazione client-side già trovati in quest'area (finestra
che non si aggiornava da sola, race condition tra richieste), un
ricaricamento COMPLETO della pagina dopo un azzeramento è la garanzia
più semplice e affidabile che l'utente veda SEMPRE lo stato vero, senza
dover fidarsi di nessuna logica di aggiornamento incrementale lato
client.


**Causa esatta del bug segnalato** ("anche portando tutto a zero e
cliccando su Fine, riaprendo la finestra i numeri sono sempre lì"):
dopo un salvataggio riuscito, il codice propagava i dati freschi
(`payload.variant_quantities`) a TUTTI gli altri stepper dello stesso
oggetto (`sibling.dataset.variants = ...`), ma con un
`if (sibling === stepperRef) return;` che escludeva ESPLICITAMENTE lo
stepper DA CUI il salvataggio era partito. Il valore in memoria (`v.qty_here`)
veniva sì aggiornato per la sessione CORRENTE della finestra aperta,
ma MAI scritto nel `dataset.variants` dell'elemento — che è dove
`renderList()` legge i dati ogni volta che la finestra viene
RIAPERTA. Risultato: chiudere e riaprire la finestra per la STESSA
valigia rileggeva sempre l'istantanea del PRIMO caricamento della
pagina, mai aggiornata — un salvataggio sembrava "non prendere mai",
anche se il server lo aveva accettato correttamente (i log di
produzione mostravano infatti risposte 200/ok per ogni richiesta).

**Lezione**: quando uno stato viene propagato a "tutti gli elementi
simili", non escludere MAI per abitudine l'elemento di partenza
pensando sia "già aggiornato per conto suo" — verificare sempre se
quell'aggiornamento avviene in un posto che sopravvive a un'eventuale
ricostruzione futura dell'elemento (qui: la ricostruzione avveniva ad
ogni riapertura della finestra, `listEl.innerHTML = ""` seguito da un
nuovo parsing di `dataset.variants`) o solo in una variabile locale
temporanea che sparisce.


**Causa esatta del bug segnalato** ("il conteggio si aggiorna ma i
modelli restano al numero originario"): `initQuantitySteppers()`
seleziona `.qty-stepper[data-trip-luggage-id]` per agganciare la
logica generica (`/api/quantita`, per oggetti SENZA modelli). Lo
stepper per valigia di un oggetto CON modelli ha la STESSA classe
base (`qty-stepper`) e lo STESSO attributo (`data-trip-luggage-id`) —
senza un'esclusione esplicita, quel selettore matchava ANCHE questo
stepper, agganciando `initRobustStepper` (che ascolta
`button[data-step]`) AGLI STESSI pulsanti +/- che
`initVariantModal()` usa per aprire la finestra di scelta modello.
Risultato: un clic attivava DUE gestori insieme — uno chiamava
`/api/quantita` (sbagliato per un oggetto con modelli, ma comunque
capace di aggiornare il numero mostrato in ottimistico), l'altro apriva
correttamente la finestra — le due cose non si parlavano, quindi il
numero cambiava ma i modelli mostrati nella finestra restavano quelli
di prima.

**Corretto su due fronti, non uno solo**: (1) il selettore di
`initQuantitySteppers()` ora esclude esplicitamente
`.qty-stepper--variant-luggage` — `":not(...)"` nella query, commentato
per bene sul PERCHÉ; (2) i pulsanti `.variant-modal-trigger` non hanno
più l'attributo `data-step` (non serviva a `initVariantModal` — apre
la finestra a prescindere da quale pulsante viene premuto — ma la sua
sola presenza era l'esca che permetteva al gestore generico di
agganciarsi). **Lezione: quando due componenti diversi condividono
intenzionalmente una classe base per ereditare uno stile visivo (qui:
`.qty-stepper` per l'aspetto), verifica SEMPRE che i rispettivi
selettori JS non si sovrappongano per errore — condividere una classe
CSS non significa condividere il comportamento.**


**Causa esatta del bug segnalato** (uno stepper mostrava un numero,
es. 5, ma la finestra di scelta modello elencava OGNI modello a 0, e
l'obiettivo risultava "superato" nonostante la somma visibile fosse
ben sotto il limite): `TripItemVariantQty` ha DUE genitori — la
valigia (`trip_luggage_id`) E il modello (`item_variant_id`).
_migrate_to_v15/v3.3.3 aveva corretto il cascade mancante SOLO sul
lato valigia (`TripLuggage.variant_quantities`); il lato MODELLO
(`ItemVariant` → `TripItemVariantQty`) non aveva MAI avuto una
relazione, tantomeno un cascade — eliminare (o sostituire) un modello
dal catalogo lasciava le sue quantità già portate in viaggio "appese",
CONTATE nel totale ma invisibili in QUALUNQUE finestra (che elenca
solo i modelli ancora esistenti dell'oggetto).

**Lezione, questa volta generalizzata con un controllo sistematico,
non solo corretta puntualmente**: dopo aver trovato il secondo caso
dello stesso tipo di bug, è stato fatto un audit di TUTTE le relazioni
del modello dati (`grep db.ForeignKey` + verifica incrociata di ogni
relazione genitore) per escludere altri casi simili — nessun altro
trovato, tutte le altre relazioni avevano già `cascade="all,
delete-orphan"` corretto. **Regola pratica per il futuro: quando una
tabella ha PIÙ di una colonna ForeignKey (qui: due, verso
`trip_luggage` e verso `item_variants`), serve una relazione con
cascade su ENTRAMBI i lati genitore, non solo su uno — è facile
implementarne uno e dimenticare l'altro, dato che il primo già
"risolve" il sintomo più visibile al momento.**

Stessa doppia correzione della volta precedente: relazione mancante
aggiunta (previene il problema d'ora in poi) + migrazione dedicata
(`_migrate_to_v16`) che ripulisce le righe già orfane nei database
esistenti.


**Causa strutturale di più sintomi insieme** (valori mai scelti
dall'utente comparsi nella finestra, "−" che non aggiornava i valori,
avviso "oltre l'obiettivo" rimasto acceso dopo essere rientrati nel
range): la vecchia `send()` catturava correttamente il contesto
(trip_item_id, trip_luggage_id) al MOMENTO della richiesta, ma
RILEGGEVA `currentStepper` (una variabile MUTABILE, condivisa da
tutta la finestra) DENTRO la risposta asincrona — se nel frattempo
l'utente chiudeva la finestra e ne apriva un'altra per una valigia
diversa, `currentStepper` cambiava, e una risposta arrivata in
ritardo per la valigia PRECEDENTE si applicava alla valigia ORA
aperta. **Corretto catturando `stepperRef`/`tripItemId`/`tripLuggageId`
come parametri FISSI di ciascuna riga** (passati a `buildRow` alla sua
creazione, mai riletti da una variabile condivisa dentro un `.then()`).

**Due livelli di guardia di sequenza, non uno solo**: oltre a uno scarto
delle risposte fuori ordine per la STESSA riga (`requestSeq`, già
presente), è stato aggiunto un contatore CONDIVISO per TUTTO
l'oggetto (`itemSeq`, una `Map` chiave trip_item_id) — necessario
perché lo stato generale dell'oggetto (colore, avviso obiettivo) può
essere aggiornato da QUALUNQUE modello di quell'oggetto: modificarne
due vicini nel tempo genera due richieste separate che possono
tornare in ordine diverso, e senza un contatore CONDIVISO tra le
righe, la risposta più vecchia (per un modello diverso) poteva
sovrascrivere per ultima uno stato nel frattempo già aggiornato
correttamente da una risposta più recente. **Se aggiungi altre azioni
concorrenti che aggiornano uno stato CONDIVISO tra più elementi
indipendenti, replica questo pattern (contatore condiviso, non solo
per singolo elemento).**

**Layout della finestra reso strutturalmente robusto, non solo
corretto per il caso visto**: la riga era `display:flex` orizzontale
(etichetta a sinistra, stepper a destra) — con una descrizione lunga
combinata al testo "già in un'altra valigia", lo stepper (incluso il
pulsante +) poteva finire tagliato fuori dal bordo della finestra (bug
reale segnalato). Cambiato a impilamento VERTICALE (etichetta sopra,
stepper sotto, allineato a destra): lo stepper resta SEMPRE
interamente visibile, a QUALUNQUE lunghezza di descrizione — non serve
più indovinare quanto spazio riservare al testo.

**L'input di ogni riga è ora di sola lettura** (`readOnly`, niente
`change` da tastiera): l'unico modo di cambiare un valore è +/-, che
già passano dalla convalida server (limite rispetto al posseduto) —
digitare liberamente avrebbe permesso di scrivere un numero non ancora
verificato, un'altra fonte di stati temporaneamente incoerenti.


**Causa esatta del bug segnalato** ("c'è un errore sull'obiettivo che
non ha senso", stato "in valigia" nonostante gli stepper visibili
sommassero molto meno dell'obiettivo): `TripLuggage.quantities`
(→ `TripItemQty`, oggetti SENZA modelli) ha sempre avuto
`cascade="all, delete-orphan"` — ma quando sono stati introdotti i
modelli legati a una valigia (v3.3.0), la relazione ANALOGA per
`TripItemVariantQty` non è mai stata creata. Eliminare una valigia
cancellava correttamente le quantità NORMALI, ma lasciava "appese" le
quantità dei MODELLI in quella valigia — invisibili in qualunque
stepper (che elenca solo le valigie ancora esistenti), ma
`TripItem.variants_total_qty` le sommava UGUALMENTE (nessun controllo
su quali `trip_luggage_id` fossero ancora validi), gonfiando lo stato
mostrato. **Riprodotto e verificato con i numeri ESATTI dello
screenshot segnalato** (6 in Cabina + 1 in Stiva = 7 visibili, ma un
totale reale di 13 per una valigia fantasma da 6 unità, eliminata in
precedenza) — prima della correzione lo stato restava "conservato"
nonostante il vero totale visibile fosse 7 contro un obiettivo di 13.

**Lezione: quando aggiungi una relazione "quantità per contenitore"
parallela a una già esistente (qui: TripItemVariantQty accanto a
TripItemQty, entrambe legate a TripLuggage), replica SEMPRE lo stesso
comportamento di cascade — non solo la struttura delle colonne.**
Un controllo utile per il futuro: cercare `cascade="all, delete-orphan"`
su `TripLuggage` e verificare che OGNI relazione "quantità" lì elencata
abbia la sua controparte.

**Doppia correzione, non solo per il futuro**: aggiunta la relazione
mancante (previene il problema d'ora in poi) E una migrazione dedicata
(`_migrate_to_v15`) che ripulisce le righe GIÀ orfane nei database
esistenti — aggiungere solo la relazione avrebbe risolto il problema
per le eliminazioni future, ma non per i dati già in questo stato in
produzione.


**Causa dell'errore 500 in produzione** ("UNIQUE constraint failed:
trip_item_variant_qty.trip_item_id, trip_item_variant_qty.item_variant_id"):
`_migrate_to_v9` aveva creato la tabella con `UNIQUE(trip_item_id,
item_variant_id)` — corretto FINCHÉ un modello non era legato a una
valigia. `_migrate_to_v13` ha aggiunto `trip_luggage_id` con
`_add_column` (che può solo AGGIUNGERE una colonna, mai toccare un
vincolo esistente), lasciando quel vecchio vincolo a 2 colonne
ATTIVO — bloccando qualunque tentativo di salvare lo stesso modello in
una SECONDA valigia. **Lezione strutturale, non solo un bug
puntuale**: `_add_column` non basta MAI quando cambia anche un
vincolo (UNIQUE, CHECK, NOT NULL) — serve SEMPRE ricostruire la
tabella (rename → create con lo schema corretto → copia dati → drop),
esattamente come già documentato per `_migrate_to_v4` (stesso identico
tipo di problema, con `trip_item_qty.trip_bag_id NOT NULL`, mai
generalizzato in una regola esplicita finché non si è ripetuto qui.
**Prima di scrivere `_add_column` per una nuova colonna, chiediti
sempre: questa modifica richiede ANCHE di cambiare un vincolo
esistente? Se sì, va ricostruita la tabella, non basta aggiungere.**

**Perché i test non l'avevano preso**: la suite normale crea il
database di test con `db.create_all()` DIRETTAMENTE dai modelli
correnti (che hanno già il vincolo giusto) — non passa MAI dal
percorso di migrazione, quindi non può accorgersi di un vincolo
vecchio rimasto attivo in un DATABASE REALE già esistente. **Per ogni
bug di migrazione, serve un test in `test_migration.py` che scriva a
mano lo schema VECCHIO (con `sqlite3.connect` + `executescript`,
MAI tramite i modelli) e verifichi che, dopo `run_migrations`, l'azione
che falliva in produzione ora funzioni — un test che passa su un
database creato da zero non prova nulla sul percorso di aggiornamento.**


**"Massimo qui" poteva restare sbagliato per tutta la visita**: i dati
per la finestra (`data-variants` su ogni stepper) sono calcolati UNA
VOLTA al render della pagina — se l'utente modificava la quantità in
UNA valigia e poi apriva la finestra per un'ALTRA valigia dello stesso
oggetto, SENZA ricaricare la pagina, quella seconda finestra mostrava
ancora il valore "qui al massimo" calcolato con i dati VECCHI (bug
reale segnalato: "non capisco cosa si intenda con massimo qui").
**Corretto propagando i dati freschi dopo OGNI salvataggio**: la
risposta di `/api/variante` include SEMPRE `variant_quantities`
(quanti di quel modello in CIASCUNA valigia, per l'intero TripItem,
non solo quella appena toccata) — dopo un salvataggio riuscito, il JS
aggiorna sia la finestra aperta sia il `data-variants` di TUTTI gli
altri stepper dello stesso oggetto (`document.querySelectorAll` per
`trip_item_id`), così riaprirli mostra sempre il numero corretto senza
bisogno di ricaricare. **Il server resta comunque la fonte di verità
definitiva**: valida sempre da capo sul database ad ogni richiesta,
quindi anche in un caso limite di dato client non aggiornato (es. un
collaboratore che modifica la stessa cosa in parallelo), non è MAI
possibile superare il posseduto — nel peggiore dei casi il numero
mostrato è temporaneamente impreciso, ma il salvataggio viene comunque
rifiutato con un errore chiaro.

**`/api/variante` NON deve stare nella coda offline**: c'era finito per
distrazione insieme agli altri endpoint di scrittura del workspace, ma
la finestra di scelta modello ha bisogno di una risposta COMPLETA e
IMMEDIATA (per calcolare il limite tra più valigie) — una risposta "in
coda" (`{ok:true, queued:true}`, senza `variant_quantities` né
`stats`) lasciava la finestra in uno stato incoerente, percepito come
"un errore di comunicazione senza un motivo chiaro" (bug reale
segnalato). Rimosso dall'elenco `ELIGIBLE_PATHS` in
`static/js/offline.js`: un fallimento di rete qui mostra ora il
normale errore "controlla la connessione", invece di un salvataggio
accodato silenziosamente. **Se in futuro un endpoint richiede una
risposta sincrona completa per funzionare correttamente (non solo un
generico +1/-1), non aggiungerlo a `ELIGIBLE_PATHS` — la coda offline
va bene solo per azioni "fire and forget" con un payload di risposta
semplice.**


**Causa reale del bug segnalato ("il peso della valigia non cambia
aggiungendo oggetti con modelli")**: `TripItemVariantQty` non aveva
MAI un `trip_luggage_id` — un modello portato in viaggio non era
legato a NESSUNA valigia specifica, quindi `trip_stats()` (che calcola
il peso SEMPRE per valigia, mai un totale generico) non poteva
includerlo per definizione, non per un errore di calcolo ma perché
mancava proprio il dato necessario. **Non bastava correggere una
formula: serviva un cambio di modello dati.**

**Nuova UX, come richiesto esplicitamente**: un oggetto con modelli
mostra ora GLI STESSI stepper Cabina/Stiva/Zaino di un oggetto
normale (classe `qty-stepper--variant-luggage`, stessa struttura
visiva) — ma i pulsanti +/- (classe `.variant-modal-trigger`) aprono
una finestra (`initVariantModal` in dashboard.js) invece di
incrementare direttamente: lì si sceglie ESPLICITAMENTE quale modello
si sta aggiungendo o togliendo da QUELLA valigia. I vecchi stepper
"uno per modello" (`.qty-stepper--variant`) sono stati rimossi
interamente.

**Dati per la finestra: pre-calcolati al render, non richiesti al
volo**. Ogni stepper porta con sé, in un attributo `data-variants`
(JSON), l'elenco completo dei modelli con tutto il necessario
(descrizione, peso, posseduto, quantità già in QUESTA valigia,
quantità nelle ALTRE valigie) — calcolato dal filtro Jinja
`get_variant_modal_data` (app/__init__.py) UNA VOLTA per stepper al
momento del render. Aprire la finestra non fa quindi ALCUNA richiesta
di rete: si popola istantaneamente da questo attributo. **Se cambi la
struttura di `ItemVariant`, aggiorna anche questo filtro.**

**Il limite "non superare il posseduto" ora vale sulla SOMMA fra
valigie**, non più per singola valigia isolata: `/api/variante`
calcola quanto di quel modello è già in TUTTE LE ALTRE valigie di
questo TripItem prima di accettare il nuovo valore — altrimenti si
potrebbero "creare" unità dal nulla distribuendole su più valigie
(2 possedute → 2 in cabina E 2 in stiva, un errore logico).

**Payload API ristrutturato**: `variant_quantities` è passato da
`{variant_id: quantità}` (un'unica quantità INVALIDA in un mondo dove
un modello può stare in più valigie) a `{variant_id: {luggage_id:
quantità}}`; aggiunto `variant_luggage_totals: {luggage_id: totale}`,
l'analogo di `quantities` (usato dagli oggetti normali) per aggiornare
lo stepper principale dopo un salvataggio nella finestra.

**Migrazione dati esistenti**: le righe già presenti (create prima di
questa versione, senza `trip_luggage_id`) vengono assegnate alla PRIMA
valigia dello stesso proprietario in quel viaggio; se non ne esiste
nessuna, la riga viene scartata (senza una valigia non aveva comunque
alcun effetto sul peso, quindi non c'è vera perdita di informazione
utile).

**Lezione da un errore commesso durante questo lavoro**: il nome
reale della tabella di `TripLuggage` è `trip_luggage` (SINGOLARE) —
un `ForeignKey("trip_luggages.id")` scritto al plurale (un errore di
battitura plausibile, dato che la relazione Python si chiama
`trip_luggages`) rompe l'intera suite di test con un
`NoReferencedTableError` a runtime, non in fase di scrittura del
codice. **Verifica sempre il `__tablename__` REALE nel modello
sorgente prima di scrivere una nuova ForeignKey, mai il nome che
"sembra giusto" per analogia con la relazione Python.**


**Sottomenu annidato: perché non un `[data-dropdown]` dentro l'altro**.
`initDropdowns()` chiude TUTTI i menu a comparsa aperti quando se ne
apre un altro (per evitarne due aperti insieme) — annidare un secondo
`[data-dropdown]` dentro il menu utente per "Impostazioni" avrebbe
significato che aprirlo chiudeva ANCHE il menu che lo contiene
(comportamento sbagliato: sparirebbe insieme al proprio contenuto).
Per questo `[data-submenu-toggle]`/`[data-submenu]` sono un meccanismo
SEPARATO e più semplice (`initDropdownSubmenus()` in app.js): si apre
ad accordion IN LINEA dentro lo stesso menu, mai un flyout laterale
(più affidabile al tocco su mobile). `Impostazioni` non è più tra le
voci riordinabili in `DEFAULT_NAV_ORDER`/`nav_order`: vive
esclusivamente nel menu utente ora, riordinarla al livello superiore
non avrebbe più senso.

**Home: tre card in una riga, senza intaccare il resto del layout a 2
colonne**. `.home-row-three` è un grid ANNIDATO dentro `.home-grid`
(come `.home-block-wide`, con `grid-column: 1/-1` per occupare tutta
la larghezza), con le proprie 3 colonne interne — così solo QUESTA
riga (Catalogo/Valigie/Lista della spesa) è a tre colonne, il resto
della Home resta a due. Ha un proprio punto di rottura intermedio
(2 colonne sotto i 1000px) prima di collassare a una sola sotto i
780px, come il resto della Home.

**"Prepara per l'uso offline" da card a pulsante**: la card dedicata
occupava molto spazio verticale per un'azione occasionale — ora è un
pulsante accanto a "Nuovo viaggio" nell'intestazione della Home, con
lo stato del precaricamento mostrato in una riga sottile subito sotto
(stesso `[data-prepare-offline-status]` di prima, solo riposizionato).

**Il disallineamento dei pulsanti dell'azione-scorrevole**:
`.action-scroll` aveva `padding-right: 20px` per dare respiro visivo
quando il contenuto scorre orizzontalmente su schermi stretti — ma
su schermi larghi (dove non serve scorrere), quel padding faceva
terminare l'ultimo pulsante 20px prima del bordo della card
sottostante, sembrando disallineato (bug reale segnalato). Rimosso:
non risolve elegantemente ENTRAMBI i casi (stretto E largo), ma
allinea correttamente il caso più comune.


**Il blocco trascinato appariva staccato dal puntatore — causa vera**:
`translateY()` sposta un elemento RISPETTO alla propria posizione
naturale (un DELTA), non a una coordinata assoluta della finestra —
`initDragReorder` calcolava però `e.clientY - offsetY` (una posizione
quasi-assoluta) e la passava a `translateY` come se fosse un delta:
più la riga si trovava in basso nella pagina, più il calcolo produceva
uno spostamento ECCESSIVO, facendo apparire il blocco sempre più
distante dal puntatore quanto più a fondo pagina si iniziava a
trascinare. **Corretto salvando `e.clientY` al MOMENTO della presa
(`grabStartY`) e usando SEMPRE `e.clientY - grabStartY` (un vero
delta) per il transform.** Se in futuro serve un trascinamento simile
altrove, usa questo stesso pattern — mai una coordinata assoluta
dentro un `translateY`.

**Menu mobile: il pulsante Catalogo/Impostazioni aveva un padding
diverso dai link semplici** — `.dropdown-toggle` (usato da
Catalogo/Impostazioni, un `<button>`, non un `<a>`) aveva un padding
per il layout desktop (pensato per una barra orizzontale) che non
veniva sovrascritto nella media query mobile, a differenza di
`.topnav a` che invece lo era — risultando in un'altezza/spaziatura
diversa una volta impilati verticalmente (bug reale segnalato). Ora
`.topnav .dropdown-toggle` ha lo stesso padding e nessun bordo su
mobile, identico ai link semplici.

**Intestazioni di tabella: mai troncare, lasciar andare a capo** —
`table.simple-table th` aveva `white-space: nowrap` + ellissi, pensato
per il CONTENUTO delle celle (dove ha senso troncare un nome lungo),
ma applicato per errore anche alle INTESTAZIONI: un'intestazione come
"VALIGIA PREDEFINITA" in una colonna stretta veniva tagliata con "..."
invece di andare semplicemente a capo su due righe (bug reale
segnalato). Rimosso da `th`, resta solo su `td`.


**Regola esplicita, richiesta dall'utente**: OGNI riordino di righe
nell'app deve avvenire per trascinamento (maniglia + Pointer Events),
mai con pulsanti su/giù. `initDragReorder()` (dashboard.js) è
l'unica implementazione, condivisa da tre contesti: lista oggetti nel
workspace di un viaggio (righe `.item-row`), tabella oggetti del
catalogo (righe `<tr>`), liste di riordino nelle impostazioni (righe
`<li>`). **Se aggiungi un nuovo riordino in futuro, usa SEMPRE questa
funzione — non scrivere pulsanti su/giù "per semplicità": è stato
esplicitamente rifiutato.**

Per farla funzionare anche su `<tr>` (non solo elementi flex come
`.item-row`), il placeholder generato durante il trascinamento si
adatta al tag della riga trascinata (`document.createElement(row.tagName)`):
per una `<tr>`, contiene una singola `<td colspan="...">` per restare
valido dentro una `<tbody>`. La tabella del catalogo ha ora una
colonna dedicata alla maniglia (icona sola, 30px) — la colonna "Nome"
è quindi la SECONDA, non la prima: il CSS che dà il trattamento
"titolo, senza etichetta" nella vista a schede (mobile) è stato
spostato da `:first-child` a `:nth-child(2)` per questa tabella
specifica.

La pagina "Ordine del menu" (impostazioni) usa lo stesso trascinamento
ma NON salva ad ogni rilascio (a differenza degli altri due contesti,
che chiamano subito un endpoint): il nuovo ordine resta nel DOM finché
non si preme "Salva ordine", che lo legge e lo invia in un'unica
richiesta — per questo carica `dashboard.js` (dove vive
`initDragReorder`) anche se il resto del file non serve su questa
pagina; le altre funzioni di inizializzazione lì dentro semplicemente
non trovano i propri elementi e non fanno nulla, senza errori.


`User.nav_order` / `User.catalog_submenu_order` (proprietà calcolate
da `nav_order_json`, un JSON libero): puramente estetico, nessun
impatto su permessi o comportamento. Le chiavi valide sono fisse
(`DEFAULT_NAV_ORDER`, `DEFAULT_CATALOG_SUBMENU_ORDER`) — un valore
salvato con chiavi mancanti o sconosciute viene silenziosamente
corretto da `_ordered()` (chiavi valide nell'ordine salvato, poi
quelle mancanti accodate secondo l'ordine di default): **se aggiungi
una nuova voce di menu in futuro, aggiungila alla lista di default
corrispondente — comparirà automaticamente in fondo per chi ha già un
ordine personalizzato salvato, senza bisogno di una migrazione dati.**

Il rendering del menu in `base.html` usa MACRO Jinja definite inline
(`nav_home`, `nav_catalogo`, ecc.), richiamate in un loop
sull'ordine salvato — **le macro definite nello stesso file HANNO
accesso al contesto del template circostante** (`current_user`,
`request`, `nav_nearest_trip`, ecc.) senza bisogno di passarle
esplicitamente come argomenti, a differenza di macro importate da un
file separato (che richiederebbero `with context`). Il link al viaggio
più vicino resta dentro la macro `nav_viaggi()` (non è una voce
riordinabile a sé: è contestuale a "Viaggi", non un elemento
indipendente).

La pagina `settings/menu_order.html` riusa lo stesso pattern a
pulsanti su/giù di `initCatalogItemReordering` (niente trascinamento,
coerenza con la scelta già fatta per il catalogo) — ma con submit
esplicito di un form invece di salvataggio istantaneo via AJAX: qui
non c'è motivo di ottimizzare la latenza percepita (è un'impostazione
occasionale, non un'azione ripetuta come impacchettare gli oggetti).


**Banner offline → pallino**: `.offline-badge` (un pallino con
numero, accanto al logo) sostituisce il vecchio banner a piena
larghezza che copriva il menu su mobile, rendendolo inutilizzabile
(bug reale segnalato). Il dettaglio testuale compare in un piccolo
popover al tocco (`.offline-badge-detail`), non più invadente.

**Viaggio più vicino nel menu**: calcolato nel context processor
`inject_nav_context` (app/__init__.py), disponibile come
`nav_nearest_trip` in OGNI template che estende base.html — non serve
ricalcolarlo per ogni pagina. Riusa la stessa logica di ordinamento
già presente in `dashboard.index()` (viaggi non passati, ordinati per
`start_date`).

**Tabella catalogo oggetti: causa vera del "non entra nella pagina" —
MAI mischiare percentuali e pixel fissi** — le larghezze mischiavano
`34%` con `110px`/`70px`/`92px`: la parte in pixel non si restringe
MAI, quindi su uno schermo stretto (mobile) la somma superava sempre
il 100% disponibile, facendo traboccare la tabella qualunque
percentuale venisse scelta per l'altra colonna. **Corretto usando SOLO
percentuali per tutte e 5 le colonne** (30/22/18/12/18%, sommando
esattamente a 100): così la tabella si restringe SEMPRE in proporzione
e non supera mai la larghezza del contenitore, su qualunque schermo. Su
schermi molto stretti il testo tronca con l'ellissi invece di
scorrere — è il compromesso VOLUTO ("fai entrare tutto... senza dover
scorrere"). **Se tocchi ancora questa tabella: MAI aggiungere una
larghezza in pixel fissi a una colonna se le altre sono in percentuale
— o tutte percentuali, o gestita diversamente (es. nascondere colonne
su mobile), mai un mix.**

`category-panel-heading`: presente SOLO nel catalogo (dove aiuta a
distinguere le tabelle quando si seleziona "Tutti"), rimosso
esplicitamente dal workspace di un viaggio su richiesta — lì non
c'è più. Il JS che lo mostra/nasconde (`initCategoryTabs()`,
condiviso tra le due pagine) resta invariato: è innocuo sul workspace
dato che l'elemento semplicemente non esiste più lì da nascondere.

**Il bordo di categoria — causa VERA, la seconda parte (v3.0.6)**: la
barra posizionata (v3.0.5) risolveva il distacco dalla curva, ma
restava squadrata agli angoli perché `.category-panel` (l'elemento a
cui è agganciata) non aveva un proprio `border-radius`/`overflow:hidden`
— l'arrotondamento visibile apparteneva a `.item-list` (un elemento
FIGLIO, un livello più interno), completamente scollegato dalla barra.
Corretto aggiungendo `border-radius: var(--radius-md); overflow:
hidden;` DIRETTAMENTE su `.category-panel`: ora la barra viene tagliata
nella stessa forma arrotondata del contenuto che le sta accanto,
perché è lo STESSO elemento a possedere sia la barra sia
l'arrotondamento. **Lezione: se un accento (bordo, barra, ombra) deve
seguire visivamente la forma arrotondata di un contenuto, il
`border-radius`/`overflow:hidden` deve stare sull'elemento che
CONTIENE fisicamente l'accento stesso — non basta che un elemento
FIGLIO qualunque sia arrotondato.**

**Il bordo di categoria — causa VERA, finalmente**: dopo quattro
tentativi (rimuovere/ripristinare il doppio bordo, togliere il
padding), il vero problema era che `border-left` su un elemento con
angoli arrotondati NON segue la curva dell'angolo quando non c'è un
`border-top` con cui "fondersi": la linea si ferma di netto appena
prima della curva, lasciando un vuoto proprio lì, A PRESCINDERE dal
padding. **Soluzione definitiva**: niente più `border-left` per questo
accento — `.category-panel::before` è una barra POSIZIONATA
(`position:absolute; left:0; top:0; bottom:0; width:3px`), non un
bordo: resta sempre incollata al bordo vero della card, e viene
tagliata automaticamente della forma giusta dall'`overflow:hidden`
della card (nessuna gestione manuale della curva necessaria). **Se in
futuro serve un accento colorato simile su un elemento con angoli
arrotondati, usa SEMPRE questa tecnica (barra posizionata), mai
`border-left` diretto.**

**`table-layout: fixed` NON va applicato a `table.simple-table` in
generale**: era stato messo sulla classe base, quindi si applicava a
OGNI tabella dell'app (Utenti, Valigie, Condivisione, Backup, Modelli
di un oggetto, non solo il Catalogo) — forzandole tutte dentro
proporzioni di colonna pensate SOLO per la tabella oggetti del
catalogo, rendendole più strette del loro stesso contenuto (bug reale
segnalato, "tabelle più piccole di ciò che contengono"). Corretto:
`table-layout:fixed` e le larghezze di colonna specifiche vivono ora
SOLO nella classe `catalog-items-table` (aggiunta ESPLICITAMENTE al
tag `<table>` in `catalog/items.html`), non nella classe base
`simple-table`. **Ogni tabella che non ha bisogno di colonne fisse
resta a `table-layout: auto` (il default): non aggiungere mai regole
di larghezza alla classe `simple-table` di base — se una tabella
specifica ha bisogno di colonne fisse, dalle una classe propria,
come `catalog-items-table`.** `catalog/categories.html` gestisce le
proprie larghezze in modo indipendente, con uno stile in linea sul
proprio `<table>` — non condivide né eredita nulla dalla classe
`catalog-items-table`.

**Switch icone/testo: perché non funzionava la scelta esplicita** — la
causa esatta non è mai stata isolata con certezza (le regole CSS
sembravano corrette anche prima), ma la soluzione più ROBUSTA
(indipendente da qualunque problema di specificità/ordine/cache) è
aggiungere `!important` alle regole `[data-column-style="icons"]`/
`[data-column-style="text"]`: una scelta ESPLICITA dell'utente deve
SEMPRE vincere sulla modalità automatica, senza ambiguità possibile.

**Icone del catalogo: SEMPRE testo libero, mai un elenco curato**:
`CatalogPrefsForm` (le icone per regola quantità/tipologia valigia) e
`CategoryForm.icon` (icona di una categoria) sono entrambi `StringField`
liberi — l'utente scrive il nome di QUALUNQUE icona lucide.dev voglia,
senza restrizioni a un sottoinsieme scelto da chi sviluppa. **Non
reintrodurre mai un `SelectField`/menu a tendina con scelte curate per
un campo icona: è stato esplicitamente rifiutato ("non voglio alcun
suggerimento").**

**Tabelle del catalogo: la sovrapposizione col bordo arrotondato della
card**: quando una card ha `padding:0` (per far toccare la tabella ai
bordi) E `border-radius`, l'ULTIMA colonna di una tabella può
visivamente sovrapporsi all'angolo arrotondato (bug reale segnalato
più volte: il pulsante Archivia sembrava "tagliato" dal bordo). Fix
minimale e sufficiente: un piccolo `padding-right` (8px) sulla card,
lasciando `padding-left: 0` (per non staccare il bordo di categoria
dal contenuto, vedi sopra). **Se aggiungi una nuova tabella dentro una
card con padding:0, applica lo stesso `padding:0 8px 0 0` per evitare
che ricapiti.**

**Lo stepper dei modelli non leggeva il proprio limite**: `initRobustStepper`
accetta `max` come PARAMETRO JS (non lo legge dall'attributo HTML
`max` dell'input), quindi impostare `max="{{ v.owned_qty }}"` nel
template da solo non bastava — serviva anche passare
`max: maxOwned` esplicitamente a `initVariantSteppers` (letto da
`input.max` all'inizializzazione). **Se aggiungi un nuovo stepper con
un limite che varia da riga a riga (non un valore fisso uguale per
tutti), ricordati di leggerlo dal DOM e passarlo esplicitamente**,
altrimenti il vincolo esiste solo visivamente (frecce native del
browser) ma non nei pulsanti +/- gestiti da JS.

**Preferenze icone del catalogo**: `User.catalog_column_style`
("auto"/"icons"/"text") + `User.catalog_icon_prefs_json` (JSON libero,
letto tramite `quantity_rule_icon()`/`luggage_type_icon()`, mai
direttamente). Il rendering usa SEMPRE entrambe le rappresentazioni
(icona E testo) nell'HTML, nascondendo l'una o l'altra via CSS
(`data-column-style` + classi `.col-icon`/`.col-text`) — **mai
condizionare cosa VIENE GENERATO lato server in base al dispositivo**:
il server non sa se il client è mobile o desktop, la scelta
"automatico" è interamente demandata a una media query CSS.

**Pulsante offline manuale, non più automatico**: `warmTripCache()`
(che precaricava da sola ad ogni apertura di Home/Viaggi) è stata
rimossa su richiesta esplicita ("spreco di risorse inutile") e
sostituita da `prepareOfflineCache()`, azionata SOLO dal pulsante
"Prepara per l'uso offline" in Home. Usa il nuovo endpoint
`GET /api/pagine-offline` (elenca Home + pagine principali + tutti i
viaggi accessibili all'utente) e scarica ogni URL in sequenza,
aggiornando un contatore visibile. **Se in futuro serve precaricare
qualcos'altro, aggiungilo alla lista in quell'endpoint — non
reintrodurre un precaricamento automatico e silenzioso** senza
un'esplicita richiesta in tal senso.

## 4.14. Modelli di un oggetto (ItemVariant)

Facoltativi: un oggetto senza modelli si comporta esattamente come
sempre. Se un oggetto ne ha almeno uno (`Item.has_variants`), la
preparazione per un viaggio SOSTITUISCE gli steppers per valigia con
uno stepper per CIASCUN modello (vedi il blocco
`{% if ti.item.has_variants %}` in `trips/workspace.html`) — target,
indossato e mancante restano invariati e si applicano comunque
all'insieme di tutti i modelli.

**Scelta di scope deliberata, non un'omissione**: un modello non si
assegna a una valigia specifica (solo "quante unità di questo modello
porto", non "in quale valigia"). Conseguenza accettata: il peso dei
modelli NON compare nel dettaglio per singola valigia della carta
d'imbarco (`trip_stats`'s `content_weight_grams`, basato su
`TripItemQty`, che gli oggetti con modelli non popolano) — solo nel
pannello di dettaglio dell'oggetto (`_item_detail_panel.html`), che
somma `weight_grams * qty_for_variant(v.id)` per ciascun modello. Se
in futuro serve il peso per valigia ANCHE per gli oggetti con modelli,
serve introdurre `trip_luggage_id` anche su `TripItemVariantQty`
(oggi assente apposta, per contenere la complessità) e aggiornare di
conseguenza sia il workspace sia `trip_stats`.

`TripItem.total_ready_qty` include `variants_total_qty` insieme a
`total_qty` (valigie) e `indossato_qty`: **qualunque nuovo "contenitore"
di quantità in futuro (un quarto modo di considerare un oggetto
"pronto") va sommato qui**, non gestito come caso a parte altrove,
altrimenti lo stato (verde/giallo/rosso/grigio) smette di essere
affidabile.

## 6. Come si avvia

**Nota tecnica importante (avvio con più worker)**: `create_app()`
esegue `db.create_all()` + migrazioni + seed dati sotto un lock di file
(`data/.init.lock`, vedi `app/__init__.py::_init_database_with_lock`).
È necessario perché gunicorn (`entrypoint.sh` usa `--workers 2`) avvia
più processi separati che importano ed eseguono `create_app()` in
parallelo: senza il lock, al primissimo avvio su un database vuoto due
worker possono provare a creare le stesse tabelle nello stesso istante e
uno dei due va in crash ("table already exists" — bug reale, riprodotto
lanciando l'app con gunicorn multi-worker; i test automatici a processo
singolo non lo avrebbero mai scoperto). **Se in futuro tocchi questa
parte di `create_app()`, testala sempre con `gunicorn --workers 2`
reale, non solo con `pytest`.**

```bash
cp .env.example .env    # imposta almeno SECRET_KEY
docker compose up -d --build   # risponde SOLO su 127.0.0.1:4825 dell'host
```
**Non serve più eliminare `data/valigia.db` per aggiornare**: le
migrazioni in `app/migrations.py` si occupano da sole di portare lo
schema al passo più recente, qualunque versione precedente tu stia
usando. Vedi sezione 8 per come aggiungerne di nuove in futuro.

**Backup**: dalla sezione "Backup" (menu, solo admin) puoi scaricare
l'intero database in un click, o ripristinarne uno (con copia di
sicurezza automatica di quello attuale prima del ripristino). Per backup
automatici periodici lato server, un semplice cron sull'host che fa
`cp data/valigia.db backups/valigia-$(date +%F).db` è sufficiente (il
file è autosufficiente: contiene tutto).

**Test** (il più utile dopo QUALSIASI modifica):
```bash
VALIGIA_ENV=testing pytest -q
```
`test_migration.py` è particolarmente importante da rilanciare se tocchi
`models.py` o `migrations.py`: verifica che un vecchio database non perda
dati. `test_walkthrough.py` verifica l'isolamento reale tra utenti via
HTTP (non solo a livello di funzioni).

**Per i test che hanno bisogno di un database su file** (non
`:memory:`, es. `test_backup.py`, `test_migration.py`): imposta la
variabile d'ambiente `VALIGIA_DATABASE_URI_OVERRIDE` (letta da
`create_app()` DOPO aver caricato la configurazione normale, quindi
funziona con qualunque `config_name`, incluso `"testing"` che ha il CSRF
già disattivato — molto più robusto di un `importlib.reload()` su
`app.config`, che NON si propaga ai moduli che hanno già importato
`config_by_name` in precedenza (bug reale trovato e risolto in questa
versione, vedi commit history/test).

## 6.5. Convenzioni per i campi numerici decimali (peso, capacità, ecc.)

**Bug reale della v2.1.1** (in due parti): (1) i campi decimali (peso,
capacità) accettavano solo il punto, ma l'app MOSTRA sempre questi
numeri con la virgola (stile italiano) — chi scriveva "2,5" falliva la
validazione SENZA vedere alcun errore (i template non rendevano gli
errori di ogni campo), dando l'impressione che l'intero form "non si
salvasse"; (2) un primo tentativo di correzione (accettare "sia punto
sia virgola come decimale") era SBAGLIATO: l'utente usa la vera
convenzione internazionale, dove il punto è il separatore delle
MIGLIAIA, non un secondo modo di scrivere il decimale. "1.500" deve
valere 1500, non 1,5.

**Regola definitiva, implementata in `app/utils.py`**:
- `parse_number_it(raw)`: converte una stringa in float. Il PUNTO (se
  presente) è SEMPRE rimosso (separatore delle migliaia); la VIRGOLA (se
  presente) diventa SEMPRE il punto decimale per `float()`. Nessuna
  euristica, nessuna ambiguità: è una regola fissa, non un tentativo di
  indovinare l'intenzione dell'utente.
- `format_number_it(value, decimals)`: l'inverso, per la visualizzazione
  (usato anche dal filtro Jinja `numero_it`).
- `app.forms.DecimalCommaFloatField` usa `parse_number_it` in
  `process_formdata` E `format_number_it` in `_value()` (il valore
  ripresentato nel campo quando riapri un modulo di modifica): è
  FONDAMENTALE che entrambe le direzioni usino la stessa convenzione,
  altrimenti riaprire un valore già salvato (es. 1500.0, ripresentato
  come "1.500") e risalvarlo SENZA toccarlo lo corromperebbe (interpretando
  di nuovo quel punto come decimale invece che come migliaia). Vedi
  `tests/test_smoke.py::test_decimal_comma_float_field_round_trips_existing_values`.

**Regola per qualunque nuovo campo decimale futuro**:
1. Usa sempre `DecimalCommaFloatField`, mai il semplice `FloatField` di
   WTForms, per qualunque numero che l'utente possa scrivere.
2. Nel template, renderizza SEMPRE il blocco errori per OGNI campo del
   form (`{% for e in form.<campo>.errors %}...{% endfor %}`), non solo
   per i campi che "sembrano" più a rischio: un fallimento di validazione
   silenzioso è un bug subdolo e frustrante da segnalare per chi lo vive.
3. Se aggiungi un modo alternativo di formattare/mostrare questi numeri
   altrove (es. un'API JSON per un futuro uso esterno), NON reinventare
   la formattazione: importa `format_number_it`/`parse_number_it` da
   `app/utils.py`.

## 6.6. Concorrenza SQLite (WAL) — non rimuovere senza un buon motivo

**Bug reale della v2.1.1**: con più worker gunicorn (`--workers 2` in
`entrypoint.sh`), un errore generico ("Qualcosa è andato storto")
poteva comparire aprendo pagine che leggono dal database (es. Home,
Viaggi) se un'ALTRA richiesta stava scrivendo nello stesso istante.
SQLite, in modalità "rollback journal" (il default), blocca i lettori
durante una scrittura.

**Soluzione**: `app/__init__.py::_configure_sqlite_for_concurrency`
attiva `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000` su ogni
connessione, tramite un event listener SQLAlchemy registrato subito dopo
`db.init_app(app)`. La modalità WAL permette letture concorrenti durante
una scrittura. **Effetto collaterale a cui fare attenzione**: con WAL
attivo, le scritture più recenti possono restare temporaneamente in un
file `<db>-wal` (e `<db>-shm`) accanto al file principale, non ancora
"fuse" in esso:
- L'esportazione di un backup (`backup/routes.py::export_backup`) fa
  SEMPRE un `PRAGMA wal_checkpoint(FULL)` prima di inviare il file, per
  essere sicura che sia completo e autosufficiente.
- Il ripristino di un backup fa lo stesso checkpoint (+ chiusura di
  tutte le connessioni) PRIMA di copiare il database attuale come
  sicurezza, e cancella esplicitamente eventuali `-wal`/`-shm` residui
  del database precedente DOPO aver scritto quello nuovo — altrimenti
  SQLite potrebbe provare a "riapplicarli" al file sbagliato.
- Qualunque test che costruisce un file `.db` manualmente (non tramite
  le route dell'app) e poi lo legge/carica direttamente da un altro
  punto DEVE fare lo stesso checkpoint esplicito prima, altrimenti può
  leggere un file incompleto (vedi `tests/test_backup.py`).

Verificato con un test di carico reale (120 richieste lettura+scrittura
in parallelo su 3 worker, zero errori) prima di considerare la
correzione valida.

## 7. Cosa NON è (ancora) implementato

- Condivisione "tutto o niente" (nessun ruolo di sola lettura).
- Nessun upload manuale di immagine di copertina.
- Il ripristino di un backup con più worker gunicorn attivi richiede un
  riavvio del container per sicurezza (spiegato in UI dopo il ripristino).
- Riordino drag&drop di categorie/oggetti non esposto in UI (il campo
  `sort_order` esiste già nei modelli).

## 8. Come funzionano le migrazioni (e come aggiungerne una nuova)

`app/migrations.py` non usa Alembic: una tabella `schema_meta` (una riga
sola) ricorda l'ultima migrazione applicata; `_MIGRATIONS` è una lista
ordinata di funzioni, ciascuna applicata UNA SOLA VOLTA con SQL diretto
(mai i modelli ORM, che riflettono già lo schema NUOVO). Regola
fondamentale: le migrazioni usano SEMPRE `ALTER TABLE ... ADD COLUMN`,
MAI `DROP`/`RENAME` — le colonne/tabelle superate restano semplicemente
inutilizzate. Questo rende ogni migrazione a basso rischio: nel peggiore
dei casi lasci dati vecchi non più letti da nessuno, ma non ne perdi mai.

**ATTENZIONE — lezione da un bug critico reale (v2.3.0):** "mai perdere
dati" NON significa "mai controllare i vincoli delle colonne vecchie".
Quando una colonna vecchia (es. `trip_item_qty.trip_bag_id`, sostituita
da `trip_luggage_id` alla v2.1) ha un vincolo `NOT NULL` E smette di
essere scritta dal codice nuovo, quel vincolo blocca OGNI futuro
inserimento nella tabella — non solo per le righe vecchie, per TUTTE,
comprese quelle nuove che il codice attuale prova a creare. `_add_column`
aggiunge la colonna nuova ma NON tocca il vincolo di quella vecchia:
se stai sostituendo una colonna (non solo aggiungendone una), verifica
SEMPRE se la vecchia ha `NOT NULL` senza default (`PRAGMA
table_info(tabella)`, colonna `notnull`). Se sì, quella tabella va
RICOSTRUITA (rinominare, creare la versione nuova, `INSERT ... SELECT`,
`DROP` della vecchia — vedi `_migrate_to_v4` come esempio), non
semplicemente "lasciata lì". Questo bug è rimasto silente per diverse
versioni: il codice funzionava finché non serviva inserire una riga
DAVVERO nuova (aprire un viaggio nuovo, aggiungere un oggetto nuovo).
**Quando sostituisci una colonna in futuro, aggiungi sempre un test che
verifichi ESPLICITAMENTE un inserimento nuovo dopo la migrazione**, non
solo che i dati vecchi sopravvivano (vedi `test_migration.py`, la
sezione "LA VERIFICA DECISIVA" in
`test_migration_preserves_data_and_upgrades_schema`).

**Per aggiungere una migrazione futura:**
1. Scrivi una funzione `_migrate_to_vN(conn)` in `app/migrations.py` che
   usa `_add_column`/`_table_exists`/SQL diretto per portare lo schema
   avanti E per spostare/adattare i dati esistenti (guarda
   `_migrate_to_v1` come esempio completo: crea tabelle nuove,
   ricostruisce mappe id-vecchio→id-nuovo, fa backfill con `UPDATE ...
   SELECT`; guarda `_migrate_to_v4` per l'esempio di ricostruzione
   tabella quando serve rimuovere un vincolo).
2. Aggiungila in fondo a `_MIGRATIONS`.
3. Scrivi un test in `test_migration.py` che crea un DB con lo schema
   VECCHIO (vedi `OLD_SCHEMA_SQL`/`OLD_SCHEMA_DATA` come modello),
   lancia `create_app()`, e verifica che i dati siano stati preservati
   E trasformati correttamente — E che un INSERIMENTO NUOVO funzioni
   dopo la migrazione. Non saltare questo passaggio: è l'unico
   modo per essere sicuri di non aver rotto i dati di chi aggiorna.
4. Aggiorna `APP_VERSION` in `app/config.py` e la sezione "Versione
   corrente" in cima a questo file.

## 9. Come continuare il lavoro in una nuova chat

1. Carica questo file e l'ultimo `CHANGELOG.md`.
2. Prima di toccare `models.py`, chiediti: questo campo/questa relazione
   deve essere personale (per utente) o condivisa (per viaggio)? La
   sezione 4 spiega il criterio già usato.
3. Dopo QUALSIASI modifica: `VALIGIA_ENV=testing pytest -q`. Se tocchi
   `models.py`, aggiungi/aggiorna anche `test_migration.py`.
4. Prima di una nuova versione: segui `changelog/README.md`, aggiorna
   `APP_VERSION` in `app/config.py` e la versione in cima a questo file.
