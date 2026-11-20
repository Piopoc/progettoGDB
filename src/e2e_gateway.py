"""Prova end-to-end attraverso il gateway (requisito M1), senza la funzione Java.

Catena: GraphDB (τ letto dal named graph) -> gateway del corso (/v1/responses) -> modello -> decisione -> confronto
con la chiave. È la stessa chiamata che farà sem:filter quando la funzione Java passerà dal gateway; qui la fa Python.

Uso (dalla radice del repository; GraphDB acceso con τ materializzato, gateway avviato con `start server`):
    python -m src.e2e_gateway --data data/films/dev --repo films-dev --n 10 \
        --gateway-log ../llm-gateway/data/calls.jsonl

Lanciato DUE volte, la seconda esecuzione deve essere servita tutta dalla cache del gateway: nel suo registro
le righe del nuovo run_id hanno cache_hit = true (requisito "a cached re-run issues zero model requests").
Ogni esecuzione ha un run_id suo (m1-e2e-q1-<data e ora>), perché run_id non fa parte della chiave di cache.
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
from .llm_client import LLMClient

PRE = "PREFIX ex: <http://example.org/semop/>\n"


def fetch_tau(base: str, repo: str, graph: str, n: int) -> list[tuple[str, str]]:
    q = PRE + f"""SELECT DISTINCT ?film ?tau WHERE {{
  ?film ex:inSet ex:set-main .
  GRAPH <{graph}> {{ ?film ex:tau ?tau }}
}} ORDER BY ?film LIMIT {n}"""
    r = httpx.post(f"{base}/repositories/{repo}", data={"query": q},
                   headers={"Accept": "application/sparql-results+json"}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"GraphDB ha risposto {r.status_code}:\n{r.text[:800]}")
    rows = [(b["film"]["value"].rsplit("/", 1)[-1], b["tau"]["value"]) for b in r.json()["results"]["bindings"]]
    if not rows:
        raise SystemExit(f"Nessun film: τ non è nel graph {graph} del repository {repo} (lanciare src.materialize_tau).")
    return rows


def log_summary(path: Path, run_id: str) -> dict | None:
    """Righe del registro del gateway per questo run_id: quante chiamate, quante dalla cache, quanti fallback."""
    if not path or not path.exists():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("run_id") == run_id:
            rows.append(rec)
    return {"righe_nel_registro": len(rows),
            "cache_hit": sum(1 for r in rows if r.get("cache_hit") is True),
            "chiamate_al_modello": sum(1 for r in rows if r.get("cache_hit") is False),
            "fallback_parse_ok_false": sum(1 for r in rows if r.get("parse_ok") is False),
            "errori": sum(1 for r in rows if r.get("error_type") and r.get("parse_ok") is not False)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--graph", default="http://example.org/semop/tau-t0_v1")
    ap.add_argument("--prompts", default="prompts/filter_v1.json")
    ap.add_argument("--run-id", help="predefinito: m1-e2e-q1-<data e ora>")
    ap.add_argument("--gateway-log", help="data/calls.jsonl nella cartella del gateway, per contare chiamate e cache")
    ap.add_argument("--out", default="eval/e2e")
    a = ap.parse_args()

    load_dotenv(find_dotenv(usecwd=True))
    base = os.environ.get("GRAPHDB_URL", "http://localhost:7200").rstrip("/")
    fp = json.loads(Path(a.prompts).read_text(encoding="utf-8"))
    langex = fp["criteria"]["Q1"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = a.run_id or f"m1-e2e-q1-{stamp}"

    films = fetch_tau(base, a.repo, a.graph, a.n)
    print(f"1. GraphDB ({a.repo}): τ di {len(films)} film letti dal graph {a.graph}")

    client = LLMClient(run_id=run_id)
    print(f"2. Gateway {client.base}, modello {client.model}, run_id {run_id}, namespace {client.namespace}")
    t = time.time()
    res = client.ask_many([(fp["instructions"], fp["template"].format(langex=langex, tau=tau)) for _, tau in films])
    secs = time.time() - t

    key = load_key(Path(a.data) / "gt" / "q1.csv")
    labels = pd.read_csv(Path(a.data) / "entities.csv", usecols=["qid", "label"]).set_index("qid").label
    df = pd.DataFrame([{
        "qid": q, "film": labels.get(q, "?"),
        "risposta": "NON VALIDA" if r["parse_failure"] else str(r["answer"]).lower(),
        "verita_chiave_espansa": key.get(q, (False, False))[0],
        "token_in": r["tokens_in"], "token_out": r["tokens_out"], "secondi": r["seconds"]}
        for (q, _), r in zip(films, res)])
    print("\n" + df.to_string(index=False))
    invalid = int((df.risposta == "NON VALIDA").sum())
    print(f"\n3. {len(df)} richieste in {secs:.1f} s, {invalid} risposte non valide.")

    summ = log_summary(Path(a.gateway_log), run_id) if a.gateway_log else None
    if summ:
        print(f"4. Registro del gateway per {run_id}: {summ}")
        if summ["chiamate_al_modello"] == 0 and summ["cache_hit"] == len(df):
            print("   Tutto servito dalla cache: zero richieste al modello.")
    elif a.gateway_log:
        print(f"4. Registro del gateway non trovato in {a.gateway_log}")

    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / f"e2e_gateway_q1_{a.repo}_{stamp}.csv", index=False)
    (d / f"e2e_gateway_q1_{a.repo}_{stamp}.json").write_text(json.dumps({
        "data": stamp, "repo": a.repo, "graph_tau": a.graph, "langex": langex, "prompt": a.prompts,
        "gateway": client.base, "modello": client.model, "run_id": run_id, "cache_namespace": client.namespace,
        "n": len(df), "risposte_non_valide": invalid, "secondi": round(secs, 2), "registro_gateway": summ},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Salvato in {d}/")


if __name__ == "__main__":
    main()
