"""Studio di τ: confronta le varianti sul dev set contro la chiave di Q1 (o Q2).

Uso (dalla radice del repository):
    # 1. prova senza chiamare il modello: testi, token, un esempio per variante
    python -m src.tau_study --data data/films/dev --dry-run
    # 2. prova veloce con il modello locale su pochi film
    python -m src.tau_study --data data/films/dev --backend local --limit 30
    # 3. run completo (1000 film x varianti)
    python -m src.tau_study --data data/films/dev --backend local
    python -m src.tau_study --data data/films/dev --backend google --yes

Regole: gira solo sul dev set (rifiuta l'eval); prompt e temperatura sono fissi; le varianti si
confrontano sugli stessi film, con un bootstrap appaiato. Non si tara nulla sull'eval set.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data_observations import KW, load_key, load_main_qids
from .tau import TauBuilder, load_cfg, token_stats

VARIANTS = ["t0", "t1", "t2", "t3", "t4"]


def find_cfg(prompts_dir: Path, name: str) -> Path:
    files = sorted(glob.glob(str(prompts_dir / f"tau_{name}_v*.json")),
                   key=lambda p: int(re.search(r"_v(\d+)\.json$", p).group(1)))
    if not files:
        raise FileNotFoundError(f"nessuna configurazione tau_{name}_v*.json in {prompts_dir}")
    return Path(files[-1])  # l'ultima versione


def prf(pred: np.ndarray, truth: np.ndarray):
    tp = int((pred & truth).sum())
    fp = int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return tp, fp, fn, p, r, f


def f1_vec(pred, truth):
    tp = (pred & truth).sum(axis=-1)
    fp = (pred & ~truth).sum(axis=-1)
    fn = (~pred & truth).sum(axis=-1)
    den = 2 * tp + fp + fn
    return np.where(den > 0, 2 * tp / np.maximum(den, 1), 0.0)


def paired_bootstrap(pred_a, pred_b, truth, B=1000, seed=0):
    """Differenza di F1 (b - a) sugli stessi film, con intervallo al 95%."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(truth), size=(B, len(truth)))
    d = f1_vec(pred_b[idx], truth[idx]) - f1_vec(pred_a[idx], truth[idx])
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--query", default="Q1", choices=["Q1", "Q2"])
    ap.add_argument("--variants", nargs="+", default=VARIANTS)
    ap.add_argument("--backend", choices=["local", "google"], default="local")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--limit", type=int, help="usa solo N film (campione casuale con seme fisso)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="conferma i run a pagamento")
    ap.add_argument("--out", default="eval")
    ap.add_argument("--cache", default="cache/study_cache.jsonl")
    a = ap.parse_args()

    data = Path(a.data)
    if "eval" in [p.lower() for p in data.parts]:
        raise SystemExit("Rifiuto: lo studio di τ si fa solo sul dev set (mai sull'eval).")

    prompts = Path(a.prompts)
    fp = json.loads((prompts / "filter_v1.json").read_text(encoding="utf-8"))
    langex = fp["criteria"][a.query]

    qids = load_main_qids(data)
    if a.limit:
        rng = np.random.default_rng(0)
        qids = sorted(rng.choice(qids, size=min(a.limit, len(qids)), replace=False))
    key = load_key(data / "gt" / f"{a.query.lower()}.csv")
    truth = np.array([key.get(q, (False, False))[0] for q in qids])
    truth_direct = np.array([key.get(q, (False, False))[1] for q in qids])
    print(f"{a.query}: {len(qids)} film, positivi (chiave espansa) {int(truth.sum())}, diretti {int(truth_direct.sum())}")

    base = TauBuilder(data, {"max_chars": None})
    kw = KW.get(a.query)
    explicit = np.array([bool(kw.search(base.build(q))) if kw else False for q in qids])

    texts, builders = {}, {}
    for v in a.variants:
        cfg_path = find_cfg(prompts, v)
        builders[v] = TauBuilder(data, load_cfg(str(cfg_path)))
        texts[v] = [builders[v].build(q) for q in qids]
        print(f"{v}: {cfg_path.name}")

    # controllo automatico di leakage per le varianti con proprietà del grafo: il testo AGGIUNTO non deve contenere
    # il valore di una proprietà nascosta dello stesso film. Confronto a parola intera, senza distinguere le maiuscole.
    hidden_path = data / "hidden_statements.csv"
    for v in a.variants:
        if builders[v].cfg["extra_props"] and hidden_path.exists():
            h = pd.read_csv(hidden_path, usecols=["qid", "property", "value_label"]).dropna()
            hid: dict = {}
            for r in h.itertuples():
                hid.setdefault(r.qid, []).append((r.property, str(r.value_label)))
            cases = []
            for q in qids:
                extra = builders[v].extra_text(q)
                for prop, lab in hid.get(q, []):
                    if extra and re.search(r"(?<!\w)" + re.escape(lab) + r"(?!\w)", extra, re.I):
                        cases.append({"qid": q, "film": builders[v].ent.loc[q, "label"], "proprieta_nascosta": prop,
                                      "valore_nascosto": lab, "testo_aggiunto": extra[:150]})
            print(f"{v}: leakage automatico nel testo aggiunto: {len({c['qid'] for c in cases})} film su {len(qids)} (atteso 0)")
            for c in cases[:10]:
                print(f"    {c['qid']} | {c['film']} | {c['proprieta_nascosta']} = {c['valore_nascosto']!r} | testo aggiunto: {c['testo_aggiunto']!r}")
            if cases:
                Path(a.out).mkdir(parents=True, exist_ok=True)
                pd.DataFrame(cases).to_csv(Path(a.out) / f"tau_study_leakage_{v}.csv", index=False)

    if a.dry_run:
        for v in a.variants:
            ts = token_stats(texts[v])
            print(f"\n=== {v}: token medi {ts['mean']:.1f}, p90 {ts['p90']:.0f}" + (" [stima]" if ts["approx"] else ""))
            print(texts[v][0][:500])
        return

    from .llm_client import LLMClient

    client = LLMClient(a.backend, cache_path=a.cache)
    instr = fp["instructions"]
    users = {v: [fp["template"].format(langex=langex, tau=t) for t in texts[v]] for v in a.variants}
    todo = sum(not client.is_cached(instr, u) for v in a.variants for u in users[v])
    print(f"Richieste nuove (non in cache): {todo} su {len(a.variants) * len(qids)}")
    if a.backend == "google" and todo and not a.yes:
        approx_tok = sum(len(u) for v in a.variants for u in users[v]) // 4
        raise SystemExit(f"Backend a pagamento: circa {approx_tok:,} token in ingresso. Rilancia con --yes per eseguire.")

    if truth.sum() < 30:
        print(f"ATTENZIONE: solo {int(truth.sum())} positivi. Con così pochi positivi le differenze tra varianti "
              "non sono interpretabili: serve solo a provare che la catena funziona.")

    t_all = time.time()
    results, rows, decisions, valid_mask = {}, [], {"qid": qids, "truth": truth}, {}
    for v in a.variants:
        res = client.ask_many([(instr, u) for u in users[v]], workers=a.workers, label=v)
        results[v] = res
        valid = np.array([not r["parse_failure"] for r in res])
        # Un parse failure NON è una risposta e non diventa un negativo: le metriche principali usano
        # solo le risposte valide. Il caso "fallimento = no" è riportato a parte, con il suo nome.
        pred = np.array([bool(r["answer"]) if not r["parse_failure"] else False for r in res])
        valid_mask[v] = valid
        pf = int((~valid).sum())
        tp, fpn, fn, p, r_, f = prf(pred[valid], truth[valid])
        _, _, _, _, _, f_dir = prf(pred[valid], truth_direct[valid])
        _, _, _, _, _, f_pess = prf(pred, truth)
        ts = token_stats(texts[v])
        tin = [r["tokens_in"] for r in res if r["tokens_in"] is not None]
        tout = [r["tokens_out"] for r in res if r["tokens_out"] is not None]
        secs = [r["seconds"] for r in res if not r["cached"] and r.get("seconds") is not None]
        pv, tv, ev = pred[valid], truth[valid], explicit[valid]
        decisions[v] = np.where(valid, pred, np.nan)
        rows.append({
            "variante": v, "modello": f"{client.model} [{client.format_name}{'' if client.thinking else ', no-think'}, max_tokens={client.max_tokens}]", "n": len(qids), "n_validi": int(valid.sum()),
            "parse_failures": pf, "quota_fallimenti": round(pf / len(qids), 3),
            "tp": tp, "fp": fpn, "fn": fn,
            "precision": round(p, 3), "recall": round(r_, 3), "f1": round(f, 3),
            "f1_fallimenti_come_no": round(f_pess, 3), "f1_chiave_diretta": round(f_dir, 3),
            "recall_espliciti": round(float((pv & tv & ev).sum() / max((tv & ev).sum(), 1)), 3) if kw else None,
            "recall_impliciti": round(float((pv & tv & ~ev).sum() / max((tv & ~ev).sum(), 1)), 3) if kw else None,
            "token_tau_medi": round(ts["mean"], 1), "token_tau_p90": round(ts["p90"]),
            "token_ingresso_reali_medi": round(float(np.mean(tin)), 1) if tin else None,
            "token_uscita_medi": round(float(np.mean(tout)), 1) if tout else None,
            "secondi_per_richiesta": round(float(np.mean(secs)), 2) if secs else None,
        })
        bad = [r for r in res if r["parse_failure"]]
        if bad:
            fin = {}
            for r in bad:
                fin[r.get("finish_reason")] = fin.get(r.get("finish_reason"), 0) + 1
            print(f"  {v}: {pf} risposte non valide su {len(qids)}. Motivo di arresto (finish_reason): {fin}. "
                  f"Esempi grezzi: {[r['raw'] for r in bad[:3]]}")

    # riferimento economico: filtro per parola chiave sul testo di t0
    if kw and "t0" in texts:
        pk = np.array([bool(kw.search(t)) for t in texts["t0"]])
        _, _, _, p, r_, f = prf(pk, truth)
        rows.append({"variante": "parola-chiave (su t0)", "modello": "-", "n": len(qids), "n_validi": len(qids),
                     "precision": round(p, 3), "recall": round(r_, 3), "f1": round(f, 3)})

    if "t0" in decisions:
        for row in rows:
            v = row["variante"]
            if v in decisions and v != "t0":
                both = valid_mask["t0"] & valid_mask[v]   # solo i film con risposta valida in entrambe le varianti
                a0 = np.nan_to_num(decisions["t0"]).astype(bool)[both]
                av = np.nan_to_num(decisions[v]).astype(bool)[both]
                m, lo, hi = paired_bootstrap(a0, av, truth[both])
                row.update({"n_confronto": int(both.sum()), "f1_diff_vs_t0": round(m, 3),
                            "ic95_basso": round(lo, 3), "ic95_alto": round(hi, 3),
                            "dentro_il_rumore": lo <= 0 <= hi, "differenza_sotto_1_punto": abs(m) < 0.01})

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.query.lower()}_{a.backend}"
    df = pd.DataFrame(rows)
    df.to_csv(out / f"tau_study_{tag}.csv", index=False)
    pd.DataFrame(decisions).to_csv(out / f"tau_study_{tag}_decisioni.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print("\n" + df.to_string(index=False))
    print(f"\nTempo totale: {(time.time() - t_all) / 60:.1f} minuti. Richieste nuove: {client.new_requests}. File: {out / f'tau_study_{tag}.csv'} e ..._decisioni.csv")


if __name__ == "__main__":
    main()