const { JSDOM } = require("jsdom");
const fs = require("fs");

const dashboardJsPath = "/home/claude/valigia/valigia/app/static/js/dashboard.js";
const src = fs.readFileSync(dashboardJsPath, "utf8");

const html = `<!doctype html><html><body>
  <div data-main-tabs data-trip-id="7"></div>
  <div class="search-field"><input type="text" data-item-search value=""></div>
  <div class="category-tabs" data-category-tabs>
    <button type="button" class="category-tab active" data-category-tab="all">Tutti</button>
    <button type="button" class="category-tab" data-category-tab="10">Vestiti</button>
    <button type="button" class="category-tab" data-category-tab="20">Elettronica</button>
  </div>
  <div class="category-section category-panel" data-category-panel="10">
    <div class="item-list" data-reorderable>
      <div class="item-row" data-item-name="Pantaloni blu"></div>
      <div class="item-row" data-item-name="Camicia bianca"></div>
    </div>
  </div>
  <div class="category-section category-panel" data-category-panel="20">
    <div class="item-list" data-reorderable>
      <div class="item-row" data-item-name="Caricabatterie USB"></div>
    </div>
  </div>
</body></html>`;

const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://localhost/viaggi/7" });
const { window } = dom;
window.requestAnimationFrame = (cb) => cb();
dom.window.eval(src);

function classesOf(selector) {
  return Array.from(dom.window.document.querySelectorAll(selector)).map(
    (el) => `${el.dataset.itemName || el.dataset.categoryPanel || el.dataset.categoryTab}: [${el.className}]`
  );
}

console.log("--- Prima di digitare (nessun filtro attivo) ---");
console.log(classesOf(".item-row"));

const input = dom.window.document.querySelector("[data-item-search]");
input.value = "camicia";
dom.window.eval("applyItemSearchFilter();");

console.log("\n--- Dopo aver digitato 'camicia' (categoria 'Vestiti' inizialmente attiva) ---");
console.log(classesOf(".item-row"));
console.log(classesOf(".category-panel"));
console.log("Tab attiva ora:", dom.window.document.querySelector(".category-tab.active").dataset.categoryTab);

input.value = "usb";
dom.window.eval("applyItemSearchFilter();");
console.log("\n--- Dopo aver digitato 'usb' (deve trovare l'oggetto in un'altra categoria) ---");
console.log(classesOf(".item-row"));
console.log(classesOf(".category-panel"));
console.log("Tab attiva ora:", dom.window.document.querySelector(".category-tab.active").dataset.categoryTab);

input.value = "";
dom.window.eval("applyItemSearchFilter();");
console.log("\n--- Dopo aver svuotato la ricerca ---");
console.log(classesOf(".item-row"));
console.log(classesOf(".category-panel"));

process.exit(0);
