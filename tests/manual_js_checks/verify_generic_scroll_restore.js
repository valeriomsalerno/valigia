const { JSDOM } = require("jsdom");
const fs = require("fs");

const dashboardJsPath = "/home/claude/valigia/valigia/app/static/js/dashboard.js";
const src = fs.readFileSync(dashboardJsPath, "utf8");

async function run(label, { savedScroll, path, hasWorkspaceMarker }) {
  const markerHtml = hasWorkspaceMarker ? '<div data-main-tabs data-trip-id="9"></div>' : "";
  const dom = new JSDOM(`<!doctype html><html><body>${markerHtml}</body></html>`, {
    runScripts: "outside-only",
    url: `http://localhost${path}`,
  });
  const { window } = dom;
  let scrolledTo = null;
  window.scrollY = 0;
  window.scrollTo = (x, y) => { scrolledTo = y; window.scrollY = y; };
  window.requestAnimationFrame = (cb) => cb();

  const key = `valigia-scroll-url-${path}`;
  if (savedScroll !== undefined) {
    window.sessionStorage.setItem(key, String(savedScroll));
  }

  dom.window.eval(src);
  dom.window.eval("initGenericScrollRestore();");

  console.log(`--- ${label} ---`);
  console.log("scrollTo chiamato con:", scrolledTo);

  window.scrollY = 777;
  window.dispatchEvent(new window.Event("beforeunload"));
  console.log("salvato su beforeunload:", window.sessionStorage.getItem(key));
  console.log();
}

(async () => {
  await run("Caso 1: catalogo, nessun valore salvato", { path: "/catalogo/oggetti" });
  await run("Caso 2: catalogo con querystring, valore salvato in precedenza", { path: "/catalogo/oggetti?archiviati=1", savedScroll: 555 });
  await run("Caso 3: workspace di un viaggio -> il meccanismo generico NON deve intervenire", { path: "/viaggi/9", savedScroll: 999, hasWorkspaceMarker: true });
  process.exit(0);
})();
