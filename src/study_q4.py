"""Studio di τ per Q4 (sem_classify): quale variante di τ classifica meglio il genere dei film.

Uso (dalla radice del repository):
    # 1. prova senza modello: testi, token, prompt di esempio e riferimento "nome del genere nel testo"
    python -m src.study_q4 --data data/films/dev --dry-run
    # 2. prova veloce su pochi film (modello: GATEWAY_MODEL nel .env; gateway avviato)
    python -m src.study_q4 --data data/films/dev --limit 30 --variants t0 --run-id prova-q4
    # 3. run completo (839 film x varianti); con una rotta cloud serve anche --yes
    python -m src.study_q4 --data data/films/dev --variants t0 s1 s2 --run-id tau-q4 --out eval/tau_q4 --workers 4

Metriche (dal documento delle query comuni, Q4):
  hit rate        su tutti gli input: la risposta è UNA delle etichette vere del film (i film possono averne più d'una)
  accuracy        solo sui film con una sola etichetta vera (527 nel dev)
  macro-F1        sugli stessi film a etichetta singola, media non pesata delle F1 delle otto classi
Una risposta fuori dall'elenco delle otto etichette è un errore (fuori_insieme), contato a parte rispetto
ai parse failure. I parse failure non sono risposte: le metriche principali usano solo le risposte valide,
e la colonna *_fallimenti_come_errore li conta come sbagliati.

Regole come in tau_study: solo dev set, prompt e temperatura fissi, confronto appaiato sugli stessi film.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data_observations import _qid
from .tau import TauBuilder, load_cfg, token_stats
from .tau_study import find_cfg


def load_q4(data: Path) -> tuple[list[str], dict[str, set[str]]]:
    sets = pd.read_csv(data / "sets.csv")
    qids = sorted(sets[sets.set_id == "q4_input"].qid.map(_qid))
    gt = pd.read_csv(data / "gt" / "q4.csv")
    idc = "qid" if "qid" in gt.columns else gt.columns[0]
    key = {_qid(r[idc]): {_qid(x) for x in str(r["labels"]).split("|") if x} for _, r in gt.iterrows()}
    missing = [q for q in qids if q not in key]
    if missing:
        print(f"ATTENZIONE: {len(missing)} input di q4_input senza riga in gt/q4.csv (es. {missing[:3]})")
    return qids, key


def macro_f1(pred: np.ndarray, truth: np.ndarray, classes: list[str]) -> float:
    """pred e truth: array di QID (pred può contenere "" per fuori insieme). Media delle F1 per classe."""
    fs = []
    for c in classes:
        tp = np.sum((pred == c) & (truth == c))
        fp = np.sum((pred == c) & (truth != c))
        fn = np.sum((pred != c) & (truth == c))
        den = 2 * tp + fp + fn
        fs.append(2 * tp / den if den else 0.0)
    return float(np.mean(fs))


def bootstrap_diff(fn, a, b, truth, B=1000, seed=0):
    """Differenza fn(b) - fn(a) sugli stessi film ricampionati, con intervallo al 95%."""
    rng = np.random.default_rng(seed)
    n = len(truth)
    d = np.empty(B)
    for i in range(B):
        idx = rng.integers(0, n, n)
        d[i] = fn(b[idx], truth[idx]) - fn(a[idx], truth[idx])
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def name_in_text_baseline(texts: list[str], labels: dict[str, str]) -> list[str]:
    """Riferimento gratuito: la prima etichetta il cui nome compare nel testo ("comedy", "horror", "war film"...).
    Misura quanto la risposta è già scritta in τ, come la parola chiave per Q1."""
    stems = {}
    for q, name in labels.items():
        stem = name[:-5] if name.endswith(" film") and name != "war film" else name
        stems[q] = re.compile(r"(?<!\w)" + re.escape(stem) + r"(?!\w)", re.I)
    out = []
    for t in texts:
        best, pos = "", len(t) + 1
        for q, rx in stems.items():
            m = rx.search(t)
            if m and m.start() < pos:
                best, pos = q, m.start()
        out.append(best)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--variants", nargs="+", default=["t0"])
    ap.add_argument("--run-id", help="run_id nel registro del gateway (predefinito: GATEWAY_RUN_ID o data e ora)")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--prompt-file", default="classify_v1.json")
    ap.add_argument("--limit", type=int, help="usa solo N film (campione casuale con seme fisso)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="conferma i run su una rotta cloud (a pagamento)")
    ap.add_argument("--out", default="eval")
    a = ap.parse_args()

    data = Path(a.data)
    if "eval" in [p.lower() for p in data.parts]:
        raise SystemExit("Rifiuto: lo studio di τ si fa solo sul dev set (mai sull'eval).")

    prompts = Path(a.prompts)
    cp = json.loads((prompts / a.prompt_file).read_text(encoding="utf-8"))
    langex = cp["criteria"]["Q4"]
    labels = cp["labels"]["Q4"]                 # {QID: nome}
    classes = list(labels)
    names = [labels[q] for q in classes]
    name2qid = {n: q for q, n in labels.items()}

    qids, key = load_q4(data)
    if a.limit:
        rng = np.random.default_rng(0)
        qids = sorted(rng.choice(qids, size=min(a.limit, len(qids)), replace=False))
    truth_sets = [key.get(q, set()) for q in qids]
    single = np.array([len(s) == 1 for s in truth_sets])
    truth1 = np.array([next(iter(s)) if len(s) == 1 else "" for s in truth_sets])
    unknown = {x for s in truth_sets for x in s} - set(classes)
    if unknown:
        raise SystemExit(f"gt/q4.csv contiene etichette fuori dall'elenco del prompt: {sorted(unknown)}")
    dist = pd.Series(truth1[single]).map(labels).value_counts()
    print(f"Q4: {len(qids)} film, {int(single.sum())} con una sola etichetta. Distribuzione (etichetta singola):")
    print("  " + ", ".join(f"{k} {v}" for k, v in dist.items()))

    texts, builders = {}, {}
    for v in a.variants:
        cfg_path = find_cfg(prompts, v)
        builders[v] = TauBuilder(data, load_cfg(str(cfg_path)))
        texts[v] = [builders[v].build(q) for q in qids]
        print(f"{v}: {cfg_path.name}")

    instr = cp["instructions"]
    users = {v: [cp["template"].format(langex=langex, labels=", ".join(names), tau=t) for t in texts[v]]
             for v in a.variants}

    def score(pred_q: np.ndarray, valid: np.ndarray) -> dict:
        hit = np.array([p in s for p, s in zip(pred_q, truth_sets)])
        sv = single & valid
        return {
            "hit_rate": round(float(hit[valid].mean()), 3) if valid.any() else None,
            "hit_rate_fallimenti_come_errore": round(float(hit.mean()), 3),
            "accuracy": round(float((pred_q[sv] == truth1[sv]).mean()), 3) if sv.any() else None,
            "macro_f1": round(macro_f1(pred_q[sv], truth1[sv], classes), 3) if sv.any() else None,
        }

    rows, per_class, decisions = [], [], {"qid": qids, "labels": ["|".join(sorted(s)) for s in truth_sets]}

    # riferimento gratuito sul testo della prima variante
    v0 = a.variants[0]
    base_pred = np.array(name_in_text_baseline(texts[v0], labels))
    allv = np.ones(len(qids), bool)
    rows.append({"variante": f"nome-del-genere-nel-testo (su {v0})", "modello": "-", "n": len(qids),
                 "n_validi": len(qids), "copertura": round(float((base_pred != "").mean()), 3),
                 **score(base_pred, allv)})

    if a.dry_run:
        for v in a.variants:
            ts = token_stats(users[v])
            print(f"\n=== {v}: token del messaggio utente medi {ts['mean']:.1f}, p90 {ts['p90']:.0f}"
                  + (" [stima]" if ts["approx"] else ""))
            print(users[v][0][:600])
        print("\n" + pd.DataFrame(rows).to_string(index=False))
        return

    from .llm_client import LLMClient

    client = LLMClient(run_id=a.run_id)
    todo = len(a.variants) * len(qids)
    print(f"Richieste al gateway: {todo} (run_id {client.run_id}). Quelle già nella sua cache non arrivano al modello.")
    if client.paid and not a.yes:
        approx_tok = sum(len(u) for v in a.variants for u in users[v]) // 4
        raise SystemExit(f"{client.model} è una rotta a pagamento: circa {approx_tok:,} token in ingresso. Rilancia con --yes per eseguire.")

    t_all = time.time()
    preds, valids = {}, {}
    for v in a.variants:
        res = client.ask_many([(instr, u) for u in users[v]], workers=a.workers, label=v, choices=names)
        valid = np.array([not r["parse_failure"] for r in res])
        pred_q = np.array([name2qid.get(r["answer"], "") if not r["parse_failure"] else "" for r in res])
        oos = int(sum(bool(r.get("out_of_set")) for r in res))
        preds[v], valids[v] = pred_q, valid
        decisions[v] = [labels.get(p, "") if ok else "" for p, ok in zip(pred_q, valid)]
        ts = token_stats(texts[v])
        tin = [r["tokens_in"] for r in res if r["tokens_in"] is not None]
        tout = [r["tokens_out"] for r in res if r["tokens_out"] is not None]
        secs = [r["seconds"] for r in res if r.get("seconds") is not None]   # comprese le risposte dalla cache del gateway
        rows.append({
            "variante": v,
            "modello": client.model,
            "n": len(qids), "n_validi": int(valid.sum()), "parse_failures": int((~valid).sum()),
            "fuori_insieme": oos, **score(pred_q, valid),
            "token_tau_medi": round(ts["mean"], 1), "token_tau_p90": round(ts["p90"]),
            "token_ingresso_reali_medi": round(float(np.mean(tin)), 1) if tin else None,
            "token_uscita_medi": round(float(np.mean(tout)), 1) if tout else None,
            "secondi_per_richiesta": round(float(np.mean(secs)), 2) if secs else None,
        })
        sv = single & valid
        for c in classes:
            t = truth1[sv] == c
            p = pred_q[sv] == c
            per_class.append({"variante": v, "classe": labels[c], "film": int(t.sum()),
                              "predetti": int(p.sum()), "corretti": int((t & p).sum()),
                              "recall": round(float((t & p).sum() / t.sum()), 3) if t.sum() else None,
                              "precision": round(float((t & p).sum() / p.sum()), 3) if p.sum() else None})
        bad = [r for r in res if r["parse_failure"]]
        if bad:
            print(f"  {v}: {len(bad)} risposte non valide. Esempi grezzi: {[r['raw'] for r in bad[:3]]}")

    if "t0" in preds:
        for row in rows:
            v = row["variante"]
            if v in preds and v != "t0":
                both = single & valids["t0"] & valids[v]
                acc = lambda p, t: float((p == t).mean())
                mf = lambda p, t: macro_f1(p, t, classes)
                m, lo, hi = bootstrap_diff(acc, preds["t0"][both], preds[v][both], truth1[both])
                m2, lo2, hi2 = bootstrap_diff(mf, preds["t0"][both], preds[v][both], truth1[both])
                row.update({"n_confronto": int(both.sum()),
                            "accuracy_diff_vs_t0": round(m, 3), "acc_ic95": f"[{lo:.3f}, {hi:.3f}]",
                            "acc_dentro_il_rumore": lo <= 0 <= hi,
                            "macro_f1_diff_vs_t0": round(m2, 3), "mf1_ic95": f"[{lo2:.3f}, {hi2:.3f}]",
                            "mf1_dentro_il_rumore": lo2 <= 0 <= hi2})

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = "q4"
    df = pd.DataFrame(rows)
    df.to_csv(out / f"tau_study_{tag}.csv", index=False)
    pd.DataFrame(per_class).to_csv(out / f"tau_study_{tag}_per_classe.csv", index=False)
    pd.DataFrame(decisions).to_csv(out / f"tau_study_{tag}_decisioni.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print("\n" + df.to_string(index=False))
    print("\nPer classe (film a etichetta singola):")
    print(pd.DataFrame(per_class).to_string(index=False))
    print(f"\nTempo totale: {(time.time() - t_all) / 60:.1f} minuti. Richieste al gateway: {client.requests}. "
          f"File in {out}: tau_study_{tag}.csv, ..._per_classe.csv, ..._decisioni.csv")

if __name__ == "__main__":
    main()