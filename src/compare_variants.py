"""Confronto film per film tra varianti di τ, a partire dal file ..._decisioni.csv di tau_study.

Uso (dalla radice del repository):
    python -m src.compare_variants --data data/films/dev --decisions eval/tau_study_q1_local_decisioni.csv
    python -m src.compare_variants --data data/films/dev --decisions eval/tau_study_q1_local_decisioni.csv --out eval/confronto_varianti.md

Per ogni variante stampa i film su cui risponde diversamente dalla base (t0), con la verità della chiave e se il
film nomina la guerra nel testo (positivo "esplicito"). Poi elenca i falsi positivi e i positivi impliciti mancati
dalla base: sono i film da leggere a mano (un falso positivo può essere una dimenticanza di Wikidata).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .data_observations import KW
from .tau import TauBuilder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--base", default="t0")
    ap.add_argument("--query", default="Q1")
    ap.add_argument("--out", help="file .md dove salvare il confronto")
    a = ap.parse_args()

    d = pd.read_csv(a.decisions)
    variants = [c for c in d.columns if c not in ("qid", "truth")]
    if a.base not in variants:
        raise SystemExit(f"la variante base {a.base} non è nel file: {variants}")
    base_tau = TauBuilder(a.data, {"max_chars": None})
    kw = KW[a.query]
    d["film"] = [base_tau.ent.loc[q, "label"] for q in d.qid]
    d["esplicito"] = [bool(kw.search(base_tau.build(q))) for q in d.qid]
    d["truth"] = d.truth.astype(bool)

    lines = [f"# Confronto tra varianti (base: {a.base})", "",
             f"File: `{a.decisions}`. {len(d)} film, {int(d.truth.sum())} positivi (chiave espansa).",
             "Legenda: POS/neg = verità della chiave; *esplicito* = il testo nomina la guerra (stesse parole chiave di data_observations).", ""]
    for v in variants:
        if v == a.base:
            continue
        diff = d[d[a.base].ne(d[v])]
        gain = int(((diff[v] == 1) & diff.truth).sum() + ((diff[v] == 0) & ~diff.truth).sum())
        loss = len(diff) - gain
        lines += [f"## {a.base} contro {v}: {len(diff)} film in disaccordo ({gain} a favore di {v}, {loss} a favore di {a.base})", ""]
        for r in diff.itertuples():
            lines.append(f"- {'POS' if r.truth else 'neg'}{' *esplicito*' if r.esplicito else ''} | "
                         f"{a.base}={int(getattr(r, a.base))} {v}={int(getattr(r, v))} | {r.film} ({r.qid})")
        lines.append("")
    b = d[a.base]
    lines += [f"## Falsi positivi di {a.base} (da leggere: possibile chiave incompleta)", ""]
    lines += [f"- {r.film} ({r.qid}){' *esplicito*' if r.esplicito else ''}" for r in d[(b == 1) & ~d.truth].itertuples()]
    lines += ["", f"## Positivi impliciti mancati da {a.base}", ""]
    lines += [f"- {r.film} ({r.qid})" for r in d[(b == 0) & d.truth & ~d.esplicito].itertuples()]
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        print(f"\nSalvato: {a.out}")


if __name__ == "__main__":
    main()