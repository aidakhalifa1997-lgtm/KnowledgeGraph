// Génère la présentation de soutenance (PPTX) à partir des figures et captures réelles du projet.
// Usage (depuis ce dossier) : NODE_PATH=<node_modules contenant pptxgenjs, react-icons, react,
// react-dom, sharp> node build_presentation.cjs <chemin/vers/apply_theme.js>
// Tous les chiffres proviennent de RAG/CODE/evaluation/results/RESULTATS.md (configuration gelée).
"use strict";
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const APPLY_THEME = process.argv[2];
const ROOT = path.resolve(__dirname, "..");
const FIG = (name) => path.join(ROOT, "figures", name);
const CAP = (name) => path.join(ROOT, "figures", "captures", name);
const OUT = path.join(ROOT, "Presentation_PFE_Knowledge_Graph_LLM.pptx");

const THEME = {
  name: "Orizia Encre et Cuivre",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1D2B3A", lt1: "FFFFFF", dk2: "45576A", lt2: "EEF2F5",
    accent1: "C2643B", accent2: "2E7D7A", accent3: "8A9BAE", accent4: "D9A441",
    accent5: "5B7FA6", accent6: "B23A48", hlink: "2E7D7A", folHlink: "5B7FA6",
  },
};
const HEX = THEME.colors;
const W = 13.333;
const MX = 0.6;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Plateforme de gestion des connaissances fondée sur un Knowledge Graph enrichi par un LLM";
pres.subject = "Soutenance de projet de fin d'études, Master Data Engineering";
pres.author = "[Prénom NOM — à compléter]";
const C = pres.SchemeColor;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "TITRE",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 1.7, w: 8.2, h: 2.2, fontFace: THEME.headFontFace,
      fontSize: 38, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 4.05, w: 8.2, h: 1.1, fontSize: 18,
      color: C.background2, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "info", type: "body", x: MX, y: 6.1, w: 9.5, h: 0.8, fontSize: 13,
      color: C.accent3, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENU",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.32, w: W - 2 * MX, h: 0.85, fontFace: THEME.headFontFace,
      fontSize: 30, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "Knowledge Graph et LLM pour la gestion des connaissances — PFE Master Data Engineering",
      options: { x: MX, y: 7.05, w: 9, h: 0.3, fontSize: 10, color: C.accent3, margin: 0 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent3, align: "right" },
});

// ------------------------------------------------------------------ outils
async function icon(Comp, color = "FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
async function iconCircle(slide, Comp, x, y, d, fill, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: name + " cercle" });
  const pad = d * 0.25;
  slide.addImage({ data: await icon(Comp), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name + " icône",
    altText: name });
}
function text(slide, value, opts) {
  slide.addText(value, { isTextBox: true, fontSize: 15, color: C.text1, margin: 0, valign: "top", ...opts });
}
function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill },
    objectName: name });
}
function source(slide, value, y = 6.62) {
  text(slide, value, { x: MX, y, w: W - 2 * MX, h: 0.3, fontSize: 10, color: C.text2, italic: true });
}
function image(slide, file, x, y, w, h, name) {
  const src = file.startsWith("image/") ? { data: file } : { path: file };
  slide.addImage({ ...src, x, y, w, h, objectName: name, altText: name });
}
// Zone « réponse » des captures de l'assistant (pixels de l'image 2160 × 1350) : agrandie pour rester lisible.
const ANSWER = { left: 385, top: 765, width: 945, height: 585 };
async function cropped(file, region = ANSWER) {
  const png = await sharp(file).extract(region).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
function frame(slide, file, x, y, w, h, name) {
  slide.addShape(pres.shapes.RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, fill: { color: C.background1 },
    line: { color: C.accent3, width: 0.75 }, shadow: { type: "outer", color: "1D2B3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 },
    objectName: name + " cadre" });
  image(slide, file, x, y, w, h, name);
}
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", legendFontFace: "+mn-lt", catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.dk2,
  dataLabelColor: HEX.dk1, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 12, titleFontSize: 14,
  titleColor: HEX.dk1, legendFontSize: 12, legendColor: HEX.dk2 };
function grid() { return { color: "D5DCE3", size: 0.5 }; }

let section = "";
function slideFor(master, sectionTitle) {
  if (sectionTitle !== section) { pres.addSection({ title: sectionTitle }); section = sectionTitle; }
  return pres.addSlide({ masterName: master, sectionTitle });
}

