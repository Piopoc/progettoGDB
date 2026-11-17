"""Scrive τ nel grafo: una tripla ex:tau per entità, in un named graph per variante di τ.

La funzione sem:filter gira dentro GraphDB e riceve τ come argomento della query: non può chiamare tau.py.
Questo script costruisce τ in Python (stesso codice dello studio) e lo carica in GraphDB, così le query
leggono esattamente il testo studiato e testato, e non la descrizione grezza dello store.

Uso (dalla radice del repository, GraphDB avviato):
    # 1. prova a secco: scrive solo il file .nq e stampa un esempio, nessun accesso a GraphDB
    python -m src.materialize_tau --data data/films/dev --cfg prompts/tau_t0_v1.json --repo films-dev --dry-run
    # 2. caricamento vero
    python -m src.materialize_tau --data data/films/dev --cfg prompts/tau_t0_v1.json --repo films-dev
    python -m src.materialize_tau --data data/films/eval --cfg prompts/tau_t0_v1.json --repo films-eval

Il named graph prende il nome dal file di configurazione: tau_t0_v1.json -> ex:tau-t0_v1.
Il caricamento è ripetibile: prima svuota quel named graph, poi lo riscrive. Gli altri grafi non vengono toccati.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
import pandas as pd
from dotenv import find_dotenv, load_dotenv

from .tau import TauBuilder, load_cfg

EX = "http://example.org/semop/"
WD = "http://www.wikidata.org/entity/"


def graph_iri(cfg_path: str) -> str:
    m = re.fullmatch(r"tau_(.+)\.json", Path(cfg_path).name)
    if not m:
        raise SystemExit(f"nome di configurazione inatteso: {cfg_path} (atteso tau_<variante>_v<N>.json)")
    return f"{EX}tau-{m.group(1)}"


def nq_literal(s: str) -> str:
    """Letterale N-Quads: si escapano backslash, virgolette e a capo (il testo resta identico dopo il parsing)."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{s}"'


def build_nquads(data_dir: str, cfg_path: str) -> tuple[str, int, str]:
    tb = TauBuilder(data_dir, load_cfg(cfg_path))
    g = graph_iri(cfg_path)
    lines = []
    for qid in tb.ent.index:
        lines.append(f"<{WD}{qid}> <{EX}tau> {nq_literal(tb.build(qid))} <{g}> .")
    return "\n".join(lines) + "\n", len(lines), g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="cartella del set, es. data/films/dev")
    ap.add_argument("--cfg", required=True, help="configurazione di τ, es. prompts/tau_t0_v1.json")
    ap.add_argument("--repo", required=True, help="repository GraphDB SENZA statement nascoste, es. films-dev")
    ap.add_argument("--out", default="rdf", help="cartella dove salvare il file .nq (non va su Git se grande)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.repo.endswith("-gt"):
        raise SystemExit("Rifiuto: τ va nei repository senza statement nascoste (quelli su cui girano le query semantiche).")
    if Path(a.data).name not in a.repo:
        print(f"ATTENZIONE: dati '{a.data}' e repository '{a.repo}' non sembrano dello stesso set (dev/eval).")

    body, n, g = build_nquads(a.data, a.cfg)
    out = Path(a.out) / f"{Path(a.cfg).stem}_{Path(a.data).name}.nq"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"{n} triple ex:tau nel graph <{g}>; file: {out}")
    print("Esempio:", body.splitlines()[0][:300])
    if a.dry_run:
        return

    load_dotenv(find_dotenv(usecwd=True))
    base = os.environ.get("GRAPHDB_URL", "http://localhost:7200").rstrip("/")
    url = f"{base}/repositories/{a.repo}/statements"
    ctx = quote(f"<{g}>", safe="")

    r = httpx.delete(f"{url}?context={ctx}", timeout=120)          # svuota solo questo named graph
    r.raise_for_status()
    r = httpx.post(url, content=body.encode("utf-8"),
                   headers={"Content-Type": "application/n-quads; charset=utf-8"}, timeout=600)
    r.raise_for_status()

    # Controllo: quante entità del set hanno τ nel graph, e che il testo letto sia identico a quello scritto.
    def ask(q):
        resp = httpx.get(f"{base}/repositories/{a.repo}", params={"query": q},
                         headers={"Accept": "application/sparql-results+json"}, timeout=120)
        resp.raise_for_status()
        return resp.json()["results"]["bindings"]

    tot = ask(f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{g}> {{ ?e <{EX}tau> ?t }} }}")[0]["n"]["value"]
    main_n = ask(f"PREFIX ex: <{EX}> SELECT (COUNT(DISTINCT ?e) AS ?n) WHERE {{ ?e ex:inSet ex:set-main . "
                 f"GRAPH <{g}> {{ ?e ex:tau ?t }} }}")[0]["n"]["value"]
    sets = pd.read_csv(Path(a.data) / "sets.csv")
    atteso = int((sets.set_id == "main").sum())
    print(f"Nel graph: {tot} triple (attese {n}). Entità del main set con τ: {main_n} (attese {atteso}).")
    if int(main_n) != atteso:
        print("ERRORE: le entità del grafo non coincidono con quelle di τ (controllare gli IRI wd:Q...).")
        raise SystemExit(1)

    tb = TauBuilder(a.data, load_cfg(a.cfg))
    q0 = tb.ent.index[0]
    letto = ask(f"SELECT ?t WHERE {{ GRAPH <{g}> {{ <{WD}{q0}> <{EX}tau> ?t }} }}")[0]["t"]["value"]
    print("Testo riletto identico a quello costruito:", letto == tb.build(q0))


if __name__ == "__main__":
    main()
