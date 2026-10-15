// Génère le mémoire (DOCX) à partir des chapitres Markdown de sources/memoire/.
// Usage : node build_memoire.js  (depuis ce dossier) — puis python3 finalize_memoire.py pour
// mettre à jour sommaire et listes et produire le PDF.
//
// Sous-ensemble Markdown pris en charge : titres (#..####, « {-} » = non numéroté,
// « {annexe} » = annexe), paragraphes, **gras**, *italique*, `code`, listes à puces et
// numérotées (un niveau d'imbrication), tableaux (ligne « Table: légende » juste après),
// images « ![légende](chemin){width=14cm} », blocs de code ```, citations « > », marqueurs
// <!-- pagebreak -->, [[SOMMAIRE]], [[FIGURES]], [[TABLEAUX]].

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat, LineRuleType, NumberFormat,
  Packer, PageBreak, PageNumber, Paragraph, ShadingType, SimpleField, Table, TableCell,
  TableOfContents, TableRow, TextRun, VerticalAlign, WidthType,
} = require("docx");

const HERE = __dirname;
const CONFIG = JSON.parse(fs.readFileSync(path.join(HERE, "memoire.json"), "utf8"));
const CM = 567; // 1 cm en DXA
const PAGE = { width: 11906, height: 16838 }; // A4
const MARGIN = { top: Math.round(2.5 * CM), bottom: Math.round(2.5 * CM), left: Math.round(3 * CM), right: Math.round(2.5 * CM) };
const TEXT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right;
const BODY_FONT = "Times New Roman";
const HEAD_FONT = "Calibri";
const MONO_FONT = "Courier New";
const ACCENT = "1F3A5F";

// ------------------------------------------------------------------ texte en ligne
function inlineRuns(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g;
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const token = m[0];
    if (token.startsWith("**")) runs.push(new TextRun({ text: token.slice(2, -2), bold: true, ...base }));
    else if (token.startsWith("`")) runs.push(new TextRun({ text: token.slice(1, -1), font: MONO_FONT, size: 20, ...base }));
    else runs.push(new TextRun({ text: token.slice(1, -1), italics: true, ...base }));
    last = m.index + token.length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  return runs;
}

// ------------------------------------------------------------------ légendes numérotées
// Champ SEQ avec valeur pré-calculée : affiché correctement même sans mise à jour des champs,
// et reconnu par les listes des figures et des tableaux.
const captionCount = { Figure: 0, Tableau: 0 };
function captionRuns(label, caption) {
  captionCount[label] += 1;
  return [new TextRun(`${label} `), new SimpleField(`SEQ ${label} \\* ARABIC`, String(captionCount[label])), new TextRun(` – ${caption}`)];
}

// ------------------------------------------------------------------ images
function pngSize(file) {
  const buf = fs.readFileSync(file);
  if (buf.toString("ascii", 1, 4) !== "PNG") throw new Error(`Image non PNG : ${file}`);
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), data: buf };
}

function imageParagraphs(caption, src, widthCm) {
  const file = path.resolve(HERE, src);
  const { width, height, data } = pngSize(file);
  const maxPx = Math.round((Math.min(widthCm || 15, TEXT_WIDTH / CM) / 2.54) * 96);
  const scale = maxPx / width;
  const imgHeight = Math.round(height * scale);
  const limitPx = Math.round((19 / 2.54) * 96); // hauteur maximale ≈ 19 cm
  const factor = imgHeight > limitPx ? limitPx / imgHeight : 1;
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60, line: 240, lineRule: LineRuleType.AUTO },
      children: [new ImageRun({ type: "png", data, transformation: { width: Math.round(maxPx * factor), height: Math.round(imgHeight * factor) },
        altText: { title: caption, description: caption, name: path.basename(file) } })],
    }),
    new Paragraph({
      style: "Caption", alignment: AlignmentType.CENTER,
      children: captionRuns("Figure", caption),
    }),
  ];
}

