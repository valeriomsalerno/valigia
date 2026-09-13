# CONTEXT.md — Stato del progetto "Valigia"

> **Questo file serve a ripristinare il contesto in una nuova chat.** Se stai
> leggendo questo file come Claude (o altro assistente) all'inizio di una
> nuova conversazione: leggilo TUTTO prima di scrivere codice. Contiene le
> decisioni già prese e il perché, non solo l'elenco delle funzionalità.

**Versione corrente: v3.11.1** (rilasciata 13 settembre 2026). Changelog
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

## 4.46. Icone Lab: bug reale nella chiave (kebab vs PascalCase); Safari e "Nome oggetto" (v3.11.1)

**Le icone Lab non apparivano affatto** (bug reale segnalato con due
esempi concreti: `luggage-cabin`, `shorts-boxer`). Causa: il file
statico `lucide-lab.js` (v3.11.0) chiavava le icone in kebab-case
(`"luggage-cabin": [...]`), ma `lucide.createIcons()` **converte
sempre** il valore di `data-lucide` in PascalCase internamente
(funzione interna `toPascalCase`, verificata leggendo il sorgente del
VERO bundle UMD scaricato dal registro npm) prima di cercarlo
nell'oggetto `icons` passato — quindi la ricerca su chiavi kebab-case
falliva SEMPRE, silenziosamente (nessun errore in console lato utente,
solo un warning nella console del browser). Il bundle
`lucide-lab.js` è stato rigenerato con chiavi PascalCase
(`"LuggageCabin"`, `"ShortsBoxer"`, ecc.) — l'attributo HTML
`data-lucide="luggage-cabin"` (quello che l'utente digita, copiandolo
da lucide.dev) resta invariato in kebab-case: è SOLO la mappa interna
delle 357 icone che doveva essere ri-chiavata.

**Lezione per la prossima volta**: quando si verifica codice che
interagisce con una libreria di terze parti, testarlo contro
un **mock semplificato** (fatto in v3.11.0) NON basta — bisogna
scaricare e testare contro il **bundle vero**, perché è lì che vivono
i dettagli implementativi non documentati (in questo caso: la
conversione automatica di case). Aggiunto un test pytest che apre
direttamente il JSON delle icone e verifica che OGNI chiave sia
PascalCase (comincia maiuscola, mai un trattino) — se in futuro
qualcuno rigenera questo file seguendo la vecchia ricetta in kebab-case
(quella scritta in v3.11.0, oggi corretta), il test lo segnala subito.

**Safari continuava a suggerire "Compilazione automatica" su "Nome
oggetto"** anche dopo il fix di v3.9.2 (che aveva cambiato solo l'`id`
del campo, lasciando `name="name"` invariato — quest'ultimo è
probabilmente il segnale più forte per l'euristica "questo è il nome
di una persona", più forte dell'id). Scoperto che WTForms permette di
disaccoppiare l'attributo Python dall'attributo HTML: `StringField(...,
name="item_title")` — l'attributo HTML reso diventa `item_title`
(`name`/`id` nel DOM), mentre il codice Python (`form.name.data`,
`{{ form.name.label }}`, ecc.) resta ESATTAMENTE invariato, perché
quello continua a fare riferimento all'attributo di classe `ItemForm.name`,
non al valore HTML. Vedi `app/forms.py::ItemForm.name`. Aggiunti anche
`autocorrect="off"`, `autocapitalize="off"`, `spellcheck="false"` come
ulteriore rinforzo contro le funzioni di suggerimento della tastiera.

**Impatto collaterale da ricordare**: qualunque test o integrazione
esterna che invia il modulo di un oggetto deve usare la chiave
`item_title` nel payload POST, non più `name` (il nome del CAMPO
DEL MODELLO `Item.name` resta "name" — cambia solo il nome del CAMPO
HTML del modulo). Se in futuro serve la stessa correzione su un altro
campo "nome" (categoria, modello, valigia — non ancora segnalati),
applica la stessa ricetta: `name="qualcosa_di_diverso"` sul campo
WTForms, aggiornando di conseguenza qualunque test che invia quel
modulo via POST.

## 4.45. Icone Lucide "Lab" ed emoji, storico compatto, icona stepper indossato (v3.11.0)

