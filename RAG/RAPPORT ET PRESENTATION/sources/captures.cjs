// Parcourt l'application réelle (pile Docker Compose) et produit les captures d'écran du mémoire.
// Relève aussi les erreurs de console et les violations de la politique de sécurité (CSP).
// Usage : NODE_PATH=$(npm root -g) BASE_URL=http://localhost:8080 node captures.cjs
const path = require("node:path");
const fs = require("node:fs");
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL || "http://localhost:8080";
const OUT = path.join(__dirname, "..", "figures", "captures");
const PASSWORD = "Demo-Orizia-2026"; // comptes de démonstration du corpus fictif
fs.mkdirSync(OUT, { recursive: true });

const problems = [];

async function session(browser, username, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "fr-FR", ...options });
  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") problems.push(`[${username}] console : ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`[${username}] exception : ${e.message}`));
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (e) => console.error(`CSP: ${e.violatedDirective} ${e.blockedURI}`));
  });
  await page.goto(BASE);
  if (username) {
    await page.getByLabel("Identifiant").fill(username);
    await page.getByLabel("Mot de passe").fill(PASSWORD);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await page.waitForSelector("nav[aria-label='Navigation principale']");
  }
  return { context, page };
}

async function shot(page, name, { full = false } = {}) {
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: full });
  console.log(`${name}.png`);
}

async function go(page, hash, waitFor) {
  const wait = waitFor ? page.waitForResponse((r) => r.url().includes(waitFor) && r.status() < 500, { timeout: 60000 }) : null;
  await page.evaluate((h) => { window.location.hash = h; }, hash);
  if (wait) await wait;
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1200); // mise en page du graphe (Cytoscape)
}

(async () => {
  const browser = await chromium.launch();

  // Connexion
  {
    const { context, page } = await session(browser, null);
    await page.getByLabel("Identifiant").fill("collaborateur");
    await shot(page, "capture_connexion");
    await context.close();
  }

  // Administrateur : accueil, assistant, explorateur, recommandations, documents
  {
    const { context, page } = await session(browser, "admin");
    await page.waitForLoadState("networkidle");
    await shot(page, "capture_accueil");
    await go(page, `/ask/${encodeURIComponent("Quelles applications dépendent de CoreNova ?")}`, "/api/ask");
    await shot(page, "capture_assistant_relationnel");
    await shot(page, "capture_assistant_relationnel_complet", { full: true });
    await go(page, "/explorer/sys:corenova", "/api/graph/neighborhood");
    await shot(page, "capture_explorateur");
    const docs = await page.evaluate(async () => {
      const raw = sessionStorage.getItem("orizia.session");
      const token = raw ? JSON.parse(raw).token : "";
      const r = await fetch("/api/documents", { headers: { Authorization: `Bearer ${token}` } });
      return r.json();
    });
    const kyc = docs.find((d) => d.reference === "PRC-KYC-001" && d.status === "active");
    await go(page, `/recommendations/${kyc.id}`, "/api/recommendations/document");
    await shot(page, "capture_recommandations");
    await go(page, `/documents/${kyc.id}`, `/api/documents/${kyc.id}`);
    await shot(page, "capture_documents");
    await context.close();
  }

  // Collaborateur : contradiction et abstention liée aux droits
  {
    const { context, page } = await session(browser, "collaborateur");
    await go(page, `/ask/${encodeURIComponent("Quelle est la fréquence de revue périodique des clients à risque élevé ?")}`, "/api/ask");
    await shot(page, "capture_assistant_contradiction");
    await go(page, `/ask/${encodeURIComponent("Quel est le RTO de CoreNova ?")}`, "/api/ask");
    await shot(page, "capture_assistant_abstention");
    await context.close();
  }

  // Ingénieur DSI : même question, réponse autorisée
  {
    const { context, page } = await session(browser, "ingenieur.dsi");
    await go(page, `/ask/${encodeURIComponent("Quel est le RTO de CoreNova ?")}`, "/api/ask");
    await shot(page, "capture_assistant_acces_dsi");
    await context.close();
  }

  // Responsable conformité : recherche d'experts
  {
    const { context, page } = await session(browser, "manager.conformite");
    await go(page, `/experts/${encodeURIComponent("lutte anti-blanchiment")}`, "/api/experts");
    await shot(page, "capture_experts");
    await context.close();
  }

  // Téléphone et mode sombre
  {
    const { context, page } = await session(browser, "collaborateur", { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await go(page, `/ask/${encodeURIComponent("Qui est responsable de Sentinel ?")}`, "/api/ask");
    await shot(page, "capture_mobile");
    await context.close();
  }
  {
    const { context, page } = await session(browser, "admin", { colorScheme: "dark" });
    await go(page, `/ask/${encodeURIComponent("Qui sont les experts en lutte anti-blanchiment ?")}`, "/api/ask");
    await shot(page, "capture_assistant_sombre");
    await context.close();
  }

  await browser.close();
  console.log(problems.length ? `PROBLÈMES (${problems.length}) :\n${problems.join("\n")}` : "Aucune erreur de console ni violation CSP.");
})();