// ------------------------------------------------------------------ tableaux
function tableBlock(lines, caption) {
  const parse = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  const header = parse(lines[0]);
  const rows = lines.slice(2).map(parse);
  const n = header.length;
  const lengths = Array.from({ length: n }, (_, i) =>
    Math.max(4, Math.min(48, Math.max(header[i].length, ...rows.map((r) => (r[i] || "").length)))));
  // Largeur minimale : le mot le plus long de la colonne (en-tête en gras compris) doit tenir
  // sur une ligne ; le reste de la largeur est réparti proportionnellement au contenu.
  // Largeur approximative d'un mot en twips (Times 9,5 pt) : capitales et chiffres plus larges.
  const wordWidth = (w) => [...w].reduce((a, ch) => a + (/[A-Z0-9_@%]/.test(ch) ? 135 : 100), 0);
  const longestWord = (t) => Math.max(0, ...String(t || "").replace(/[*`]/g, "").split(/\s+/).map(wordWidth));
  const minWidths = Array.from({ length: n }, (_, i) =>
    Math.max(Math.round(longestWord(header[i]) * 1.1), ...rows.map((r) => longestWord(r[i]))) + 220);
  const widths = new Array(n).fill(0);
  const fixed = new Set();
  for (let pass = 0; pass < n; pass += 1) {
    const free = [...Array(n).keys()].filter((i) => !fixed.has(i));
    const available = TEXT_WIDTH - [...fixed].reduce((a, i) => a + widths[i], 0);
    const freeTotal = free.reduce((a, i) => a + lengths[i], 0);
    free.forEach((i) => { widths[i] = Math.floor((available * lengths[i]) / freeTotal); });
    const tooNarrow = free.filter((i) => widths[i] < minWidths[i]);
    if (!tooNarrow.length) break;
    tooNarrow.forEach((i) => { widths[i] = minWidths[i]; fixed.add(i); });
  }
  widths[n - 1] += TEXT_WIDTH - widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, i, isHeader) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    shading: isHeader ? { type: ShadingType.CLEAR, color: "auto", fill: "DCE4EE" } : undefined,
    children: [new Paragraph({ spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.LEFT,
      children: inlineRuns(text || "", { size: 19, bold: isHeader ? true : undefined, font: BODY_FONT }) })],
  });
  const blocks = [];
  if (caption) {
    blocks.push(new Paragraph({ style: "Caption", alignment: AlignmentType.CENTER, keepNext: true,
      children: captionRuns("Tableau", caption) }));
  }
  blocks.push(new Table({
    width: { size: TEXT_WIDTH, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: header.map((_, i) => cell(r[i], i, false)) })),
    ],
  }));
  blocks.push(new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }));
  return blocks;
}

// ------------------------------------------------------------------ titres et numérotation
const counters = { chapter: 0, h2: 0, h3: 0, annex: 0 };
let inAnnex = false;

function heading(level, raw) {
  let text = raw.trim();
  if (/\{nontoc\}\s*$/.test(text)) {
    return new Paragraph({ style: "FrontHeading", pageBreakBefore: true, children: [new TextRun(text.replace(/\{nontoc\}\s*$/, "").trim())] });
  }
  const unnumbered = /\{-\}\s*$/.test(text);
  const annex = /\{annexe\}\s*$/.test(text);
  text = text.replace(/\{-\}\s*$|\{annexe\}\s*$/, "").trim();
  let label = text;
  if (level === 1) {
    counters.h2 = 0; counters.h3 = 0;
    if (annex) { inAnnex = true; counters.annex += 1; label = `Annexe ${String.fromCharCode(64 + counters.annex)} – ${text}`; }
    else if (!unnumbered) { inAnnex = false; counters.chapter += 1; label = `Chapitre ${counters.chapter} – ${text}`; }
    else { inAnnex = false; }
  } else if (level === 2 && !unnumbered && !inAnnex && counters.chapter > 0 && !/\{-\}/.test(raw)) {
    counters.h2 += 1; counters.h3 = 0; label = `${counters.chapter}.${counters.h2} ${text}`;
  } else if (level === 3 && !unnumbered && !inAnnex && counters.h2 > 0) {
    counters.h3 += 1; label = `${counters.chapter}.${counters.h2}.${counters.h3} ${text}`;
  }
  const headingLevel = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4][level - 1];
  return new Paragraph({ heading: headingLevel, pageBreakBefore: level === 1, children: [new TextRun(label)] });
}

// ------------------------------------------------------------------ conversion d'un fichier Markdown
function convert(markdown, state) {
  const out = [];
  const lines = markdown.replace(/\r/g, "").split("\n");
  let i = 0;
  let paragraph = [];
  let referenceMode = false;  // « <!-- references --> » : entrées bibliographiques à retrait suspendu
  const flush = () => {
    if (paragraph.length) {
      out.push(new Paragraph({ style: referenceMode ? "Reference" : "BodyText", children: inlineRuns(paragraph.join(" ")) }));
      paragraph = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) { flush(); i += 1; continue; }
    if (trimmed === "<!-- pagebreak -->") { flush(); out.push(new Paragraph({ children: [new PageBreak()] })); i += 1; continue; }
    if (trimmed === "<!-- references -->") { flush(); referenceMode = true; i += 1; continue; }
    if (trimmed.startsWith("<!--")) { i += 1; continue; }
    if (trimmed === "[[SOMMAIRE]]") {
      flush();
      out.push(new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-3" }));
      i += 1; continue;
    }
    if (trimmed === "[[FIGURES]]" || trimmed === "[[TABLEAUX]]") {
      flush();
      out.push(new TableOfContents(trimmed === "[[FIGURES]]" ? "Liste des figures" : "Liste des tableaux",
        { hyperlink: true, captionLabelIncludingNumbers: trimmed === "[[FIGURES]]" ? "Figure" : "Tableau" }));
      i += 1; continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (h) { flush(); if (h[1].length <= 2) referenceMode = false; out.push(heading(h[1].length, h[2])); i += 1; continue; }
    if (trimmed.startsWith("```")) {
      flush();
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) { code.push(lines[i]); i += 1; }
      i += 1;
      code.forEach((c, k) => out.push(new Paragraph({
        style: "CodeBlock", keepNext: k < code.length - 1,
        children: [new TextRun({ text: c.replace(/\t/g, "    ") || " ", font: MONO_FONT, size: 17 })],
      })));
      continue;
    }
    const img = /^!\[([^\]]*)\]\(([^)]+)\)(\{width=([\d.]+)cm\})?$/.exec(trimmed);
    if (img) { flush(); out.push(...imageParagraphs(img[1], img[2], img[4] ? parseFloat(img[4]) : undefined)); i += 1; continue; }
    if (trimmed.startsWith("|")) {
      flush();
      const block = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) { block.push(lines[i]); i += 1; }
      let caption = null;
      while (i < lines.length && !lines[i].trim()) i += 1;
      if (i < lines.length && /^Table:\s*/.test(lines[i].trim())) { caption = lines[i].trim().replace(/^Table:\s*/, ""); i += 1; }
      out.push(...tableBlock(block, caption));
      continue;
    }
    if (trimmed.startsWith(">")) {
      flush();
      const quote = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) { quote.push(lines[i].trim().replace(/^>\s?/, "")); i += 1; }
      out.push(new Paragraph({ style: "Quote", children: inlineRuns(quote.join(" ")) }));
      continue;
    }
    const bullet = /^(\s*)[-*]\s+(.*)$/.exec(line);
    const numbered = /^(\s*)(\d+)[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      flush();
      const level = Math.min(1, Math.floor(((bullet || numbered)[1].length) / 2));
      let text = bullet ? bullet[2] : numbered[3];
      i += 1;
      while (i < lines.length && lines[i].trim() && !/^(\s*)([-*]|\d+[.)])\s+/.test(lines[i]) && /^\s{2,}/.test(lines[i])) {
        text += " " + lines[i].trim(); i += 1;
      }
      if (numbered && level === 0 && numbered[2] === "1") state.listInstance += 1; // nouvelle liste numérotée
      out.push(new Paragraph({
        style: "ListText",
        numbering: bullet ? { reference: "puces", level } : { reference: "numeros", level, instance: state.listInstance },
        children: inlineRuns(text),
      }));
      continue;
    }
    paragraph.push(trimmed);
    i += 1;
  }
  flush();
  return out;
}