// ------------------------------------------------------------------ diapositives
async function build() {
  // 1. Titre ----------------------------------------------------------------
  let s = slideFor("TITRE", "Introduction");
  s.addText("Une plateforme de gestion des connaissances fondée sur un Knowledge Graph enrichi par un LLM",
    { placeholder: "title" });
  s.addText("Conception, développement et évaluation d'une architecture hybride RAG / GraphRAG pour un contexte bancaire",
    { placeholder: "body" });
  s.addText("Projet de fin d'études — Master Data Engineering · [Prénom NOM — à compléter] · Année universitaire 2025–2026",
    { placeholder: "info" });
  // Motif : petit graphe de connaissances
  const nodes = [[10.3, 1.6, 0.55, C.accent1], [11.9, 2.3, 0.42, C.accent2], [10.9, 3.4, 0.7, C.accent2],
    [12.2, 4.2, 0.38, C.accent4], [9.6, 4.5, 0.45, C.accent3], [11.2, 5.2, 0.5, C.accent1]];
  const links = [[0, 2], [1, 2], [2, 3], [2, 4], [2, 5], [0, 1], [4, 5]];
  for (const [a, b] of links) {
    const [x1, y1, d1] = nodes[a]; const [x2, y2, d2] = nodes[b];
    const ax = x1 + d1 / 2; const ay = y1 + d1 / 2; const bx = x2 + d2 / 2; const by = y2 + d2 / 2;
    s.addShape(pres.shapes.LINE, { x: Math.min(ax, bx), y: Math.min(ay, by), w: Math.abs(bx - ax) || 0.01,
      h: Math.abs(by - ay) || 0.01, flipH: (bx - ax) * (by - ay) < 0, line: { color: C.accent3, width: 1.25 },
      objectName: "motif lien" });
  }
  nodes.forEach(([x, y, d, col], i) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: col },
    line: { color: C.background1, width: 1.5 }, objectName: "motif nœud " + i }));
  s.addNotes("Bonjour. Je présente mon projet de fin d'études : une plateforme qui permet d'interroger la documentation " +
    "interne d'une banque en langage naturel, avec des réponses citées et conformes aux droits d'accès. Mon profil est " +
    "double : consultante en organisation dans une banque, où je rédige des procédures, et étudiante en Data Engineering. " +
    "Ce projet est né de cette double pratique. Toutes les données utilisées sont synthétiques : la banque « Orizia » est fictive.");

  // 2. Contexte ---------------------------------------------------------------
  s = slideFor("CONTENU", "Introduction");
  s.addText("Une connaissance écrite, mais difficile à mobiliser", { placeholder: "title" });
  const pains = [
    [fa.FaSitemap, "Dispersion", "Les dépendances de CoreNova sont réparties entre un compte rendu, une note d'architecture et une cartographie"],
    [fa.FaCodeBranch, "Versions", "La procédure KYC existe en version 1.0 (revue à 24 mois) et 2.0 (12 mois)"],
    [fa.FaExclamationTriangle, "Contradictions", "Le guide de l'outil Sentinel KYC indique encore 24 mois"],
    [fa.FaLock, "Diffusion restreinte", "Le plan de continuité n'est diffusé qu'à trois directions"],
    [fa.FaCopy, "Doublons", "Copies exactes et copies de travail coexistent avec l'original"],
    [fa.FaUserTie, "Expertise", "Savoir qui maîtrise la lutte anti-blanchiment est aussi utile que le texte"],
  ];
  for (let i = 0; i < pains.length; i += 1) {
    const col = i % 3; const row = Math.floor(i / 3);
    const x = MX + col * 4.1; const y = 1.55 + row * 2.45;
    card(s, x, y, 3.85, 2.2, "carte " + pains[i][1]);
    await iconCircle(s, pains[i][0], x + 0.3, y + 0.3, 0.7, i === 2 ? C.accent1 : C.accent2, pains[i][1]);
    text(s, pains[i][1], { x: x + 1.15, y: y + 0.35, w: 2.5, h: 0.6, fontSize: 19, bold: true, valign: "middle" });
    text(s, pains[i][2], { x: x + 0.3, y: y + 1.12, w: 3.3, h: 0.95, fontSize: 14, color: C.text2 });
  }
  s.addNotes("Dans une banque, la connaissance est largement écrite : procédures, comptes rendus, chartes, guides, rapports " +
    "d'audit. Le problème n'est pas l'absence d'information, c'est sa mobilisation. Six difficultés, toutes présentes dans " +
    "mon corpus : la dispersion, les versions, les contradictions, la diffusion restreinte, les doublons, et la question de " +
    "savoir qui sait. Dans un établissement contrôlé, s'ajoutent la traçabilité et le respect des habilitations.");

  // 3. Problématique ------------------------------------------------------------
  s = slideFor("CONTENU", "Introduction");
  s.addText("Problématique et questions de recherche", { placeholder: "title" });
  card(s, MX, 1.5, 4.6, 4.95, "encadré problématique", C.text1);
  text(s, "Comment permettre à un collaborateur d'interroger la documentation interne d'une banque en langage naturel, en " +
    "obtenant des réponses exactes, sourcées et conformes à ses droits, y compris lorsque la réponse relie plusieurs " +
    "documents, entités et versions ?", { x: MX + 0.35, y: 1.85, w: 3.9, h: 4.3, fontSize: 19, color: C.background1,
    fontFace: THEME.headFontFace, italic: true });
  const qr = [
    ["QR1", "Le graphe améliore-t-il la recherche pour les questions relationnelles et multi-sauts ?"],
    ["QR2", "Le graphe dégrade-t-il les questions factuelles simples ?"],
    ["QR3", "Le contrôle de suffisance permet-il de s'abstenir à bon escient ?"],
    ["QR4", "Des preuves typées trouvent-elles mieux les experts qu'un comptage de mentions ?"],
    ["QR5", "Contenu + graphe recommandent-ils mieux que le contenu seul ?"],
  ];
  qr.forEach(([id, q], i) => {
    const y = 1.5 + i * 1.0;
    s.addShape(pres.shapes.OVAL, { x: 5.6, y: y + 0.1, w: 0.7, h: 0.7, fill: { color: C.accent1 }, line: { color: C.accent1 },
      objectName: id + " pastille" });
    text(s, id, { x: 5.6, y: y + 0.1, w: 0.7, h: 0.7, fontSize: 14, bold: true, color: C.background1, align: "center",
      valign: "middle" });
    text(s, q, { x: 6.55, y: y + 0.05, w: 6.15, h: 0.8, fontSize: 16, valign: "middle" });
  });
  s.addNotes("Ma problématique : comment interroger la documentation en langage naturel avec des réponses exactes, sourcées " +
    "et conformes aux droits, y compris quand la réponse relie plusieurs documents. J'en ai tiré cinq questions de " +
    "recherche, chacune associée à une hypothèse testable : l'apport du graphe sur les questions relationnelles, " +
    "l'absence de dégradation du factuel, l'abstention, la recherche d'experts et les recommandations.");

  // 4. Démarche ---------------------------------------------------------------------
  s = slideFor("CONTENU", "Introduction");
  s.addText("Démarche : un banc d'essai bancaire synthétique", { placeholder: "title" });
  const stats = [["35", "documents d'une banque fictive"], ["66", "questions annotées, 10 catégories"],
    ["5", "architectures comparées"], ["0", "donnée réelle d'entreprise"]];
  stats.forEach(([v, l], i) => {
    const x = MX + (i % 2) * 3.05; const y = 1.55 + Math.floor(i / 2) * 2.45;
    card(s, x, y, 2.85, 2.2, "statistique " + l);
    text(s, v, { x: x + 0.25, y: y + 0.2, w: 2.4, h: 1.1, fontSize: 54, bold: true, color: i === 3 ? C.accent2 : C.accent1,
      fontFace: THEME.headFontFace, valign: "middle" });
    text(s, l, { x: x + 0.25, y: y + 1.35, w: 2.4, h: 0.7, fontSize: 14, color: C.text2 });
  });
  text(s, "Des pièges intégrés volontairement", { x: 7.1, y: 1.55, w: 5.6, h: 0.5, fontSize: 20, bold: true });
  const traps = [[fa.FaCodeBranch, "Versions successives d'une même procédure"],
    [fa.FaBalanceScale, "Valeurs contradictoires : 12 ou 24 mois, 33 ou 40 %"],
    [fa.FaCopy, "Doublon exact et copie de travail"], [fa.FaFileImage, "Note de service scannée, lue par OCR"],
    [fa.FaLock, "Cinq documents à diffusion restreinte"], [fa.FaBug, "Mémo contenant une injection de prompt"]];
  for (let i = 0; i < traps.length; i += 1) {
    const y = 2.2 + i * 0.72;
    await iconCircle(s, traps[i][0], 7.1, y, 0.5, i === 5 ? C.accent6 : C.accent2, traps[i][1]);
    text(s, traps[i][1], { x: 7.8, y, w: 4.9, h: 0.5, fontSize: 15, valign: "middle" });
  }
  s.addNotes("Les documents réels d'une banque ne peuvent pas sortir de l'établissement. J'ai donc rédigé un corpus de 35 " +
    "documents d'une banque fictive, en y intégrant les difficultés que je rencontre dans mon métier : versions, " +
    "contradictions, doublons, document scanné, diffusion restreinte et un mémo piégé. J'ai annoté 66 questions en dix " +
    "catégories, avec les documents justificatifs et les réponses attendues, puis comparé cinq architectures.");

  // 5. Architecture ---------------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Architecture : six couches, un LLM optionnel", { placeholder: "title" });
  frame(s, FIG("schema_architecture.png"), MX, 1.45, 7.6, 7.6 / 1.51, "schéma d'architecture");
  const archPoints = [[fa.FaPlug, "LLM optionnel", "Sans clé, tout fonctionne hors-ligne : règles d'extraction et générateur extractif"],
    [fa.FaDatabase, "Une seule base", "Neo4j porte le graphe, l'index vectoriel et l'index plein texte"],
    [fa.FaShieldAlt, "Droits dès le départ", "Documents autorisés calculés avant toute recherche"]];
  for (let i = 0; i < archPoints.length; i += 1) {
    const y = 1.55 + i * 1.65;
    await iconCircle(s, archPoints[i][0], 8.65, y, 0.62, i === 0 ? C.accent1 : C.accent2, archPoints[i][1]);
    text(s, archPoints[i][1], { x: 9.45, y, w: 3.3, h: 0.45, fontSize: 18, bold: true });
    text(s, archPoints[i][2], { x: 9.45, y: y + 0.45, w: 3.3, h: 1.05, fontSize: 14, color: C.text2 });
  }
  s.addNotes("L'architecture comporte six couches : documents, connaissances, recherche, services métier, API et interface. " +
    "Trois choix structurants. Premièrement, le LLM est un maillon optionnel : la plateforme fonctionne et se mesure sans " +
    "lui. Deuxièmement, une seule base, Neo4j, porte le graphe, les vecteurs et le plein texte. Troisièmement, le contrôle " +
    "d'accès n'est pas une couche ajoutée à la fin : il est appliqué avant toute recherche.");

  // 6. Du document au graphe ---------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Du document au graphe, avec la provenance de chaque fait", { placeholder: "title" });
  frame(s, FIG("schema_pipeline_ingestion.png"), MX, 1.45, 8.3, 8.3 / 2.5, "pipeline d'ingestion");
  card(s, MX, 5.05, 8.3, 1.45, "exemple de provenance", C.background2);
  text(s, [
    { text: "AML Watch  →  dépend de  →  CoreNova", options: { bold: true, fontSize: 16, breakLine: true } },
    { text: "un seul fait, trois documents, trois citations exactes, extracteur et confiance pour chaque preuve : retirer " +
      "un document retire les faits qu'il était seul à justifier", options: { fontSize: 14, color: C.text2 } },
  ], { x: MX + 0.3, y: 5.2, w: 7.7, h: 1.2 });
  const ing = [["31", "documents actifs"], ["1 + 2", "version remplacée, doublons"], ["1", "quarantaine (injection)"],
    ["18,45 s", "ingestion complète"], ["0,38 s", "relance sans changement"]];
  ing.forEach(([v, l], i) => {
    const y = 1.45 + i * 1.02;
    text(s, v, { x: 9.3, y, w: 1.75, h: 0.85, fontSize: 26, bold: true, color: i === 2 ? C.accent6 : C.accent1,
      fontFace: THEME.headFontFace, valign: "middle" });
    text(s, l, { x: 11.1, y, w: 1.65, h: 0.85, fontSize: 13, color: C.text2, valign: "middle" });
  });
  s.addNotes("L'ingestion est volontairement prudente. Chaque fichier est contrôlé, lu, au besoin par OCR, nettoyé ; le " +
    "cartouche est lu, y compris la diffusion, qui alimente directement le contrôle d'accès. Les doublons sont détectés par " +
    "empreinte et par MinHash, et un document contenant des instructions pour un assistant est mis en quarantaine. Dans le " +
    "graphe, chaque fait garde ses preuves : par exemple, la dépendance d'AML Watch à CoreNova est confirmée par trois " +
    "documents. L'ingestion est idempotente : la relancer sans changement prend 0,38 seconde.");

  // 7. Recherche ------------------------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Trois sources de preuves, fusionnées et routées", { placeholder: "title" });
  const srcs = [[fa.FaFont, "BM25", "mots exacts : sigles, références, valeurs"],
    [fa.FaProjectDiagram, "Vecteurs", "sens proche, paraphrases (WordLlama)"],
    [fa.FaSitemap, "Graphe", "entités de la question, voisinage à 2 sauts, PageRank personnalisé"]];
  for (let i = 0; i < srcs.length; i += 1) {
    const y = 1.55 + i * 1.6;
    card(s, MX, y, 4.3, 1.35, "source " + srcs[i][1]);
    await iconCircle(s, srcs[i][0], MX + 0.25, y + 0.3, 0.75, i === 2 ? C.accent1 : C.accent2, srcs[i][1]);
    text(s, srcs[i][1], { x: MX + 1.25, y: y + 0.15, w: 2.9, h: 0.45, fontSize: 18, bold: true });
    text(s, srcs[i][2], { x: MX + 1.25, y: y + 0.6, w: 2.9, h: 0.65, fontSize: 13, color: C.text2 });
  }
  s.addShape(pres.shapes.RIGHT_ARROW, { x: 5.15, y: 3.35, w: 0.8, h: 0.6, fill: { color: C.accent3 }, line: { color: C.accent3 },
    objectName: "flèche vers la fusion" });
  card(s, 6.15, 2.55, 2.2, 2.2, "fusion RRF", C.text1);
  text(s, [{ text: "Fusion RRF", options: { bold: true, fontSize: 18, breakLine: true } },
    { text: "rangs seuls, k = 60", options: { fontSize: 13 } }], { x: 6.3, y: 3.0, w: 1.9, h: 1.3, color: C.background1,
    align: "center", valign: "middle" });
  text(s, "Routage selon le type de question", { x: 8.75, y: 1.55, w: 4.0, h: 0.45, fontSize: 17, bold: true });
  s.addTable([
    [{ text: "Type", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk1 } } },
      { text: "Poids du graphe", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk1 } } },
      { text: "Sauts", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk1 } } }],
    ["factuelle", "0,5", "1"], ["relationnelle", "1,0", "2"], ["multi-sauts", "1,5", "2"], ["expertise", "1,0", "1"],
    ["ambiguë", "1,0", "2"],
  ], { x: 8.75, y: 2.1, w: 4.0, colW: [1.7, 1.45, 0.85], fontSize: 14, fontFace: "Calibri", color: HEX.dk1,
    border: { type: "solid", pt: 0.5, color: "C9D2DB" }, rowH: 0.42, objectName: "table de routage" });
  text(s, "Le graphe seul est excellent sur le relationnel mais dégrade le factuel : le routage dose son poids.",
    { x: 8.75, y: 4.85, w: 4.0, h: 1.2, fontSize: 14, color: C.text2, italic: true });
  s.addNotes("La recherche combine trois sources aux forces différentes : BM25 pour les termes exacts, les vecteurs pour le " +
    "sens, et le graphe pour les relations, avec un PageRank personnalisé à partir des entités de la question, à la manière " +
    "de HippoRAG. Les scores ne sont pas comparables, donc la fusion n'utilise que les rangs : c'est la Reciprocal Rank " +
    "Fusion. Le poids du graphe dépend du type de question, détecté de façon déterministe.");

  // 8. Workflow ---------------------------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Un workflow qui vérifie avant et après la génération", { placeholder: "title" });
  frame(s, FIG("schema_workflow.png"), MX, 1.5, 7.9, 7.9 / 2.11, "workflow LangGraph");
  text(s, "LangGraph comme automate à états : le LLM, s'il est configuré, n'intervient que dans la génération et ne choisit " +
    "jamais l'étape suivante.", { x: MX, y: 5.5, w: 7.9, h: 0.9, fontSize: 14, color: C.text2, italic: true });
  const wf = [[fa.FaSearchPlus, "Suffisance", "couverture des termes pondérée par l'IDF (seuil 0,55), entités, valeur chiffrée"],
    [fa.FaRedo, "Une relance au plus", "graines et termes enrichis, puis génération ou abstention"],
    [fa.FaCheckDouble, "Vérification", "citations réelles, phrases appuyées, liens et HTML retirés"]];
  for (let i = 0; i < wf.length; i += 1) {
    const y = 1.55 + i * 1.6;
    await iconCircle(s, wf[i][0], 8.95, y, 0.62, i === 2 ? C.accent1 : C.accent2, wf[i][1]);
    text(s, wf[i][1], { x: 9.75, y, w: 3.0, h: 0.45, fontSize: 17, bold: true });
    text(s, wf[i][2], { x: 9.75, y: y + 0.45, w: 3.0, h: 1.05, fontSize: 13, color: C.text2 });
  }
  s.addNotes("Le workflow est un graphe d'états explicite : analyse, recherche, contrôle de suffisance, relance au plus une " +
    "fois, génération, vérification, ou abstention. Le contrôle de suffisance s'inspire des approches correctives : avant " +
    "de répondre, on vérifie que le contexte couvre la question, y compris la présence d'une valeur chiffrée quand on " +
    "demande un délai. Après la génération, on vérifie les citations et on assainit la réponse. Sans clé, le générateur est " +
    "extractif : il ne peut pas inventer.");

  // 9. Sécurité --------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Sécurité : filtrer avant de chercher", { placeholder: "title" });
  const cw = 5.85; const ch = cw * ANSWER.height / ANSWER.width;
  frame(s, await cropped(CAP("capture_assistant_abstention.png")), MX, 1.45, cw, ch, "capture abstention collaborateur");
  frame(s, await cropped(CAP("capture_assistant_acces_dsi.png")), MX + cw + 0.3, 1.45, cw, ch, "capture réponse ingénieur DSI");
  text(s, [{ text: "Compte « collaborateur » : ", options: { bold: true } },
    { text: "abstention, sans révéler l'existence du plan de continuité" }], { x: MX, y: 1.6 + ch, w: cw, h: 0.55, fontSize: 14 });
  text(s, [{ text: "Compte « ingenieur.dsi » : ", options: { bold: true } }, { text: "« RTO : 4 heures », avec sa source" }],
    { x: MX + cw + 0.3, y: 1.6 + ch, w: cw, h: 0.55, fontSize: 14 });
  card(s, MX, 6.05, W - 2 * MX, 0.6, "bandeau sécurité", C.background2);
  text(s, "0 fuite sur 990 réponses rejouées avec 3 comptes restreints · mémo piégé en quarantaine · diffusion absente = refus",
    { x: MX + 0.25, y: 6.05, w: W - 2 * MX - 0.5, h: 0.6, fontSize: 15, bold: true, color: C.accent2, valign: "middle" });
  s.addNotes("La même question, « Quel est le RTO de CoreNova ? », donne deux résultats selon le compte. Le collaborateur " +
    "n'est pas destinataire du plan de continuité : la plateforme s'abstient, sans même révéler que le document existe. " +
    "L'ingénieur de la DSI obtient la valeur et sa source. C'est possible parce que la liste des documents autorisés est " +
    "calculée avant la recherche et passée à chaque requête. Un audit dédié rejoue les 66 questions avec trois comptes " +
    "restreints et les cinq architectures : 990 réponses, aucune fuite. Et un document dont la diffusion n'est pas déclarée " +
    "est refusé par défaut.");

  // 10. Démonstration ---------------------------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Démonstration : relations citées et contradictions signalées", { placeholder: "title" });
  frame(s, await cropped(CAP("capture_assistant_relationnel.png")), MX, 1.45, cw, ch, "capture question relationnelle");
  frame(s, await cropped(CAP("capture_assistant_contradiction.png")), MX + cw + 0.3, 1.45, cw, ch, "capture contradiction");
  text(s, [{ text: "« Quelles applications dépendent de CoreNova ? » ", options: { bold: true } },
    { text: "faits du graphe [F] et passages [C], tous cliquables" }], { x: MX, y: 1.6 + ch, w: cw, h: 0.8, fontSize: 14 });
  text(s, [{ text: "Revue des clients à risque élevé : ", options: { bold: true } },
    { text: "12 mois selon la procédure en vigueur ; l'outil et l'ancienne version disent 24 mois" }],
    { x: MX + cw + 0.3, y: 1.6 + ch, w: cw, h: 0.8, fontSize: 14 });
  s.addNotes("Deux exemples de réponses réelles. À gauche, une question relationnelle : les faits viennent du graphe, les " +
    "extraits des documents, et chaque marqueur renvoie à sa preuve. À droite, la plateforme répond 12 mois selon la " +
    "procédure en vigueur, mais signale que la version 1.0, le guide de l'outil Sentinel KYC, le rapport d'audit et un " +
    "compte rendu indiquent 24 mois. Pour un auditeur, c'est un constat : l'outil n'a pas été mis à jour. " +
    "Si le temps le permet, je fais la démonstration en direct.");

  // 11. Explorer, experts, recommandations -------------------------------------------------------------
  s = slideFor("CONTENU", "La solution");
  s.addText("Explorer le graphe, trouver les experts, recommander", { placeholder: "title" });
  const tw = 3.85; const th = tw / 1.6;
  [["capture_explorateur.png", "Explorateur", "voisinage de CoreNova, filtré par les droits"],
    ["capture_experts.png", "Experts", "classement justifié par des preuves typées (rôle manager)"],
    ["capture_recommandations.png", "Recommandations", "documents liés à la procédure KYC v2, avec leurs raisons"]]
    .forEach(([f, t, d], i) => {
      const x = MX + i * (tw + 0.3);
      frame(s, CAP(f), x, 1.55, tw, th, "capture " + t);
      text(s, t, { x, y: 1.75 + th, w: tw, h: 0.45, fontSize: 18, bold: true });
      text(s, d, { x, y: 2.2 + th, w: tw, h: 0.75, fontSize: 14, color: C.text2 });
    });
  text(s, "Interface React + Cytoscape.js, politique de sécurité du contenu stricte ; aucune page n'accède directement à la base.",
    { x: MX, y: 5.75, w: W - 2 * MX, h: 0.5, fontSize: 14, italic: true, color: C.text2 });
  s.addNotes("Au-delà de l'assistant, trois fonctions. L'explorateur affiche le graphe autour d'une entité, avec les mêmes " +
    "règles de visibilité. La recherche d'experts classe les personnes selon des preuves typées : expertise déclarée, " +
    "pilotage de projet, responsabilité applicative ; elle est réservée aux managers et chaque rang est justifié. Les " +
    "recommandations combinent similarité de contenu, entités partagées et proximité dans le graphe.");

  // 12. Protocole --------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Un protocole conçu contre le sur-ajustement", { placeholder: "title" });
  const steps = [["1", "Partition des documents", "règles mises au point sur D01–D20, testées sur D21–D35"],
    ["2", "Questions séparées", "17 de développement, 49 jamais inspectées avant la campagne"],
    ["3", "Configuration gelée", "puis campagne principale ; workflow identique pour les 5 architectures"],
    ["4", "Journal post-gel", "toute modification ultérieure tracée et mesurée à part"]];
  steps.forEach(([n, t, d], i) => {
    const x = MX + i * 3.08;
    s.addShape(pres.shapes.OVAL, { x: x + 1.05, y: 1.55, w: 0.9, h: 0.9, fill: { color: C.accent1 }, line: { color: C.accent1 },
      objectName: "étape " + n });
    text(s, n, { x: x + 1.05, y: 1.55, w: 0.9, h: 0.9, fontSize: 24, bold: true, color: C.background1, align: "center",
      valign: "middle", fontFace: THEME.headFontFace });
    if (i < 3) {
      s.addShape(pres.shapes.LINE, { x: x + 2.05, y: 2.0, w: 2.0, h: 0, line: { color: C.accent3, width: 1.5, dashType: "dash" },
        objectName: "liaison " + n });
    }
    text(s, t, { x: x + 0.1, y: 2.65, w: 2.8, h: 0.5, fontSize: 17, bold: true, align: "center" });
    text(s, d, { x: x + 0.1, y: 3.15, w: 2.8, h: 1.1, fontSize: 14, color: C.text2, align: "center" });
  });
  card(s, MX, 4.55, W - 2 * MX, 1.85, "métriques", C.background2);
  text(s, [{ text: "Métriques : ", options: { bold: true } },
    { text: "Recall@5, MRR, nDCG@5 (pertinence graduée) pour la recherche ; exactitude par mots-clés, abstention, citations, " +
      "fuites pour les réponses ; P@1, nDCG@3 pour les experts ; nDCG@5 pour les recommandations.", options: { breakLine: true } },
    { text: "Statistiques : ", options: { bold: true } },
    { text: "intervalles de confiance à 95 % par bootstrap (2 000 tirages) et test exact des signes sur données appariées." }],
  { x: MX + 0.3, y: 4.7, w: W - 2 * MX - 0.6, h: 1.6, fontSize: 15, paraSpaceAfter: 6 });
  s.addNotes("Le principal risque, quand on écrit soi-même le corpus et le système, est de sur-ajuster. Quatre mesures : " +
    "une partition des documents pour l'extraction, une séparation entre 17 questions de développement et 49 jamais " +
    "inspectées, un gel de la configuration avant la campagne, et un journal des modifications post-gel. Avec 66 questions, " +
    "j'accompagne chaque moyenne d'un intervalle de confiance et chaque comparaison d'un test apparié.");

  // 13. Résultats recherche ------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Recherche : la fusion routée en tête, BM25 très proche", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "nDCG@5", labels: ["Graphe seul", "Vectoriel", "Hybride", "Hybride + graphe (fixe)",
    "BM25", "Final routé"], values: [0.708, 0.720, 0.803, 0.813, 0.831, 0.839] }], {
    x: MX, y: 1.45, w: 7.4, h: 5.0, barDir: "bar", showTitle: true, title: "nDCG@5 moyen (55 questions)",
    chartColors: [HEX.accent3, HEX.accent3, HEX.accent3, HEX.accent3, HEX.accent2, HEX.accent1], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", valAxisMinVal: 0.5, valAxisMaxVal: 0.9,
    valAxisLabelFormatCode: "0.0", valGridLine: grid(), catGridLine: { style: "none" }, showLegend: false,
    barGapWidthPct: 45, ...chartText, objectName: "graphique nDCG par stratégie" });
  const rs = [["0,839", "nDCG@5 du final [0,78 ; 0,90]", C.accent1], ["0,409 → 0,720", "vectoriel : spaCy → WordLlama", C.accent2],
    ["0,96 / 0,52", "graphe seul : relationnel / factuel", C.accent2]];
  rs.forEach(([v, l, col], i) => {
    const y = 1.5 + i * 1.6;
    text(s, v, { x: 8.4, y, w: 4.3, h: 0.75, fontSize: 30, bold: true, color: col, fontFace: THEME.headFontFace });
    text(s, l, { x: 8.4, y: y + 0.75, w: 4.3, h: 0.6, fontSize: 14, color: C.text2 });
  });
  source(s, "Source : evaluation/results/RESULTATS.md — configuration gelée, encodeur WordLlama ; écart final − BM25 non significatif.");
  s.addNotes("En recherche documentaire, l'architecture finale obtient le meilleur nDCG@5, 0,839, mais BM25 est très proche " +
    "et l'écart n'est pas significatif : BM25 est une référence très forte sur des questions riches en termes exacts. " +
    "L'ablation de l'encodeur montre que l'intérêt de l'hybride dépend de la qualité des vecteurs : avec spaCy, le " +
    "vectoriel tombe à 0,409. Le graphe seul est excellent sur le relationnel, 0,96, mais mauvais sur le factuel, 0,52.");

  // 14. Résultats réponses ----------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Réponses : le graphe change la donne sur les relations", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Exactitude", labels: ["GraphRAG", "RAG hybride", "RAG vectoriel", "Final routé",
    "Hybride + graphe (fixe)"], values: [0.515, 0.606, 0.651, 0.742, 0.773] }], {
    x: MX, y: 1.45, w: 6.0, h: 4.95, barDir: "bar", showTitle: true, title: "Exactitude de bout en bout (66 questions)",
    chartColors: [HEX.accent3, HEX.accent3, HEX.accent3, HEX.accent1, HEX.accent2], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.000", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0", valGridLine: grid(),
    catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 45, ...chartText,
    objectName: "graphique exactitude par architecture" });
  s.addChart(pres.charts.BAR, [
    { name: "RAG vectoriel", labels: ["Factuelles", "Relationnelles", "Multi-sauts"], values: [0.92, 0.12, 0.30] },
    { name: "Final routé", labels: ["Factuelles", "Relationnelles", "Multi-sauts"], values: [0.92, 0.62, 0.60] }], {
    x: 6.85, y: 1.45, w: 5.85, h: 3.6, barDir: "col", barGrouping: "clustered", showTitle: true,
    title: "Exactitude par catégorie", chartColors: [HEX.accent3, HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0.0", valGridLine: grid(),
    catGridLine: { style: "none" }, showLegend: true, legendPos: "b", ...chartText, objectName: "graphique par catégorie" });
  card(s, 6.85, 5.2, 5.85, 1.2, "encadré sur-ajustement", C.background2);
  text(s, [{ text: "0,882 ", options: { bold: true, color: C.text2 } }, { text: "sur les questions de développement, " },
    { text: "0,694 ", options: { bold: true, color: C.accent1 } }, { text: "sur les questions jamais inspectées : c'est le chiffre honnête." }],
  { x: 7.1, y: 5.3, w: 5.4, h: 1.0, fontSize: 15, valign: "middle" });
  source(s, "Source : RESULTATS.md — générateur extractif hors-ligne ; final [0,64 ; 0,85] ; final − RAG hybride : p = 0,02 ; final − fixe : p = 0,5.");
  s.addNotes("En réponses de bout en bout, les architectures avec graphe dominent. L'architecture finale atteint 0,742, et " +
    "l'hybride à graphe fixe 0,773, un écart de deux questions qui n'est pas significatif. L'effet du graphe est net là où " +
    "on l'attendait : sur les questions relationnelles, on passe de 0,12 à 0,62, sur les multi-sauts de 0,30 à 0,60, sans " +
    "perte sur le factuel. Le chiffre que je retiens est 0,694, sur les questions jamais inspectées : l'écart avec 0,882 " +
    "mesure le sur-ajustement de mes heuristiques.");

  // 15. Fiabilité -------------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Fiabilité : aucune invention, mais trop d'abstentions", { placeholder: "title" });
  const fiab = [["0", "citation inventée"], ["0", "fuite d'accès"], ["0", "chaîne interdite"]];
  fiab.forEach(([v, l], i) => {
    const x = MX + i * 2.0;
    card(s, x, 1.55, 1.8, 1.9, "fiabilité " + l);
    text(s, v, { x, y: 1.7, w: 1.8, h: 0.95, fontSize: 48, bold: true, color: C.accent2, align: "center",
      fontFace: THEME.headFontFace, valign: "middle" });
    text(s, l, { x: x + 0.1, y: 2.7, w: 1.6, h: 0.6, fontSize: 14, color: C.text2, align: "center" });
  });
  text(s, [{ text: "Abstention (final) : ", options: { bold: true } }, { text: "rappel 0,909 (10 sur 11), précision 0,5, " },
    { text: "18 % d'abstentions abusives", options: { bold: true, color: C.accent6 } },
    { text: " : le contrôle lexical est sensible aux paraphrases." }], { x: MX, y: 3.8, w: 5.8, h: 1.3, fontSize: 15 });
  text(s, "Le seuil règle un compromis métier : coût d'une réponse fausse contre coût d'une non-réponse.",
    { x: MX, y: 5.2, w: 5.8, h: 0.9, fontSize: 14, italic: true, color: C.text2 });
  s.addChart(pres.charts.LINE, [
    { name: "Rappel d'abstention", labels: ["0,35", "0,45", "0,55", "0,65", "0,75"], values: [0.727, 0.818, 0.909, 1.0, 1.0] },
    { name: "Abstention abusive", labels: ["0,35", "0,45", "0,55", "0,65", "0,75"], values: [0.127, 0.164, 0.182, 0.218, 0.327] }], {
    x: 6.75, y: 1.45, w: 5.95, h: 4.95, showTitle: true, title: "Sensibilité au seuil de suffisance (0,55 fixé a priori)",
    chartColors: [HEX.accent2, HEX.accent6], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 8, showValue: true,
    dataLabelPosition: "t", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1.1, valAxisLabelFormatCode: "0.0",
    valGridLine: grid(), catGridLine: { style: "none" }, showLegend: true, legendPos: "b", ...chartText,
    objectName: "graphique sensibilité au seuil" });
  source(s, "Source : RESULTATS.md — sections 5 et 6 ; vérification des citations et filtrage des droits appliqués à toutes les architectures.");
  s.addNotes("La fiabilité est obtenue par construction : aucune citation inventée, aucune fuite, aucune chaîne interdite. " +
    "Le point faible est l'abstention : la plateforme détecte dix des onze questions sans réponse, mais s'abstient à tort " +
    "sur 18 % des questions qui en ont une, parce que le contrôle est lexical. Le graphique montre le compromis : monter " +
    "le seuil améliore le rappel d'abstention mais augmente les abstentions abusives. C'est une décision métier.");

  // 16. Experts et recommandations ------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Experts et recommandations : le graphe apporte la justification", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "nDCG@3", labels: ["Comptage de mentions", "Preuves typées"], values: [0.911, 0.975] }], {
    x: MX, y: 1.45, w: 5.9, h: 3.9, barDir: "col", showTitle: true, title: "Experts : nDCG@3 (15 domaines)",
    chartColors: [HEX.accent3, HEX.accent1], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
    valAxisMinVal: 0, valAxisMaxVal: 1.1, valAxisLabelFormatCode: "0.0", valGridLine: grid(), catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 70, ...chartText, objectName: "graphique experts" });
  s.addChart(pres.charts.BAR, [{ name: "nDCG@5", labels: ["Contenu seul", "Graphe", "Hybride"], values: [0.648, 0.877, 0.908] }], {
    x: 6.8, y: 1.45, w: 5.9, h: 3.9, barDir: "col", showTitle: true, title: "Recommandations : nDCG@5 (10 documents)",
    chartColors: [HEX.accent3, HEX.accent2, HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.000", valAxisMinVal: 0, valAxisMaxVal: 1.1, valAxisLabelFormatCode: "0.0", valGridLine: grid(),
    catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 60, ...chartText, objectName: "graphique recommandations" });
  text(s, [{ text: "H4 non démontrée : ", options: { bold: true } }, { text: "écart de +0,064, p = 0,375 ; l'apport tient aux preuves affichées." }],
    { x: MX, y: 5.5, w: 5.9, h: 0.9, fontSize: 15 });
  text(s, [{ text: "H5 validée : ", options: { bold: true } }, { text: "+0,261 sur le contenu seul, p = 0,004 ; aucun doublon recommandé." }],
    { x: 6.8, y: 5.5, w: 5.9, h: 0.9, fontSize: 15 });
  source(s, "Source : RESULTATS.md — sections 7 et 8 ; test exact des signes apparié.");
  s.addNotes("Pour les experts, le score fondé sur des preuves typées fait mieux que le comptage de mentions, mais l'écart " +
    "n'est pas significatif sur quinze domaines : l'hypothèse 4 n'est pas démontrée. Son intérêt est ailleurs : chaque " +
    "classement est justifié. Pour les recommandations, combiner contenu, entités partagées et graphe améliore nettement " +
    "le résultat : plus 0,26 de nDCG, significatif.");

  // 17. Hypothèses --------------------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Évaluation");
  s.addText("Bilan des hypothèses de recherche", { placeholder: "title" });
  const verdict = (t, col) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: col }, align: "center" } });
  const head = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk1 } } });
  s.addTable([
    [head("Hypothèse"), head("Constat mesuré"), head("Verdict")],
    ["H1 — le graphe aide le relationnel et le multi-sauts", "exactitude 0,12 → 0,62 et 0,30 → 0,60 ; en recherche, égal à l'hybride sur le relationnel",
      verdict("Partiellement", HEX.accent4)],
    ["H2 — pas de dégradation du factuel", "nDCG@5 0,99 et exactitude 0,92 grâce au routage", verdict("Validée", HEX.accent2)],
    ["H3 — abstention à bon escient", "rappel 0,909 mais 18 % d'abstentions abusives", verdict("Partiellement", HEX.accent4)],
    ["H4 — experts par preuves typées", "nDCG@3 0,975 contre 0,911, p = 0,375", verdict("Non démontrée", HEX.accent6)],
    ["H5 — recommandations hybrides", "nDCG@5 0,908 contre 0,648, p = 0,004", verdict("Validée", HEX.accent2)],
  ], { x: MX, y: 1.5, w: W - 2 * MX, colW: [4.2, 5.9, 2.03], fontSize: 15, fontFace: "Calibri", color: HEX.dk1,
    border: { type: "solid", pt: 0.5, color: "C9D2DB" }, rowH: 0.7, valign: "middle", objectName: "table des hypothèses" });
  text(s, "Menaces à la validité : corpus et questions conçus par la même personne, corpus synthétique et petit, " +
    "66 questions, mesures lexicales, encodeurs légers.", { x: MX, y: 6.15, w: W - 2 * MX, h: 0.55, fontSize: 14, italic: true,
    color: C.text2 });
  s.addNotes("En synthèse : deux hypothèses validées, l'absence de dégradation du factuel et les recommandations ; deux " +
    "partiellement validées, l'apport du graphe et l'abstention ; une non démontrée, les experts. Je rappelle les menaces " +
    "à la validité : biais de conception, corpus synthétique, petits effectifs. Je ne conclus que lorsque l'incertitude " +
    "le permet.");

  // 18. Gouvernance et déploiement ----------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Déploiement et conclusion");
  s.addText("Déployer en banque : une trajectoire et une gouvernance", { placeholder: "title" });
  const traj = [["Cadrage et homologation", "analyse de risques, sécurité, DPO"], ["Pilote", "un domaine, questions réelles annotées par les métiers"],
    ["Industrialisation", "SSO, supervision, sauvegardes automatisées"], ["Extension", "domaine par domaine, gouvernance en place"]];
  traj.forEach(([t, d], i) => {
    const x = MX + i * 3.08;
    s.addShape(pres.shapes.CHEVRON, { x, y: 1.55, w: 2.95, h: 0.95, fill: { color: i === 1 ? C.accent1 : C.accent2 },
      line: { color: i === 1 ? C.accent1 : C.accent2 }, objectName: "étape trajectoire " + (i + 1) });
    text(s, t, { x: x + 0.45, y: 1.55, w: 2.1, h: 0.95, fontSize: 14, bold: true, color: C.background1, valign: "middle",
      align: "center" });
    text(s, d, { x: x + 0.15, y: 2.65, w: 2.7, h: 0.8, fontSize: 13, color: C.text2, align: "center" });
  });
  const gov = [[fa.FaUserCog, "Gestionnaire des connaissances", "valide entités candidates et quarantaine"],
    [fa.FaClipboardCheck, "Contrôle par échantillonnage", "la conformité relit un échantillon de réponses"],
    [fa.FaUserShield, "Experts : finalité limitée", "orienter, jamais évaluer ; avis du DPO"],
    [fa.FaCloud, "Décision formelle sur le LLM", "classification des données, contrat, réévaluation"]];
  for (let i = 0; i < gov.length; i += 1) {
    const x = MX + (i % 2) * 6.1; const y = 3.75 + Math.floor(i / 2) * 1.35;
    await iconCircle(s, gov[i][0], x, y, 0.62, C.accent2, gov[i][1]);
    text(s, gov[i][1], { x: x + 0.8, y, w: 5.1, h: 0.42, fontSize: 16, bold: true });
    text(s, gov[i][2], { x: x + 0.8, y: y + 0.42, w: 5.1, h: 0.6, fontSize: 14, color: C.text2 });
  }
  s.addNotes("Pour un usage réel, je propose une trajectoire progressive : cadrage et homologation, puis un pilote sur un " +
    "domaine délimité, avec des questions réelles annotées par les métiers, ce qui reproduit mon protocole sur des " +
    "documents réels. Côté gouvernance, mon expérience d'organisation m'a conduite à proposer un gestionnaire des " +
    "connaissances, des contrôles par échantillonnage confiés à la conformité, une finalité limitée pour la recherche " +
    "d'experts et une décision formelle avant tout recours à un LLM externe. Le détail, avec la matrice RACI, est au chapitre 7.");

  // 19. Limites et perspectives ------------------------------------------------------------------------------------------
  s = slideFor("CONTENU", "Déploiement et conclusion");
  s.addText("Limites assumées et perspectives", { placeholder: "title" });
  card(s, MX, 1.5, 5.9, 4.95, "colonne limites", C.background2);
  card(s, 6.83, 1.5, 5.9, 4.95, "colonne perspectives", C.background2);
  await iconCircle(s, fa.FaExclamationCircle, MX + 0.3, 1.75, 0.6, C.accent6, "limites");
  text(s, "Limites", { x: MX + 1.05, y: 1.75, w: 4.5, h: 0.6, fontSize: 20, bold: true, valign: "middle" });
  text(s, [
    { text: "Aucun LLM évalué : aucune clé disponible", options: { bullet: true, breakLine: true } },
    { text: "Corpus synthétique, conçu par l'auteure", options: { bullet: true, breakLine: true } },
    { text: "Encodeurs légers, hors-ligne", options: { bullet: true, breakLine: true } },
    { text: "Suffisance lexicale : 18 % d'abstentions abusives", options: { bullet: true, breakLine: true } },
    { text: "Rappel des règles 0,717 sur les documents de test", options: { bullet: true, breakLine: true } },
    { text: "Aucun déploiement distant ; pas prête pour la production", options: { bullet: true } },
  ], { x: MX + 0.3, y: 2.65, w: 5.3, h: 3.6, fontSize: 17, paraSpaceAfter: 14 });
  await iconCircle(s, fa.FaLightbulb, 7.13, 1.75, 0.6, C.accent1, "perspectives");
  text(s, "Perspectives", { x: 7.88, y: 1.75, w: 4.5, h: 0.6, fontSize: 20, bold: true, valign: "middle" });
  text(s, [
    { text: "Rejouer la campagne avec un LLM, plus une relecture humaine", options: { bullet: true, breakLine: true } },
    { text: "Pilote sur documents réels, questions des métiers", options: { bullet: true, breakLine: true } },
    { text: "Encodeur neuronal multilingue", options: { bullet: true, breakLine: true } },
    { text: "Contrôle de suffisance sémantique", options: { bullet: true, breakLine: true } },
    { text: "Écran de validation des entités candidates", options: { bullet: true, breakLine: true } },
    { text: "GraphRAG global : résumés de communautés", options: { bullet: true } },
  ], { x: 7.13, y: 2.65, w: 5.3, h: 3.6, fontSize: 17, paraSpaceAfter: 14 });
  s.addNotes("Je préfère annoncer moi-même les limites. Aucun LLM n'a été évalué, faute de clé : la plateforme est prête, la " +
    "mesure reste à faire. Le corpus est synthétique. Les encodeurs sont légers. Le contrôle de suffisance est lexical. Les " +
    "règles d'extraction perdent en rappel sur les documents jamais vus. Et la plateforme n'est ni déployée à distance ni " +
    "prête pour la production. Chaque limite ouvre une perspective concrète, la première étant de rejouer la campagne avec " +
    "un LLM, sur les mêmes questions.");

  // 20. Conclusion -----------------------------------------------------------------------------------------------------------
  s = slideFor("TITRE", "Déploiement et conclusion");
  s.addText("Ce qui fait la valeur d'un assistant documentaire en banque", { placeholder: "title" });
  s.addText([
    { text: "Une plateforme complète, du fichier brut à la réponse citée", options: { bullet: true, breakLine: true } },
    { text: "Une évaluation honnête : le graphe aide là où on l'attend", options: { bullet: true, breakLine: true } },
    { text: "Des droits, une provenance et une gouvernance pensés dès la conception", options: { bullet: true } },
  ], { placeholder: "body" });
  s.addText([{ text: "Merci de votre attention", options: { fontSize: 24, bold: true, color: C.background1 } }],
    { placeholder: "info" });
  nodes.forEach(([x, y, d, col], i) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: col },
    line: { color: C.background1, width: 1.5 }, objectName: "motif final " + i }));
  s.addNotes("Pour conclure : la valeur d'un assistant documentaire en banque tient moins à la sophistication de son modèle " +
    "de langage qu'à la rigueur de ce qui l'entoure : la qualité des documents, la traçabilité des faits, le respect des " +
    "droits et la capacité à dire « je ne sais pas ». C'est ce que j'ai cherché à construire et à mesurer. Je vous remercie " +
    "et je suis prête à répondre à vos questions.");

  await pres.writeFile({ fileName: OUT });
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("PPTX écrit : " + OUT);
}

build().catch((err) => { console.error(err); process.exit(1); });
