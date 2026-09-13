const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");

// real-lucide.js: bundle UMD scaricato con `npm pack lucide` (dist/umd/lucide.js)
// — non incluso nel repository, va scaricato accanto a questo script.
const realLucideSrc = fs.readFileSync(path.join(__dirname, "real-lucide.js"), "utf8");
const labSrc = fs.readFileSync(path.join(__dirname, "..", "..", "app", "static", "js", "lucide-lab.js"), "utf8");

const dom = new JSDOM(`<!doctype html><html><body>
  <i data-lucide="shirt"></i>
  <i data-lucide="luggage-cabin"></i>
  <i data-lucide="shorts-boxer"></i>
</body></html>`, { runScripts: "outside-only" });

dom.window.eval(realLucideSrc);
console.log("lucide caricato:", typeof dom.window.lucide);
console.log("lucide.icons esiste:", typeof dom.window.lucide.icons, "numero chiavi:", dom.window.lucide.icons ? Object.keys(dom.window.lucide.icons).length : "n/a");
console.log("una chiave di esempio:", dom.window.lucide.icons ? Object.keys(dom.window.lucide.icons).slice(0,5) : null);

dom.window.eval(labSrc);
console.log("LUCIDE_LAB_ICONS caricato, numero:", Object.keys(dom.window.LUCIDE_LAB_ICONS).length);

dom.window.eval(`
  if (window.lucide && window.LUCIDE_LAB_ICONS) {
    const nativeCreateIcons = window.lucide.createIcons.bind(window.lucide);
    window.lucide.createIcons = function (options) {
      const icons = Object.assign({}, window.lucide.icons, window.LUCIDE_LAB_ICONS, (options && options.icons) || {});
      return nativeCreateIcons(Object.assign({}, options, { icons }));
    };
  }
`);

dom.window.eval("window.lucide.createIcons();");

const doc = dom.window.document;
console.log("\n--- risultato dopo createIcons() ---");
doc.querySelectorAll("[data-lucide]").forEach(el => {
  console.log(el.getAttribute("data-lucide"), "-> innerHTML length:", el.innerHTML.length, el.outerHTML.slice(0, 120));
});