// ------------------------------------------------------------------ page de titre
function titlePage() {
  const c = CONFIG;
  const p = (text, opts = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: opts.after ?? 120 },
    children: [new TextRun({ text, font: HEAD_FONT, size: opts.size ?? 24, bold: opts.bold, color: opts.color, italics: opts.italics })] });
  return [
    p(c.institution, { size: 26, bold: true }),
    p(c.department, { size: 22 }),
    p(c.program, { size: 22, after: 1200 }),
    p(c.document_type, { size: 26, color: ACCENT, after: 400 }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
      border: { top: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 12 }, bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 12 } },
      children: [new TextRun({ text: c.title, font: HEAD_FONT, size: 40, bold: true, color: ACCENT })] }),
    p(c.subtitle, { size: 24, italics: true, after: 1400 }),
    p(`Présenté par : ${c.author}`, { size: 24, bold: true }),
    p(`Encadrement académique : ${c.academic_supervisor}`, { size: 22 }),
    p(`Encadrement professionnel : ${c.professional_supervisor}`, { size: 22, after: 1400 }),
    p(c.year, { size: 24, bold: true }),
    p(c.notice, { size: 18, italics: true, color: "595959" }),
  ];
}

// ------------------------------------------------------------------ assemblage
async function main() {
  const state = { listInstance: 0 };
  const front = [];
  const body = [];
  for (const file of CONFIG.front_matter) front.push(...convert(fs.readFileSync(path.join(HERE, file), "utf8"), state));
  for (const file of CONFIG.chapters) body.push(...convert(fs.readFileSync(path.join(HERE, file), "utf8"), state));

  const headerFooter = (format) => ({
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 4 } },
      children: [new TextRun({ text: CONFIG.running_title, font: HEAD_FONT, size: 16, color: "7F7F7F" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: HEAD_FONT, size: 18, color: "595959" })] })] }) },
    properties: { page: { size: PAGE, margin: MARGIN, pageNumbers: { start: 1, formatType: format } } },
  });

  const doc = new Document({
    creator: CONFIG.author, title: CONFIG.title, description: CONFIG.subtitle, language: "fr-FR",
    features: { updateFields: true },
    styles: {
      default: { document: { run: { font: BODY_FONT, size: 24 }, paragraph: { spacing: { line: 336, lineRule: LineRuleType.AUTO } } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "BodyText", quickFormat: true,
          run: { font: HEAD_FONT, size: 36, bold: true, color: ACCENT },
          paragraph: { spacing: { before: 240, after: 360 }, keepNext: true, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "BodyText", quickFormat: true,
          run: { font: HEAD_FONT, size: 28, bold: true, color: ACCENT },
          paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "BodyText", quickFormat: true,
          run: { font: HEAD_FONT, size: 25, bold: true, color: "2F2F2F" },
          paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 2 } },
        { id: "Heading4", name: "Heading 4", basedOn: "Normal", next: "BodyText", quickFormat: true,
          run: { font: HEAD_FONT, size: 23, bold: true, italics: true, color: "2F2F2F" },
          paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 3 } },
        { id: "FrontHeading", name: "Front Heading", basedOn: "Normal", next: "BodyText",
          run: { font: HEAD_FONT, size: 36, bold: true, color: ACCENT }, paragraph: { spacing: { before: 240, after: 360 }, keepNext: true } },
        { id: "BodyText", name: "Body Text", basedOn: "Normal", quickFormat: true,
          paragraph: { alignment: AlignmentType.JUSTIFIED, spacing: { after: 140, line: 336, lineRule: LineRuleType.AUTO } } },
        { id: "Reference", name: "Reference", basedOn: "Normal",
          paragraph: { alignment: AlignmentType.LEFT, indent: { left: 567, hanging: 567 }, spacing: { after: 120, line: 300, lineRule: LineRuleType.AUTO } } },
        { id: "ListText", name: "List Text", basedOn: "Normal",
          paragraph: { alignment: AlignmentType.JUSTIFIED, spacing: { after: 70, line: 312, lineRule: LineRuleType.AUTO } } },
        { id: "Caption", name: "Caption", basedOn: "Normal", next: "BodyText",
          run: { font: HEAD_FONT, size: 19, italics: true, color: "404040" }, paragraph: { spacing: { before: 60, after: 220 } } },
        { id: "Quote", name: "Quote", basedOn: "Normal",
          run: { italics: true, color: "404040" }, paragraph: { indent: { left: 567, right: 567 }, spacing: { after: 140 } } },
        { id: "CodeBlock", name: "Code Block", basedOn: "Normal",
          run: { font: MONO_FONT, size: 17 },
          paragraph: { spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO }, indent: { left: 284 },
            shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" } } },
      ],
    },
    numbering: {
      config: [
        { reference: "puces", levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 567, hanging: 284 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1134, hanging: 284 } } } }] },
        { reference: "numeros", levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 567, hanging: 340 } } } },
          { level: 1, format: LevelFormat.LOWER_LETTER, text: "%2)", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1134, hanging: 340 } } } }] },
      ],
    },
    sections: [
      { properties: { page: { size: PAGE, margin: MARGIN } }, children: titlePage() },
      { ...headerFooter(NumberFormat.LOWER_ROMAN), children: front },
      { ...headerFooter(NumberFormat.DECIMAL), children: body },
    ],
  });
  const target = path.join(HERE, "..", CONFIG.output_docx);
  fs.writeFileSync(target, await Packer.toBuffer(doc));
  console.log(`DOCX écrit : ${target}`);
}

main().catch((err) => { console.error(err); process.exit(1); });