**Icone Lucide "Lab" (lucide.dev/icons/lab).** Il set principale di
Lucide (caricato via CDN, `unpkg.com/lucide@latest`) NON include le
icone "Lab" (es. `shorts-boxer`) — sono un pacchetto npm separato,
`@lucide/lab`, pubblicato SOLO in formato ESM (nessun bundle
UMD/globale pronto per un semplice `<script src="...">`, verificato
prima di scegliere questa strada). Anziché caricare moduli ES a runtime
(fragile: introdurrebbe una dipendenza asincrona e un possibile
problema di ordine rispetto alle tante chiamate a
`lucide.createIcons()` già sparse nell'app), le **357 icone Lab sono
state estratte UNA VOLTA SOLA dal pacchetto npm reale** (scaricato dal
registro ufficiale) e impacchettate in un file statico self-hosted,
`app/static/js/lucide-lab.js` — coerente con l'impostazione
offline-first dell'app (PWA, service worker): nessuna dipendenza
runtime da un servizio esterno diverso da quello già in uso.

Per rigenerarlo (es. dopo un aggiornamento di `@lucide/lab` a monte):
```
npm pack @lucide/lab && tar xzf lucide-lab-*.tgz
```
poi, dentro `package/`, leggere `dist/cjs/lucide-lab.js` (già in
formato icon-node compatibile con `lucide.createIcons`) e i nomi file
in `icons/*.svg` per la mappa kebab-case → export camelCase (la
conversione kebab→camelCase è affidabile al 100%; quella camelCase→kebab
NO — 10 icone su 357 hanno un numero finale che l'algoritmo inverso
sbaglia, es. "crosshair2" invece di "crosshair-2" — usare SEMPRE i nomi
file `.svg` come fonte della verità per il nome pubblico dell'icona).

In `base.html`, la funzione `lucide.createIcons` viene "monkey-patchata"
UNA SOLA VOLTA, subito dopo aver caricato sia il pacchetto principale
sia `lucide-lab.js`: ogni chiamata successiva (anche quelle già
esistenti nei tanti punti dell'app — `app.js`, `dashboard.js`, ecc. —
tutte senza argomenti) include automaticamente anche le icone Lab,
senza dover toccare nessuno di quei punti.

**Emoji nel campo Icona.** Un'emoji digitata da tastiera (es. "👕") non
è un nome icona: dentro `data-lucide="👕"`, `lucide.createIcons()` la
cercherebbe invano nel set di icone e non produrrebbe nulla (bug
potenziale, corretto preventivamente). Nuovo test Jinja
`is lucide_icon_name` (`app/__init__.py`) — riconosce la FORMA di un
nome icona (`^[a-z0-9]+(-[a-z0-9]+)*$`, sempre minuscolo) per decidere
se renderizzare `<i data-lucide="...">` oppure un
`<span class="emoji-icon">` col testo/emoji letterale. Centralizzato
in una macro condivisa, `app/templates/_macros.html::item_icon_or_emoji`,
importata in tutti e tre i punti dove compare la miniatura di un
oggetto (item_detail.html, items.html, workspace.html) — se in futuro
serve un quarto punto, importa la stessa macro, non duplicare la
logica.

**Storico nei viaggi più compatto.** Date in formato `gg/mm/aaaa`
(`.strftime('%d/%m/%Y')`), quella di fine su una riga separata (`<br>`,
niente trattino) invece di "19 set 2026 — 30 set 2026" su una riga
sola — richiesta esplicita per risparmiare spazio orizzontale. Colonna
"Quantità" allineata a sinistra come le altre (era l'unica a destra).
Cambiamento scoped SOLO a questa tabella (`item_detail.html`): il
filtro `data_it` usato altrove nell'app (es. le card dei viaggi) resta
invariato.

**Icona dello stepper "indossato".** Cambiata da `shirt` a `user`
(`lucide.dev/icons/user`) in `workspace.html` — richiesta esplicita
con screenshot, un solo punto da correggere.

## 4.44. Foto non ritagliate, icona Lucide per oggetti senza foto (v3.10.0)

**Foto non più ritagliate.** `.item-photo-preview img` e
`.item-photo-thumb img` usavano `object-fit: cover` (riempie il
riquadro, RITAGLIANDO le parti che eccedono) — cambiato in
`object-fit: contain` (l'immagine intera resta sempre visibile, a
costo di un margine vuoto quando le proporzioni non coincidono col
riquadro quadrato). Puro CSS: si applica retroattivamente anche alle
foto già caricate, senza bisogno di rielaborarle o ricaricarle.

**Icona Lucide per un oggetto senza foto.** Nuova colonna `Item.icon`
(stringa libera, `_migrate_to_v20` in `migrations.py`) — **come
`Category.icon`, MAI un menu a tendina curato** (regola consolidata,
vedi le note di progetto): un semplice campo di testo libero nel
modulo di un oggetto ("Icona (se non hai una foto)"), con link a
lucide.dev/icons, validato lato client solo per lunghezza (nessuna
validazione sul NOME dell'icona: un nome sbagliato semplicemente non
mostra nulla, Lucide ignora silenziosamente le icone che non esistono
— comportamento accettabile, coerente con come già si comporta il
campo icona delle categorie).

**Foto e icona sono ALTERNATIVE, mai sovrapposte**: la foto, se
presente, ha SEMPRE la precedenza (`{% if item.has_photo %}...{% elif
item.icon %}...{% endif %}`, stesso ordine ovunque compare una
miniatura di un oggetto — pagina dell'oggetto, lista del catalogo,
riga nel workspace di un viaggio). Un oggetto senza NÉ foto NÉ icona
mostra la vecchia icona generica "immagine" invariata (fallback,
nessuna regressione per gli oggetti esistenti: la colonna nuova è
`nullable`, tutti gli oggetti già in database partono con `icon =
NULL`).

**Non toccato**: le VARIANTI (modelli) di un oggetto non hanno un
proprio campo icona — la richiesta parlava esplicitamente di "ogni
oggetto", non di ogni modello; il loro placeholder senza foto resta la
generica icona "immagine". Se in futuro serve anche lì, replicare
esattamente la stessa ricetta (colonna nullable su `ItemVariant`,
stesso ordine `has_photo` → `icon` → generico).

## 4.43. Tre rifiniture sulla pagina di un oggetto (v3.9.2)

**Spaziatura nell'intestazione "Modelli"**: `.flex-between` (nessun
`gap` di suo) affiancava il titolo "Modelli" e la frase informativa
("Facoltativo — utile per oggetti con varianti diverse...") senza
respiro, specialmente quando la frase va a capo su due righe restando
comunque a ridosso del titolo. Aggiunto `gap:12px; flex-wrap:wrap;`
inline su quello specifico `.flex-between` (non alla classe base, che
è condivisa altrove e non deve necessariamente comportarsi allo stesso
modo ovunque).

**Pulsanti di salvataggio duplicati anche in alto.** Un modulo lungo
(più lungo ancora dopo la fusione con la pagina dettaglio, v3.8.0)
costringeva a scorrere fino in fondo solo per premere "Salva oggetto".
Il `<form>` principale ha ora `id="item-edit-form"`; i pulsanti
duplicati in alto (`<button form="item-edit-form">`, attributo HTML
standard che collega un pulsante a un form altrove nel documento,
indipendentemente dalla posizione nel DOM) restano perfettamente
funzionanti pur stando fuori dal markup del form stesso. "Annulla" in
alto è un semplice `<a href="{{ return_to }}">` duplicato, non ha
bisogno dell'attributo `form`.

**Il browser non deve suggerire "Nome oggetto" come un campo
anagrafico/password.** Bug segnalato con screenshot: un'estensione o
funzione del browser proponeva "Compilazione automatica" su quel
campo. Corretto con la combinazione standard: `autocomplete="off"` sul
`<form>` E su OGNI campo (non basta uno dei due secondo le
implementazioni pratiche dei vari browser), PIÙ — solo per "Nome
oggetto", il campo più a rischio — un `id` non generico
(`id="item-name"` invece del default `id="name"` che WTForms genera
dal nome del campo Python: `id="name"` è probabilmente il singolo
segnale più forte per l'euristica "questo è il nome di una persona").
Sovrascrivere l'`id` richiede di sovrascrivere ANCHE il `for` della
label associata, altrimenti si rompe il click-per-mettere-a-fuoco
(`{{ form.name.label(**{'for': 'item-name'}) }}` — `for` è parola
riservata in Python, va passato come chiave di un dict spacchettato,
non come kwarg diretto). **Se in futuro emerge lo stesso problema su
un altro campo "nome" altrove nell'app** (categoria, modello,
valigia...) non ancora segnalato, la stessa ricetta si applica
identica.

## 4.42. "Torna al catalogo" da link-cronologia a link fisso ancorato (v3.9.1)

**Bug grave segnalato**: "Torna al catalogo" (e di conseguenza anche
"Salva oggetto" e "Annulla", che condividono lo stesso `return_to` —
vedi `catalog/routes.py::_resolve_navigation_context`) "funziona come
il pulsante Indietro del browser": dipendeva dal Referer HTTP (o dal
campo nascosto "ritorno" introdotto in v3.8.0 per farlo sopravvivere a
Precedente/Successivo/Salva e vai al successivo), quindi seguiva
l'ultima azione dell'utente invece di puntare sempre allo stesso posto
prevedibile — esattamente il comportamento indesiderato di un
pulsante "indietro" nella cronologia, non di un link.

**La correzione, radicale**: `_resolve_navigation_context` non guarda
più NÉ il Referer NÉ un campo "ritorno" per il caso catalogo (il ramo
`da_viaggio`/viaggio resta invece invariato: quello era già un
parametro esplicito e deliberato, non un'euristica, e non era la parte
segnalata come rotta). Quando NON si viene da un viaggio, `return_to`
è ora SEMPRE `url_for("catalog.items", archiviati=...) +
f"#item-{item.id}"` — un link fisso e prevedibile, ancorato ESATTAMENTE
alla riga dell'oggetto di provenienza. Il campo nascosto "ritorno" (e
tutto il codice che lo leggeva/scriveva) è stato rimosso: non serve
più, dato che ogni pagina di un oggetto ricalcola da sé il proprio
link di ritorno corretto, sempre ancorato all'oggetto CORRENTE (anche
dopo Precedente/Successivo — anzi, è un miglioramento: prima "Torna al
catalogo" da un oggetto raggiunto per Successivo restava ancorato al
punto di partenza ORIGINALE, ora si aggiorna correttamente sul nuovo
oggetto corrente).

