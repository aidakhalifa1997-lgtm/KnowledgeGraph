import { Fragment, type ReactNode } from "react";

// Rendu sûr de la réponse : le texte n'est jamais interprété comme du HTML. Les citations
// [C1] / [F2] deviennent des boutons qui affichent la source correspondante.

interface Props {
  text: string;
  validIds: Set<string>;
  onCite: (id: string) => void;
}

const CITATION = /\[(C|F)(\d+)\]/g;

function inline(line: string, props: Props, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of line.matchAll(CITATION)) {
    const id = `${match[1]}${match[2]}`;
    if (match.index! > last) parts.push(line.slice(last, match.index));
    const valid = props.validIds.has(id);
    parts.push(
      <button
        key={`${keyPrefix}-${match.index}`}
        className={`cite${match[1] === "F" ? " fact" : ""}${valid ? "" : " invalid"}`}
        onClick={() => valid && props.onCite(id)}
        aria-label={match[1] === "C" ? `Voir le passage source ${id}` : `Voir le fait du graphe ${id}`}
        type="button"
      >
        {id}
      </button>,
    );
    last = match.index! + match[0].length;
  }
  if (last < line.length) parts.push(line.slice(last));
  return parts;
}

export default function AnswerText(props: Props) {
  const blocks = props.text.split(/\n{2,}/);
  return (
    <div className="answer">
      {blocks.map((block, b) => {
        const lines = block.split("\n");
        const bullets = lines.filter((l) => l.trim().startsWith("- "));
        const intro = lines.filter((l) => !l.trim().startsWith("- "));
        return (
          <Fragment key={b}>
            {intro.length > 0 && <p>{intro.map((l, i) => <Fragment key={i}>{i > 0 && <br />}{inline(l, props, `${b}-i${i}`)}</Fragment>)}</p>}
            {bullets.length > 0 && (
              <ul>{bullets.map((l, i) => <li key={i}>{inline(l.trim().slice(2), props, `${b}-l${i}`)}</li>)}</ul>
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
