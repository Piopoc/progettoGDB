"""Osservazioni sui dati che motivano le scelte su τ. Ogni numero ha la sua definizione.

Uso (dalla radice del repository, ambiente attivo):
    python -m src.data_observations --data data/films/dev
    python -m src.data_observations --data data/films/dev --out eval/data_observations.md

Ogni riga stampata dice: cosa si misura, su quale popolazione, il valore, il riferimento del
professore (se esiste) e come è calcolato. Quello che si scrive nel design note come "osservato
sui dati" deve essere una riga di questa tabella.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .tau import TauBuilder, token_stats

KW = {
    "Q1": re.compile(r"World War II|Second World War|WWII|World War Two", re.I),
}
KW_TEXT = "World War II | Second World War | WWII | World War Two (senza distinzione di maiuscole)"


def _qid(v) -> str:
    return str(v).rsplit("/", 1)[-1]


def load_main_qids(data_dir) -> list[str]:
    sets = pd.read_csv(Path(data_dir) / "sets.csv")
    return sorted(sets[sets.set_id == "main"].qid.map(_qid))


def load_key(path) -> dict[str, tuple[bool, bool]]:
    """Legge gt/qN.csv. Restituisce {qid: (path, direct)} per i film presenti nel file.

    Assunzioni da verificare con `head gt/q1.csv`: una colonna con l'identificatore (qid, oppure la
    prima colonna) e le colonne `path` (chiave espansa) e `direct`. Se mancano, errore esplicito."""
    df = pd.read_csv(path)
    idc = "qid" if "qid" in df.columns else df.columns[0]
    if "path" not in df.columns:
        raise ValueError(f"{path}: manca la colonna 'path'. Colonne trovate: {list(df.columns)}")

    def truthy(x):
        if isinstance(x, str):
            return x.strip().lower() in ("1", "true", "t", "yes")
        return bool(x) and x == x

    out = {}
    for _, r in df.iterrows():
        out[_qid(r[idc])] = (truthy(r["path"]), truthy(r["direct"]) if "direct" in df.columns else False)
    return out


def _pct(a, b):
    return f"{a} su {b} ({a / b:.1%})" if b else "n/d"


def observe(data_dir) -> list[dict]:
    d = Path(data_dir)
    ent = pd.read_csv(d / "entities.csv")
    films = ent[ent["class"] == "Film"].copy()
    rows = []

    def add(oss, pop, val, rif, come):
        rows.append({"osservazione": oss, "popolazione": pop, "valore": val, "riferimento": rif, "come_si_calcola": come})

    main = load_main_qids(d) if (d / "sets.csv").exists() else list(films.qid)
    main_pop = f"main set ({len(main)} film)"
    base = TauBuilder(d, {"max_chars": None})
    t0 = TauBuilder(d, {})

    add("Entità nel dev set", "tutte", f"{len(films)} film, {(ent['class'] == 'Novel').sum()} romanzi",
        "README: 1.250 film, 600 romanzi", "righe di entities.csv per colonna class")
    add("Film senza anno di prima uscita", "film", str(int(films.first_year.isna().sum())), "-",
        "first_year vuoto in entities.csv")

    empty = films.description_screened.isna()
    flags = films[empty].description_flags.value_counts().to_dict()
    add("Descrizioni scartate dallo screening", "film", _pct(int(empty.sum()), len(films)), "lol.md: 74 entità",
        f"description_screened vuota. Motivi (description_flags): {flags}")

    L = np.array([len(base.build(q)) for q in films.qid])
    add("Lunghezza di τ0 senza taglio (caratteri)", "film",
        f"mediana {int(np.median(L))}; oltre 1200: {(L > 1200).mean():.1%}; oltre 600: {(L > 600).mean():.1%}; oltre 2000: {(L > 2000).mean():.1%}",
        "-", "lunghezza di titolo + descrizione screened + lead, senza taglio")

    ts = token_stats([t0.build(q) for q in main])
    add("Token di τ0 (con taglio a 1200)", main_pop,
        f"media {ts['mean']:.1f}; 90° percentile {ts['p90']:.0f}" + (" [STIMA caratteri/4: tiktoken non disponibile]" if ts["approx"] else ""),
        "README: media 168, p90 270 (cl100k_base)", "token_stats su τ0 per i film del main set")

    yr = films.first_year.fillna(-1).astype(int).astype(str)
    in_txt = [y in (str(r.description_screened) + " " + str(r.lead)) for y, r in zip(yr, films.itertuples())]
    in_desc = [y in str(r.description_screened) for y, r in zip(yr, films.itertuples())]
    add("L'anno di uscita compare già nel testo", "film",
        f"in descrizione+lead: {np.mean(in_txt):.1%}; solo nella descrizione: {np.mean(in_desc):.1%}", "-",
        "first_year come sottostringa di description_screened e lead")

    add("Lead con a capo interni", "film", f"{films.lead.str.contains(chr(10)).mean():.1%}", "-",
        "presenza di \\n nel lead (conta per la chiave della cache)")

    dd = films.description_screened.fillna("").str.contains("directed by", case=False)
    add("La descrizione screened contiene 'directed by'", "film", f"{dd.mean():.1%}", "-",
        "ricerca della stringa nella descrizione")

    if (d / "statements.csv").exists():
        st = pd.read_csv(d / "statements.csv", usecols=["qid", "property", "value", "value_label"])
        st["txt"] = st.value_label.where(st.value_label.notna(), st.value)
        for prop, name in (("P57", "regista"), ("P495", "paese di origine")):
            g = st[(st.property == prop) & st.qid.isin(main)].groupby("qid").txt.apply(list)
            hit = sum(any(str(v).lower() in t0.build(q).lower() for v in vals) for q, vals in g.items())
            add(f"Il {name} (statement del grafo) compare già in τ0", f"main set, film con {prop}",
                _pct(hit, len(g)), "-", f"almeno una label di {prop} come sottostringa del testo di τ0")

    # --- guerra: il confronto con le slide ---
    kw = KW["Q1"]
    full = {q: base.build(q) for q in main}
    names = {q for q, t in full.items() if kw.search(t)}
    key = None
    k1 = Path(d) / "gt" / "q1.csv"
    if k1.exists():
        key = load_key(k1)
    if key is None:
        add("Film che nominano la guerra nel testo", main_pop, str(len(names)), "slide: circa 106 (90+16)",
            f"parole chiave: {KW_TEXT}")
    else:
        pos = {q for q in main if key.get(q, (False, False))[0]}
        neg = set(main) - pos
        add("Positivi Q1 (chiave espansa)", main_pop, f"{len(pos)} su {len(main)}", "slide: 200 su 1000", "righe di gt/q1.csv con path vero")
        add("Positivi che nominano la guerra", main_pop, _pct(len(pos & names), len(pos)), "slide: 90 su 200",
            f"parole chiave: {KW_TEXT}; testo di τ0 senza taglio")
        add("Negativi che nominano la guerra", main_pop, _pct(len(neg & names), len(neg)), "slide: 16 su 800", "come sopra")
        add("Recall del filtro per parola chiave", main_pop, f"{len(pos & names) / len(pos):.2f}", "slide: 0,45",
            "positivi che nominano la guerra / positivi")
        add("Positivi impliciti (non nominano la guerra)", main_pop, _pct(len(pos - names), len(pos)), "slide: circa 110 su 200",
            "positivi senza parole chiave nel testo: solo l'inferenza li trova")
    first = [kw.search(full[q]).start() for q in names]
    if first:
        f = np.array(first)
        add("Prima menzione della guerra oltre il taglio", main_pop + ", film che la nominano",
            f"oltre 1200 car.: {(f > 1200).sum()} su {len(f)}; oltre 600: {(f > 600).sum()} su {len(f)}", "-",
            "posizione della prima occorrenza nel testo di τ0 senza taglio. Misura le parole chiave, non la comprensione del modello.")
    return rows


def to_markdown(rows) -> str:
    out = ["| # | Osservazione | Popolazione | Valore | Riferimento | Come si calcola |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append(f"| {i} | {r['osservazione']} | {r['popolazione']} | {r['valore']} | {r['riferimento']} | {r['come_si_calcola']} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="cartella dev del dominio, es. data/films/dev")
    ap.add_argument("--out", help="file .md dove salvare la tabella (es. eval/data_observations.md)")
    a = ap.parse_args()
    rows = observe(a.data)
    md = to_markdown(rows)
    print(md)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md + "\n", encoding="utf-8")
        pd.DataFrame(rows).to_csv(Path(a.out).with_suffix(".csv"), index=False)
        print(f"\nSalvato: {a.out}")


if __name__ == "__main__":
    main()