**Lo scroll fino al punto giusto lo fa il browser stesso, nativamente,
tramite l'ancora HTML (`id="item-<id>"` su ogni riga, in
`items.html`)** — NESSUN meccanismo lato client (sessionStorage,
`initGenericScrollRestore`) è coinvolto in questo caso specifico: un
link con `#frammento` è intrinsecamente più affidabile di un Referer
(che può mancare, essere bloccato da estensioni/policy sulla privacy,
o riflettere l'ultima azione invece della pagina di provenienza
originale). `initGenericScrollRestore` (v3.8.0) RESTA comunque utile e
INVARIATA per altri casi (es. "Categorie", che si ricarica sulla
stessa identica URL dopo aver salvato una modifica) — le due tecniche
convivono, ciascuna per il caso a cui è più adatta.

**Due dettagli di rifinitura**, entrambi in `style.css`, scoped a
`table.catalog-items-table tr[id^="item-"]` (mai alla base
`simple-table`, per non toccare altre tabelle): `scroll-margin-top:
76px` (altrimenti la riga finirebbe scorsa esattamente sotto la
topbar fissa, `min-height:60px`, a filo o parzialmente coperta) e
un'animazione `:target` (`item-row-highlight`, sfumatura color
`--brass-100` che svanisce in 2.4s) che evidenzia la riga appena
raggiunta — puramente CSS, nessun JS, rispetta già la regola globale
`prefers-reduced-motion` esistente in cima al file.

**Se in futuro aggiungi un'altra pagina che deve "tornare al
catalogo"**: usa `_resolve_navigation_context(item)` esattamente come
qui, non reintrodurre un uso di `request.referrer` per questo scopo —
è esattamente la scelta che ha causato questo bug.

## 4.41. Ordine categorie, "Indossa", Ricalcola completo, verifica isolamento eliminazione (v3.9.0)

