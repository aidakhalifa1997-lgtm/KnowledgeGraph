// Rend chaque schéma SVG de schemas.html en PNG (×2) dans ../figures/.
// Usage : NODE_PATH=$(npm root -g) node render_schemas.cjs
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2 });
  await page.goto("file://" + path.join(__dirname, "schemas.html"));
  for (const id of ["schema_architecture", "schema_pipeline_ingestion", "schema_modele_graphe", "schema_workflow", "schema_deploiement"]) {
    await page.locator(`#${id}`).screenshot({ path: path.join(__dirname, "..", "figures", `${id}.png`) });
    console.log(`${id}.png`);
  }
  await browser.close();
})();
