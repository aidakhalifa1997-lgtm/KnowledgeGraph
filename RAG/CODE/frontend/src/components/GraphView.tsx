import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";
import type { GraphData } from "../types";
import { TYPE_STYLE, relationLabel } from "./graphStyle";

interface Props {
  data: GraphData;
  selected?: string | null;
  onSelect?: (id: string) => void;
  small?: boolean;
  label: string;
}

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Sans marqueur, Cytoscape injecte une balise <style> en ligne, refusée par la CSP (style-src 'self').
// La règle équivalente (position: relative du conteneur) est fournie par styles.css.
function preventInlineStylesheet() {
  if (!document.getElementById("__________cytoscape_stylesheet")) {
    const marker = document.createElement("meta");
    marker.id = "__________cytoscape_stylesheet";
    document.head.appendChild(marker);
  }
}

const truncate = (s: string, n = 34) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export default function GraphView({ data, selected, onSelect, small, label }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    if (!container.current) return;
    preventInlineStylesheet();
    const ink = cssVar("--ink") || "#1d1c1a";
    const ink2 = cssVar("--ink-3") || "#7a756b";
    const surface = cssVar("--surface") || "#fffdf8";
    const accent = cssVar("--accent") || "#a8492a";
    const ids = new Set(data.nodes.map((n) => n.id));
    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id, label: truncate(n.name), type: n.type, seed: n.seed ? 1 : 0,
          color: TYPE_STYLE[n.type]?.color ?? "#8a857a", shape: TYPE_STYLE[n.type]?.shape ?? "ellipse",
        },
      })),
      ...data.edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e) => ({
          data: { id: e.id, source: e.source, target: e.target, label: relationLabel(e.label), cited: e.cited ? 1 : 0 },
        })),
    ];
    const instance = cytoscape({
      container: container.current,
      elements,
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.25,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)", shape: "data(shape)" as never, width: 26, height: 26,
            label: "data(label)", "font-size": 10, color: ink, "text-valign": "bottom", "text-margin-y": 5,
            "text-wrap": "wrap", "text-max-width": "120px", "border-width": 2, "border-color": surface,
            "text-background-color": surface, "text-background-opacity": 0.85, "text-background-padding": "2px",
          },
        },
        { selector: "node[seed = 1]", style: { width: 34, height: 34, "border-color": accent, "border-width": 3 } },
        { selector: "node:selected", style: { "border-color": accent, "border-width": 4 } },
        {
          selector: "edge",
          style: {
            width: 1.5, "line-color": ink2, "target-arrow-color": ink2, "target-arrow-shape": "triangle",
            "arrow-scale": 0.8, "curve-style": "bezier", label: "data(label)", "font-size": 8, color: ink2,
            "text-rotation": "autorotate", "text-background-color": surface, "text-background-opacity": 0.9,
            "text-background-padding": "1px", opacity: 0.85,
          },
        },
        { selector: "edge[cited = 1]", style: { width: 3, "line-color": accent, "target-arrow-color": accent, color: ink } },
      ],
      // Voisinage d'une entité : disposition concentrique, l'entité au centre ; sinon force dirigée.
      layout: (data.center && ids.has(data.center)
        ? { name: "concentric", animate: false, padding: 30, minNodeSpacing: 40, avoidOverlap: true,
            concentric: (node: cytoscape.NodeSingular) =>
              node.id() === data.center ? 3 : node.neighborhood(`node[id = "${data.center}"]`).length ? 2 : 1,
            levelWidth: () => 1 }
        : { name: "cose", animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 90, padding: 24,
            randomize: false, componentSpacing: 60 }) as cytoscape.LayoutOptions,
    });
    instance.on("tap", "node", (evt) => select.current?.(evt.target.id()));
    cy.current = instance;
    return () => instance.destroy();
  }, [data]);

  useEffect(() => {
    const instance = cy.current;
    if (!instance) return;
    instance.nodes().unselect();
    if (selected) instance.getElementById(selected).select();
  }, [selected, data]);

  return (
    <div>
      <div ref={container} className={`graph-canvas${small ? " small" : ""}`} role="img" aria-label={label} />
      <div className="legend" style={{ marginTop: 8 }} aria-label="Légende du graphe">
        {Object.entries(TYPE_STYLE)
          .filter(([type]) => data.nodes.some((n) => n.type === type))
          .map(([type, s]) => (
            <span key={type}><span className="dot" style={{ background: s.color }} />{s.label}</span>
          ))}
      </div>
    </div>
  );
}