**Ordine delle categorie, sia nel catalogo sia nel viaggio.**
`Category.sort_order` esisteva già ed era già rispettato da entrambe
le schermate (`catalog.items` e `trips.workspace` ordinano già
`.order_by(Category.sort_order, ...)`) — mancava però qualunque
interfaccia per RIORDINARLE a mano (unico caso, tra le entità
principali dell'app, senza drag-and-drop). Aggiunto in
`categories.html`: colonna maniglia (`.drag-handle-cell`, nuova regola
CSS generica per QUALUNQUE tabella con maniglia, non solo
`catalog-items-table` — quella resta con le sue rifiniture di
spaziatura specifiche, più specifica e quindi prioritaria), `<tbody
data-reorderable-categories>`, nuovo endpoint
`POST /api/riordina-categorie` (mirror esatto di
`/api/riordina-oggetti`, ma su un unico elenco piatto — le categorie
non hanno sotto-gruppi), nuova `initCategoryReordering()` in
`dashboard.js`. **Non richiede alcuna modifica a `catalog.items` o
`trips.workspace`**: ordinano già per quel campo, il nuovo ordine si
riflette da solo.

**"Indossa" come posizione predefinita di un oggetto.** Aggiunto
`LuggageType.INDOSSA` — ma SOLO alle scelte di
`Item.default_luggage_type` (`LuggageType.POSITION_CHOICES = CHOICES +
[(INDOSSA, "Indossa")]`), MAI a `LuggageType.CHOICES` usato dal form di
una valigia REALE (`LuggageForm.tipologia`): non esiste una valigia
fisica "Indossa" da poter possedere. L'etichetta del campo nel modulo
di un oggetto (`ItemForm.default_luggage_type`) è stata rinominata da
"Tipologia di valigia predefinita" a "**Posizione predefinita**" (e
così pure la colonna nella tabella del catalogo, `items.html`) — per
restare grammaticalmente compatibile con "Indossa" ("Posizione
predefinita: Indossa", non "Tipologia di valigia predefinita:
Indossa"). **Nessuna nuova logica di stato necessaria**: l'app conta
già `TripItem.indossato_qty` a tutti gli effetti come "pronto" (vedi
`total_ready_qty`), quindi un oggetto con posizione "Indossa" segnato
come indossato è già, oggi, correttamente conteggiato. L'unico pezzo
mancante era l'AVVISO quando invece finisce impacchettato in una
valigia vera: `TripItem.has_luggage_mismatch` già confrontava
`Luggage.tipologia != Item.default_luggage_type` — con "indossa" come
valore, quel confronto fallisce automaticamente per QUALUNQUE valigia
reale, quindi l'avviso scatta già da solo, gratis, senza toccare
quella funzione. **Un'unica cosa richiedeva un vero cambiamento**: la
FRASE dell'avviso era scritta a mano, IN DUE PUNTI DIVERSI (tooltip in
`workspace.html` E messaggio JSON di `/api/quantita` in
`api/routes.py`), come `"andrebbe messo nella valigia da {label}"` —
con "Indossa" come label diventerebbe "andrebbe messo nella valigia da
indossa", frase senza senso. Centralizzata in una nuova proprietà
`Item.mismatch_hint`, che sceglie la frase giusta per i due casi, e
richiamata da entrambi i punti (se aggiungi un TERZO punto che deve
mostrare questo avviso in futuro, usa questa proprietà, non
ricostruire la frase a mano una terza volta). Icona di default
`"shirt"` aggiunta a `User.DEFAULT_LUGGAGE_TYPE_ICONS` (il
personalizzatore di icone in Impostazioni resta invece hard-coded solo
su cabina/stiva/zaino: non serve estenderlo, "Indossa" ha già
un'icona sensata di suo).

**Il pulsante "Ricalcola" ora fa tre cose in più.** Prima chiamava
SOLO `recompute_automatic_quantities` (aggiorna `target_qty` per gli
oggetti Fissa/Per giorno, es. dopo aver cambiato le date). Nuova
`resync_trip_with_catalog(trip, user)` in `utils.py`, chiamata in
aggiunta dalla route `trips.recompute`: (1) `sync_trip_items` (aggiunge
gli oggetti nuovi del catalogo — già idempotente, e in realtà gira già
da sola ad ogni apertura del workspace: richiamarla qui è innocuo, non
ridondante in modo dannoso); (2) rimuove le `TripItem` il cui oggetto è
stato nel frattempo archiviato (**bug reale**: restavano lì per
sempre); (3) riallinea `TripItem.sort_order` di OGNI oggetto del
viaggio a `Item.sort_order` attuale del catalogo (**bug reale**: un
oggetto riordinato nel Catalogo DOPO essere stato aggiunto al viaggio
restava nella vecchia posizione). Tocca SOLO le righe di `user`
(verificato con un test su un viaggio condiviso). Il pulsante ora
mostra un `confirm()` prima di procedere (nuovo, dato che può
eliminare righe, non solo aggiungerle) e un messaggio di riepilogo che
elenca solo le categorie di modifica effettivamente avvenute.

**Verifica isolamento eliminazione oggetti (richiesta esplicita, "controlla se...").**
Nessuna modifica di codice necessaria: `Item.owner_id` è già
per-utente, `catalog.delete_item` già filtra
`Item.query.filter_by(id=item_id, owner_id=current_user.id)`, e
`TripItem` garantisce per costruzione (vedi il suo stesso docstring)
che due collaboratori dello stesso viaggio abbiano SEMPRE righe
distinte, mai condivise — cancellare l'`Item` di un utente cascata
(`cascade="all, delete-orphan"`) solo sulle SUE `TripItem`, mai su
quelle di un altro. Il concetto di "pubblico" (`Item.is_public`) è
un'ESPORTAZIONE una tantum verso un file JSON di base
(`export_catalog_as_base`, vedi `importer.py`), non una condivisione
live: un nuovo utente che lo importa ottiene righe COMPLETAMENTE
proprie (nuovo `owner_id`), indipendenti da quelle originali fin da
subito. Aggiunto un test esplicito
(`test_deleting_item_only_affects_owner_not_shared_trip_collaborators`)
che lo dimostra concretamente su un viaggio condiviso reale, non solo
a parole — se in futuro questa garanzia dovesse mai incrinarsi (es.
introducendo un vero catalogo condiviso tra collaboratori), quel test
lo segnalerebbe subito.

## 4.40. Ricerca istantanea, eliminazione oggetti archiviati, pagina oggetto unificata (v3.8.0)

Quattro richieste distinte, in ordine di complessità crescente — la
quarta ha richiesto di ripensare la navigazione tra pagine dell'intero
catalogo, quindi le altre tre sono documentate brevemente, l'ultima
per esteso.

**Ricerca in tempo reale nel workspace del viaggio.** Il campo di
ricerca del pannello "Valigia" era un `<form method="get">`: bisognava
premere Invio (o ricaricare la pagina) per vedere i risultati — non
"in tempo reale" come richiesto. Convertita in ricerca puramente
client-side, esattamente come quella già esistente nella "Lista della
spesa" (`applyShoppingSearchFilter`): nuova `applyItemSearchFilter` /
`initItemSearch` in `dashboard.js`, filtro sull'attributo
`data-item-name` di ogni `.item-row` (aggiunto apposta), classe
`is-hidden-by-search` per nascondere righe e intere sezioni-categoria
senza risultati. **Passa automaticamente alla scheda "Tutti"** se il
testo cercato esiste in una categoria diversa da quella attualmente
selezionata — altrimenti sembrerebbe "nessun risultato" pur esistendo
altrove (la vecchia versione, ricaricando l'intera pagina, finiva
sempre su "Tutti" per costruzione; la nuova doveva replicarlo
esplicitamente). `app/trips/routes.py::workspace` non filtra più per
`q` lato server: il parametro resta SOLO per precompilare il campo
(serve a preservare il testo cercato passando da una pill di stato
all'altra, che restano navigazioni server-side vere e proprie). Il
drag-and-drop per riordinare resta sempre attivo durante la ricerca —
verificato che è sicuro: la lista COMPLETA resta sempre nel DOM (solo
nascosta via CSS), quindi l'ordine finale inviato al server include
sempre anche le righe momentaneamente filtrate, nella loro posizione
invariata.

**Eliminazione definitiva di oggetti archiviati.** Il pulsante
"Elimina definitivamente" esisteva già in `item_detail.html`, ma era
bloccato per QUALSIASI oggetto (anche già archiviato) ancora presente
in dei viaggi passati. `catalog.delete_item` ora permette
l'eliminazione definitiva di un oggetto ARCHIVIATO anche con uno
storico di viaggi: la cascata già configurata nel modello
(`Item.trip_items`, `cascade="all, delete-orphan"`) si occupa di
ripulire correttamente anche quelle righe. Un oggetto ancora ATTIVO
(non archiviato) e con storico resta protetto come prima (va prima
archiviato). Aggiunto anche un pulsante di eliminazione diretto per
riga nella lista "Vedi archiviati" (`items.html`), per non dover
aprire ogni oggetto singolarmente.

**"Salva oggetto" torna alla pagina di provenienza, stessa posizione
di scroll.** Vedi il meccanismo generico `initGenericScrollRestore` in
`dashboard.js`, descritto nella sezione seguente insieme al resto
della fusione — le due richieste erano risolvibili solo insieme, dato
che cambiava radicalmente da dove si "torna" dopo il salvataggio.

### Pagina unica per un oggetto (dettaglio + modifica fuse)

**Il problema:** "Modifica" (pagina `catalog.edit_item`,
`/oggetti/<id>/modifica`) e "dettaglio" (pagina `catalog.item_detail`,
`/oggetti/<id>`) erano due pagine SEPARATE che si rimandavano l'un
l'altra in continuazione — "Modifica" da una portava all'altra,
"Modelli e dettagli" dall'altra tornava alla prima — troppi click per
una singola modifica (bug reale segnalato, con screenshot: lo spazio
vuoto a destra del modulo di modifica, segnato con una X rossa, era il
suggerimento esplicito di dove mettere il contenuto della pagina
dettaglio).

**La fusione.** Le due viste Python (`item_detail` e `edit_item`) e i
due template (`item_detail.html` e `item_form.html`) sono diventati
UNO: la vista `catalog.item_detail` (`/oggetti/<id>`, ora GET+POST) fa
tutto quello che facevano prima le due insieme. `item_form.html` è
stato ELIMINATO. `catalog.edit_item` (`/oggetti/<id>/modifica`) resta
SOLO come redirect di retrocompatibilità verso `catalog.item_detail`
(preservando `da_viaggio`/`ritorno` in querystring), per eventuali
link o segnalibri vecchi — NESSUN codice nell'app punta più lì
direttamente, è puro fallback.

**Layout (`item_detail.html`, nuova classe CSS `.item-page-layout`):**
due colonne su desktop — modulo di modifica a sinistra (`max-width:
560px`, come prima), dettagli (zona pericolosa, modelli, storico nei
viaggi) a destra — che collassano in una sola colonna sotto gli
**860px** (stessa soglia "mobile" già usata altrove nell'app per il
menu hamburger, per coerenza) con il modulo prima e i dettagli sotto.
**Attivo SOLO per un oggetto esistente**: per "Nuovo oggetto"
(`item is None`) niente `.item-page-layout`, una sola colonna col solo
modulo — zona pericolosa/modelli/storico richiedono che l'oggetto
esista già (serve un ID).

**La card "Automazione quantità" è stata RIMOSSA**, non solo spostata:
si limitava a ripetere in sola lettura (regola quantità, tipologia
valigia, peso) campi già editabili proprio accanto, nel modulo — utile
quando erano due pagine separate, ridondante e un po' assurdo ora che
sono la stessa pagina. Se in futuro serve di nuovo una vista
"riepilogo" di quei campi, va ripensata (es. per la stampa), non
semplicemente riportata indietro: sarebbe di nuovo la stessa
duplicazione.

**Da dove si torna, dopo aver salvato — il pezzo più delicato.** Tre
helper nuovi in `app/catalog/routes.py`:

- `_safe_internal_redirect_target(url)` — restituisce `url` SOLO se
  punta a questo stesso host, altrimenti `None`. Usato ovunque in
  questo file si segua un Referer per un redirect: un Referer è un
  header che il browser invia così com'è, quindi in teoria
  contraffabile da un link costruito ad arte — non va mai usato alla
  cieca (anche i redirect via Referer già esistenti da PRIMA di questa
  versione, es. `toggle_archive_item`, ora ci passano attraverso).
- `_resolve_navigation_context()` — calcola `(from_trip, return_to)`
  una volta sola: se c'è un parametro esplicito `da_viaggio` (link
  "Vai alle impostazioni dell'oggetto" dal workspace di un viaggio),
  quello vince SEMPRE, perché è deliberato, non un'euristica —
  `return_to` diventa l'URL del workspace di quel viaggio (che ha GIÀ
  il proprio scroll-restore per-viaggio, v3.7.1, invariato). Altrimenti
  `return_to` viene dal campo nascosto `ritorno` (che sopravvive a
  "Salva e vai al successivo"/Precedente/Successivo, portando lo
  stesso contesto lungo tutta la sequenza) o, alla primissima apertura,
  dal Referer HTTP — con il catalogo attivo come ripiego finale, mai
  `None`.
- `_nav_context_kwargs(from_trip, return_to)` — i parametri
  (`da_viaggio` oppure `ritorno`, mai entrambi) da riattaccare ai link
  "Precedente"/"Successivo" e ai redirect interni, per NON perdere il
  contesto passando da un oggetto all'altro in sequenza. Il modulo
  principale li porta anche come campi nascosti (`{% for key, value in
  nav_kwargs.items() %}`), fondamentale perché al POST il Referer del
  browser sarebbe questa stessa pagina, non più utile.

"Salva oggetto" (il submit normale, non "Salva e vai al successivo")
ora fa `redirect(return_to)` invece di restare bloccato sulla stessa
pagina di modifica (comportamento deliberato di v3.6.x, esplicitamente
superato da questa richiesta). Lato client, **`initGenericScrollRestore`**
in `dashboard.js` (accanto a `initWorkspaceScrollRestore`, invariata)
generalizza lo stesso meccanismo (sessionStorage + `beforeunload` +
ripristino una tantum) a QUALSIASI pagina, usando l'URL COMPLETO
(percorso + querystring) come chiave invece di un ID di viaggio — si
disattiva da sola se `[data-main-tabs]` è nel DOM (pagina di un
viaggio: ha già il proprio meccanismo, più preciso per quel caso
specifico, perché ignora deliberatamente i filtri nell'URL di
partenza). Funziona perché il server fa sempre tornare l'utente
ESATTAMENTE all'URL di partenza, querystring inclusa — se in futuro un
qualunque redirect "torna a…" ricostruisce l'URL a mano invece di
riusare quello originale byte per byte, questo meccanismo smette di
funzionare silenziosamente (la chiave in sessionStorage non
coinciderebbe più).

Anche le route satellite (`add_variant`, `edit_variant`,
`delete_variant`, upload/rimozione foto di oggetto e modello) ora
tornano al Referer (validato) invece che a un URL fisso — così un
qualunque cambiamento fatto da dentro la pagina di un oggetto (nuovo
modello, nuova foto) non perde il contesto `da_viaggio`/`ritorno`
eventualmente presente nell'URL corrente.

**Se in futuro aggiungi un'altra azione che deve "tornare a…" da
qualche parte in questo file**: usa `_safe_internal_redirect_target`
sul Referer prima di un qualunque `redirect()`, non aggiungerlo senza.
Se aggiungi un altro punto di ingresso alla pagina di un oggetto
(un altro link tipo "Vai alle impostazioni dell'oggetto"), NON serve
altro codice — basta che il link porti `da_viaggio=<id>` o lasci fare
al Referer naturale del browser: `_resolve_navigation_context` lo
raccoglie da solo.

## 4.39. Anteprima foto dei modelli nel viaggio, scroll preservato tornando dalle impostazioni (v3.7.1)

**Bug: l'anteprima/zoom della foto non compariva per un oggetto CON
modelli, guardato dalla schermata di un viaggio** (funzionava invece
per un oggetto semplice, senza modelli). Causa: la finestra di scelta
del modello (`initVariantModal` in `dashboard.js::buildRow`) costruisce
ogni riga a partire da `data-variants`, generato dal filtro Jinja
`get_variant_modal_data` (`app/__init__.py`) — quel filtro non aveva
MAI incluso alcuna informazione sulla foto (né un flag `has_photo`, né
un URL), quindi la finestra non aveva letteralmente nulla da mostrare,
anche quando il modello ne aveva una caricata sul serio. **Corretto in
due punti, non uno solo**: (1) il filtro ora restituisce anche
`has_photo`/`photo_url` (quest'ultimo da `url_for("catalog.variant_photo_file", ...)`,
`None` se assente); (2) `buildRow` crea una miniatura `.item-photo-thumb`
con `data-photo-zoom-trigger` quando `v.has_photo` è vero — riusa
esattamente lo stesso overlay di zoom già delegato in `app.js` (nessun
nuovo listener da agganciare). **Se in futuro `get_variant_modal_data`
guadagna altri campi derivati da `ItemVariant`, ricordati che è
l'UNICO punto che alimenta quella finestra: qualunque informazione che
la riga principale dell'oggetto già mostra (qui: la foto) va replicata
esplicitamente qui, non ereditata automaticamente.** Verificato con un
test end-to-end via client HTTP reale
(`test_variant_photo_appears_in_trip_workspace_modal_data` in
`test_smoke.py`, non solo la funzione del filtro isolata): carica
davvero una foto, apre il workspace, controlla che `data-variants`
contenga `has_photo: true` e un `photo_url` che risponde 200 coi byte
giusti.

**Scroll perso tornando da "Torna al viaggio"**: i link "Torna al
viaggio" dalle pagine di impostazioni raggiunte da un viaggio (oggetto,
valigie, condivisione, modifica viaggio) sono navigazioni a PAGINA
INTERA verso `trips.workspace` — non l'overlay del pannello di
dettaglio — quindi il workspace si ricaricava sempre da capo, con lo
scroll che ripartiva dall'inizio anche se prima si era molto più in
basso (bug reale segnalato). **Corretto con
`initWorkspaceScrollRestore()` in `dashboard.js`**: salva
`window.scrollY` in `sessionStorage` (chiave per-viaggio, letta da
`[data-main-tabs] data-trip-id`) su `beforeunload`, e lo ripristina —
UNA TANTUM, poi la chiave viene rimossa — al successivo caricamento
dello stesso viaggio. Se non c'è nulla di salvato (prima apertura,
arrivo da un altro punto dell'app), il comportamento resta quello di
sempre: scroll in cima. **Se in futuro aggiungi un'altra pagina di
impostazioni raggiunta da un viaggio con un proprio "Torna al
viaggio", non serve toccare nulla di nuovo**: finché il link torna a
`trips.workspace` con lo stesso `trip_id` (senza parametri aggiuntivi
nell'URL), il ripristino scatta automaticamente.

**Nota tecnica**: la suite pytest non può eseguire JS reale in un
browser, quindi questa seconda correzione non ha un test automatico
nella suite Python. È stata verificata a mano con uno script
Node/jsdom (`tests/manual_js_checks/verify_workspace_scroll_restore.js`,
con relativo README nella stessa cartella — non fa parte di CI, va
eseguito manualmente se tocchi questa funzione in futuro) che simula
`beforeunload`/ricaricamento pagina e conferma: nessun valore salvato
→ nessuna chiamata a `scrollTo`; valore salvato → `scrollTo` chiamato
con quel valore E la chiave rimossa subito dopo.

## 4.38. Modelli per un oggetto nuovo, e foto per oggetti/modelli (v3.7.0)

**Bug del "nuovo oggetto senza modelli"**: `catalog.new_item` reindirizzava
sempre a `catalog.items` (la lista) dopo il salvataggio — "Modelli e
dettagli" compare SOLO quando `item` esiste già (`{% if item %}` in
`item_form.html`), quindi un oggetto appena creato non aveva NESSUN
percorso diretto per aggiungere modelli, finché non veniva ritrovato
nella lista e riaperto in modifica. Corretto reindirizzando invece a
`catalog.edit_item` per lo STESSO oggetto appena creato: la pagina di
atterraggio mostra già "Modelli e dettagli" (ed ora anche il
caricamento foto), senza alcun giro in più.

