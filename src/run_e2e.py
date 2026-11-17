"""Prova end-to-end (requisito M1): query SPARQL -> sem:filter in GraphDB -> modello -> risposta, su N film.

Uso (dalla radice del repository; GraphDB avviato con il jar caricato, τ materializzato, server del modello acceso):
    python -m src.run_e2e --data data/films/dev --repo films-dev --n 10

Esegue Q1 sui primi N film del main set (ordinati per IRI, quindi sempre gli stessi) in due forme:
  1. diagnostica: BIND(sem:filter(...) AS ?ans) restituisce la risposta di OGNI film. Un errore della funzione
     (per esempio un parse failure) lascia ?ans vuoto, quindi si vede; dentro un FILTER sarebbe un "falso" silenzioso.
  2. piano di riferimento: la forma con sottoquery DISTINCT + LIMIT e il FILTER fuori, come nelle slide.
Salva tutto in eval/e2e/ con la verità della chiave per confronto. Le chiamate al modello vanno contate nel log
(della funzione Java ora, del gateway poi): attese N per la forma 1 e N per la forma 2.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from dotenv import find_dotenv, load_dotenv

from .data_observations import load_key

PRE = """PREFIX ex: <http://example.org/semop/>
PREFIX sem: <http://example.org/semop/function/>
"""


def inner(graph: str, n: int) -> str:
    return f"""SELECT DISTINCT ?film ?tau WHERE {{
        ?film ex:inSet ex:set-main .
        GRAPH <{graph}> {{ ?film ex:tau ?tau }}
      }} ORDER BY ?film LIMIT {n}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--graph", default="http://example.org/semop/tau-t0_v1")
    ap.add_argument("--prompts", default="prompts/filter_v1.json")
    ap.add_argument("--run", default="ex:run-e2e-q1")
    ap.add_argument("--out", default="eval/e2e")
    a = ap.parse_args()

    load_dotenv(find_dotenv(usecwd=True))
    base = os.environ.get("GRAPHDB_URL", "http://localhost:7200").rstrip("/")
    langex = json.loads(Path(a.prompts).read_text(encoding="utf-8"))["criteria"]["Q1"]
    lit = json.dumps(langex)  # letterale SPARQL con virgolette ed escape

    def run(q):
        t = time.time()
        r = httpx.post(f"{base}/repositories/{a.repo}", data={"query": q},
                       headers={"Accept": "application/sparql-results+json"}, timeout=None)
        if r.status_code != 200:
            raise SystemExit(f"GraphDB ha risposto {r.status_code}:\n{r.text[:1500]}")
        return r.json()["results"]["bindings"], time.time() - t

    q_diag = PRE + f"""SELECT ?film ?ans WHERE {{
  {{ {inner(a.graph, a.n)} }}
  BIND(sem:filter(?tau, {lit}, {a.run}) AS ?ans)
}}"""
    q_ref = PRE + f"""SELECT ?film WHERE {{
  {{ {inner(a.graph, a.n)} }}
  FILTER(sem:filter(?tau, {lit}, {a.run}))
}}"""

    rows, t1 = run(q_diag)
    if not rows:
        raise SystemExit("Nessun film: τ non è nel graph indicato (lanciare prima src.materialize_tau) o il set è vuoto.")
    key = load_key(Path(a.data) / "gt" / "q1.csv")
    labels = pd.read_csv(Path(a.data) / "entities.csv", usecols=["qid", "label"]).set_index("qid").label
    out = []
    for b in rows:
        qid = b["film"]["value"].rsplit("/", 1)[-1]
        ans = b.get("ans", {}).get("value")          # assente = errore della funzione
        out.append({"qid": qid, "film": labels.get(qid, "?"), "risposta": ans if ans is not None else "ERRORE",
                    "verita_chiave_espansa": key.get(qid, (False, False))[0]})
    ref, t2 = run(q_ref)
    ref_q = sorted(b["film"]["value"].rsplit("/", 1)[-1] for b in ref)
    diag_true = sorted(r["qid"] for r in out if r["risposta"] == "true")

    df = pd.DataFrame(out)
    print(df.to_string(index=False))
    err = int((df.risposta == "ERRORE").sum())
    print(f"\nForma diagnostica: {len(df)} film, {err} errori, {t1:.1f} s ({t1 / len(df):.2f} s per film).")
    print(f"Forma di riferimento (FILTER): {len(ref_q)} film veri, {t2:.1f} s.")
    print("Stesso insieme di film veri nelle due forme:", ref_q == diag_true)
    print(f"Attese nel log delle chiamate: {len(df)} chiamate per ciascuna forma (nessuna cache senza gateway).")

    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    df.to_csv(d / f"e2e_q1_{a.repo}_{stamp}.csv", index=False)
    (d / f"e2e_q1_{a.repo}_{stamp}.json").write_text(json.dumps({
        "data": stamp, "repo": a.repo, "graph_tau": a.graph, "langex": langex, "run": a.run,
        "modello": os.getenv("LOCAL_MODEL"), "n": len(df), "errori": err,
        "secondi_diagnostica": round(t1, 2), "secondi_riferimento": round(t2, 2),
        "veri_riferimento": ref_q, "veri_diagnostica": diag_true,
        "query_diagnostica": q_diag, "query_riferimento": q_ref}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Salvato in {d}/")


if __name__ == "__main__":
    main()
