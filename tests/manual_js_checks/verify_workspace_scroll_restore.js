const { JSDOM } = require("jsdom");
const fs = require("fs");

const dashboardJsPath = "/home/claude/valigia/valigia/app/static/js/dashboard.js";
const src = fs.readFileSync(dashboardJsPath, "utf8");

async function run(label, { savedScroll, tripId }) {
  const dom = new JSDOM(`<!doctype html><html><body>
    <div data-main-tabs data-trip-id="${tripId}"></div>
  </body></html>`, { runScripts: "outside-only", url: "http://localhost/viaggi/" + tripId });

  const { window } = dom;

  // jsdom non implementa window.scrollTo/scrollY di default in modo utile: li simuliamo.
  let scrolledTo = null;
  window.scrollY = 0;
  window.scrollTo = (x, y) => { scrolledTo = y; window.scrollY = y; };

  // requestAnimationFrame: eseguiamo subito il callback (sincrono) per il test.
  window.requestAnimationFrame = (cb) => cb();

  if (savedScroll !== undefined) {
    window.sessionStorage.setItem(`valigia-scroll-trip-${tripId}`, String(savedScroll));
  }

  dom.window.eval(src);

  // Chiamiamo direttamente initWorkspaceScrollRestore (definita nel file) tramite eval del suo nome.
  dom.window.eval("initWorkspaceScrollRestore();");

  const keyStillPresent = dom.window.sessionStorage.getItem(`valigia-scroll-trip-${tripId}`);

  console.log(`--- ${label} ---`);
  console.log("scrollTo chiamato con:", scrolledTo);
  console.log("chiave sessionStorage dopo il ripristino:", keyStillPresent);

  // Simuliamo l'evento beforeunload per verificare che lo scroll corrente venga salvato.
  window.scrollY = 456;
  window.dispatchEvent(new window.Event("beforeunload"));
  const savedAfterUnload = dom.window.sessionStorage.getItem(`valigia-scroll-trip-${tripId}`);
  console.log("valore salvato su beforeunload (atteso 456):", savedAfterUnload);
  console.log();
}

(async () => {
  await run("Caso 1: nessun valore salvato in precedenza (prima apertura)", { tripId: 42 });
  await run("Caso 2: valore salvato in precedenza (torno dalle impostazioni)", { tripId: 42, savedScroll: 1234 });
  process.exit(0);
})();