**Foto per oggetti e modelli — un booleano, non il nome del file**:
`Item.has_photo`/`ItemVariant.has_photo` (non un campo con
l'estensione, dato che questa può cambiare a ogni ricaricamento — jpg
sostituito da png, per dire) — il file vive su disco in
`DATA_DIR/item-photos/{item|variant}_<id>.<ext>`, cercato per
prefisso al momento di servirlo (`_existing_photo_path`), stesso
principio già in uso per le copertine dei viaggi
(`trips/routes.py::_cover_uploads_dir`).

**Un solo visualizzatore a schermo intero, condiviso da OGNI pagina**:
il markup vive in `base.html` (non in un template specifico), la
logica in `app.js` (caricato ovunque, a differenza di `dashboard.js`
che lo è solo su alcune pagine) — usa la DELEGA DEGLI EVENTI (un solo
ascoltatore su `document`, non uno per miniatura): funziona anche per
miniature aggiunte DOPO il caricamento della pagina (es. dentro un
pannello caricato via AJAX), senza dover essere ri-agganciato ogni
volta. Ogni miniatura è semplicemente `<img data-photo-zoom-trigger>`
— cliccarla apre l'overlay con la STESSA immagine (niente url
"miniatura" separata da quella "intera": non c'è generazione di
thumbnail, il ridimensionamento è solo CSS via `object-fit:cover`).

**Pulizia dei file all'eliminazione**: eliminare un oggetto o un
modello rimuove ANCHE il file foto corrispondente dal disco (non solo
la riga dal database) — verificato con un test dedicato che controlla
il filesystem, non solo lo stato del database.

**Lezione da un falso allarme durante la verifica dal vivo**: un
`400 CSRF` intermittente durante i test manuali via curl si è rivelato
un artefatto del MIO script di prova (token riletti da pagine caricate
in momenti diversi, quindi ormai scaduti/sostituiti da Flask-WTF) — non
un bug dell'applicazione. Isolare la richiesta di caricamento DA SOLA
(senza `-L`, leggendo il token da una pagina appena ricaricata) ha
confermato una risposta 302 pulita. **Quando un test manuale mostra un
errore intermittente legato a token/sessione, verificare PRIMA se il
test stesso sta riusando dati ormai scaduti, prima di sospettare
l'applicazione.**


**`app/seed_data/catalogo_base.json` esiste davvero da questa
versione**: fino ad ora era solo un meccanismo pronto ma mai usato (il
terzo livello di seeding aggiunto in v3.6.3, verificato solo con dati
di prova). Ora contiene il catalogo curato fornito dall'utente —
5 categorie (Vestiti, Bagno, Elettronica, Documento, Medicine),
17 oggetti, i Pantaloni con 6 modelli specifici (Jeans azzurri corti,
Blu scuri, Bianchi, Grigi, Verdi, Blu scuri leggeri), 2 valigie reali
(Rimowa Classic Cabin e Hybrid Check-in). Verificato dal vivo su
un'installazione fatta completamente da zero, non solo con i test.

**Bug reale scoperto sistemando i test**: `provision_new_user_defaults`
creava SEMPRE due valigie generiche ("Valigia da stiva", "Bagaglio a
mano") PRIMA di importare il catalogo di base — quando quel catalogo
è un CSV (che non porta valigie), questo va bene; ma quando è un JSON
che INCLUDE le proprie valigie (come ora), un nuovo utente si
ritrovava con QUATTRO valigie invece di due: le due generiche più le
due curate, tutte insieme. **Corretto invertendo l'ordine**: prima
importa il catalogo (comprese le sue eventuali valigie), POI crea le
due generiche SOLO se l'importazione non ne ha portata nessuna. Un
catalogo curato con le proprie valigie non genera più doppioni.

**Perché il catalogo curato ha una sola valigia marcata "predefinita
per nuovo viaggio" (solo la Cabina, non la Stiva) — e perché va
bene così**: è una scelta legittima di chi ha esportato il catalogo,
non un errore da correggere. `ensure_default_trip_luggages` gestisce
correttamente qualunque numero di valigie predefinite (zero, una,
molte) senza mai fallire — ma diversi test presumevano SEMPRE
esattamente due (cabina + stiva) attive di default su ogni nuovo
viaggio di prova. **Non ho forzato il catalogo a marcarne due per far
tornare i test**: ho invece corretto l'helper di test
`_make_trip` (e il caso analogo per un secondo utente collaboratore)
perché garantisca ENTRAMBI i tipi attivi per i propri scopi, SENZA
toccare il comportamento reale dell'app né i dati dell'utente. **Lezione:
quando un cambiamento nei dati di partenza rompe delle assunzioni nei
test, la domanda giusta è "il test presumeva qualcosa di troppo
specifico?", non "i dati vanno adattati al test?" — qui la risposta
corretta era la prima.**


**Il pendolo si è fermato al centro, letteralmente**: dopo aver tolto
`text-align:right` dai valori (v3.6.5), era rimasto un
`padding-left:20px` pensato per mantenere un po' di respiro dalla
colonna precedente — ma quel rientro, combinato con una colonna
relativamente stretta (12%) e valori brevi ("150 g"), dava l'illusione
visiva di un testo CENTRATO invece che allineato a sinistra in modo
pulito (bug reale segnalato). **Corretto rimuovendo ogni trattamento
speciale**: la colonna Peso ora eredita esattamente lo stesso
comportamento delle altre (nessuna regola dedicata, nessun padding
extra) — lo spazio adeguato dalla colonna precedente resta comunque
garantito dalla larghezza allargata (12% invece dell'8% originale),
senza bisogno di nessun accorgimento aggiuntivo.

**Lezione da un problema risolto tre volte sulla stessa colonna**:
ogni "piccolo" aggiustamento visivo (allineamento, poi padding) ha
introdotto un effetto collaterale non previsto — la soluzione più
semplice (nessuna regola dedicata affatto) era anche la più robusta
fin dall'inizio. Quando un dettaglio visivo continua a tornare
indietro dopo più correzioni mirate, vale la pena chiedersi se la
colonna abbia davvero bisogno di un trattamento SPECIALE, o se il
problema originale (poco spazio dalla colonna precedente) si risolva
meglio a monte (qui: allargando la colonna), lasciando l'allineamento
del tutto invariato rispetto alle altre.


**Causa esatta**: `dashboard.js` — dove vive TUTTA la logica del
trascinamento (`initColumnResize`, `initColumnEditToggle`) — era
incluso SOLO da `catalog/items.html` (tramite `{% block extra_scripts %}`).
Quando ho esteso il sistema a Valigie e Categorie (v3.6.4), ho
aggiunto il markup (pulsante, maniglie, attributi) ma NON l'inclusione
dello script in quelle due pagine — il pulsante c'era, le maniglie
erano nel DOM, il CSS era pronto, ma NESSUN ascoltatore di eventi era
mai stato agganciato a nulla: premere il pulsante non faceva
letteralmente nulla (bug reale segnalato: "non appaiono i separatori,
non posso modificare"). Corretto aggiungendo lo stesso
`<script src=".../dashboard.js">` anche a `luggage/list.html` e
`catalog/categories.html`. **Lezione: quando si estende una
funzionalità JS a una pagina nuova, verificare SEMPRE che lo script
che la contiene sia effettivamente CARICATO in quella pagina — un
markup e un CSS perfetti restano completamente inerti senza lo script
che li anima, e questo tipo di errore non produce nessun errore
visibile in console: semplicemente, non succede nulla.**

**Allineamento Peso: il pendolo è tornato indietro**. Prima
l'etichetta era finita per errore a destra insieme ai valori (v3.6.3);
poi ho separato etichetta (sinistra) e valori (destra, v3.6.4); ora,
su richiesta esplicita, anche i VALORI tornano a sinistra — lo spazio
da "Valigia predefinita" resta comunque adeguato grazie alla colonna
allargata (12% invece dell'8% originale) più un padding-left
aggiuntivo, senza bisogno di cambiare allineamento per ottenerlo.

**Colonna "Oggetti" nelle Categorie**: rimosso `text-align:right`
inline sia dall'intestazione sia dalla cella dati — era così fin dalla
prima versione di quella tabella (mai toccata prima d'ora), semplice
incoerenza mai notata prima.

**Spaziatura `.toolbar`**: aggiunto `margin-bottom:16px` alla classe
condivisa da tutte le barre-pulsanti dell'app (non solo "Modifica
tabella") — prima lo spazio SOTTO dipendeva solo da cosa veniva DOPO,
niente di garantito dalla classe stessa.


**Uscita automatica rimossa, come richiesto**: `finishDrag` (dentro
`initColumnResize`) non chiama più `exitColumnEditMode()` dopo un
salvataggio riuscito — quella chiamata è rimasta SOLO dentro
`initColumnEditToggle`, quindi l'unico modo di uscire dalla modalità
modifica è ora il clic esplicito su "Fine modifica". Permette di
regolare più colonne di fila senza dover riattivare la modalità ogni
volta.

**"Peso" — intestazione a sinistra, solo i VALORI a destra**: la
regola di allineamento era finita per errore anche sull'etichetta
della colonna (`th:nth-child(5)`), non solo sui dati (`td:nth-child(5)`)
— separata: ora `td:nth-child(5)` resta allineato a destra (i numeri
restano ben distinti dalla colonna precedente), `th:nth-child(5)`
torna ad allinearsi come tutte le altre intestazioni.

**Estensione a Valigie e Categorie — trovato e corretto un problema di
generalizzazione**: `initColumnResize` assumeva SEMPRE una prima
colonna "di servizio" non regolabile (nel Catalogo: il trascina-
riordina, 30px fissi) e tagliava sempre il primo elemento
(`ths.slice(1)`) prima di salvare — ma Valigie e Categorie NON hanno
questa colonna fissa: OGNI colonna, dalla prima, è regolabile e va
salvata. Corretto leggendo un nuovo attributo
`data-resize-start-index` sulla tabella (default 0, quante colonne
iniziali NON regolabili saltare prima di quella salvata) invece di
un valore fisso — il Catalogo dichiara esplicitamente `="1"`, Valigie
e Categorie usano il default 0. **Lezione: quando si generalizza un
meccanismo scritto pensando a UN solo caso concreto, verificare sempre
quali assunzioni erano implicite in quel caso specifico (qui: "la
prima colonna non conta mai") prima di applicarlo a un secondo caso
strutturalmente diverso.**

**Pulsante "Modifica tabella" nascosto in modalità icone su mobile**:
il pulsante porta ora `data-column-style` (lo stesso valore del
`.table-scroll` a cui appartiene) — sotto i 680px, se lo stile è
"automatico", una regola CSS lo nasconde (le colonne in quel momento
mostrano icone, non testo: regolarne la larghezza non avrebbe alcun
effetto visibile). Le preferenze ESPLICITE ("solo testo") restano
sempre visibili, a qualunque larghezza.


**Il problema che questo risolve**: `export_catalog_as_base` salva
SEMPRE in `data/catalogo_base.json` — la cartella dati persistente,
esclusa di proposito da git (`.gitignore`), perché lì vive anche il
database vero. Questo significa che, prima di questa versione, il
catalogo curato con le spunte pubbliche non poteva MAI raggiungere
GitHub: un push "così com'è" avrebbe sempre incluso il vecchio
`app/seed_data/catalogo_base.csv` originale (quello con "Felpa per il
viaggio" e simili) come unico paracadute per una nuova installazione,
indipendentemente da quanto lavoro fosse stato fatto nella pagina
Catalogo pubblico — perché quel lavoro viveva SOLO nel runtime, mai
nel codice.

**Soluzione: un terzo livello, imbustato nel codice**. Aggiunto
`BASE_CATALOG_JSON_PATH = app/seed_data/catalogo_base.json` — se
presente (cioè se qualcuno lo ha scaricato con "Scarica il file" e
committato con questo nome esatto), `import_base_catalog_for_user` lo
usa AL POSTO del vecchio CSV, senza bisogno di alcuna conversione di
formato (è già esattamente ciò che `export_catalog_as_base` genera).
**Ordine di precedenza a tre livelli**: (1) `data/catalogo_base.json`
— personalizzazione LIVE di questa specifica installazione, mai su
GitHub; (2) `app/seed_data/catalogo_base.json` — se committato,
diventa il nuovo default per CHIUNQUE clona il repository; (3)
`app/seed_data/catalogo_base.csv` — l'originale, ultimo paracadute se
nessuno dei due sopra esiste.

**Verificato dal vivo in modo diretto, non solo con un test**: creato
un finto `catalogo_base.json` con un oggetto e una valigia
riconoscibili, avviato un server COMPLETAMENTE da zero (nessun utente
esistente, la condizione esatta di "primissimo avvio" descritta in
`_ensure_seed_data`), e confermato che l'admin ricevesse quel
catalogo — non più quello del CSV originale. File di prova rimosso
subito dopo, per non lasciarlo nel pacchetto consegnato.


**"Modifica dev'essere applicata a tutte le categorie, subito"**: la
pagina Catalogo → Oggetti mostra UNA `<table>` per categoria, tutte
con la stessa chiave (`data-resizable-table="catalog-items"`) e quindi
le stesse larghezze salvate — al RICARICAMENTO della pagina questo era
già corretto (tutte leggono lo stesso `current_user.get_column_widths`),
ma SENZA ricaricare, trascinare in UNA tabella lasciava le ALTRE
invariate a schermo (solo il DOM della tabella toccata veniva
aggiornato). Corretto propagando lo stesso risultato, dopo un
salvataggio riuscito, a TUTTE le `<table>` con la stessa chiave
presenti in pagina (`document.querySelectorAll` per attributo, non
solo l'elemento su cui si è trascinato).

**Maniglie nascoste per default, visibili solo in "modalità modifica
tabella"**: un separatore sempre visibile era segnalato come brutto da
vedere costantemente — ora `display:none` di default,
`display:block` solo con la classe `editing-table-columns` sul
`<body>`, attivata dal pulsante "Modifica tabella"
(`initColumnEditToggle`) e DISATTIVATA IN AUTOMATICO subito dopo un
salvataggio riuscito (`exitColumnEditMode()`, chiamata dentro
`finishDrag` di `initColumnResize`) — l'utente non deve mai ricordarsi
di "uscire" a mano dalla modalità modifica.

**Conferma sui modelli nell'esportazione pubblica** (domanda posta
direttamente, non un bug): spuntare un oggetto come pubblico esporta
SEMPRE anche i suoi modelli (`ItemVariant`), se configurati — non
esiste una spunta separata per i modelli, viaggiano automaticamente
col loro oggetto (vedi `export_catalog_as_base` in importer.py,
verificato anche con un test dedicato).


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
