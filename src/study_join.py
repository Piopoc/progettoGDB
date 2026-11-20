"""Studio di τ e del blocking per i join (Q6, e Q7 facoltativa): "the film is based on the novel".

Tre usi, dal più economico al più costoso (dalla radice del repository):

    # 1. prova senza modello: testi, token, numero di richieste per piano
    python -m src.study_join --data data/films/dev --query Q6 --dry-run

    # 2. solo blocking, ZERO richieste al modello: per ogni film i k romanzi più simili (embedding),
    #    e quante coppie vere restano tra i candidati per k = 1, 3, 5, 10, 20, 50
    python -m src.study_join --data data/films/dev --query Q6 --blocking-only --variants t0 t3 t6

    # 3. join con il modello
    #    piano di riferimento (nested loop, tutte le 50 x 100 = 5000 coppie: ore in locale)
    python -m src.study_join --data data/films/dev --query Q6 --plan nested --variants t0 --run-id q6-nested
    #    piano con blocking (k romanzi per film: 50 x 10 = 500 richieste), confrontato anche con il riferimento
    python -m src.study_join --data data/films/dev --query Q6 --plan topk --k 10 --variants t0 --run-id q6-topk10 \
        --reference eval/q6_qwen3b/join_q6_nested_decisioni.csv

Metriche (documento delle query comuni, Q6): precision, recall e F1 contro la chiave e contro il run di
riferimento. La recall è sempre calcolata su TUTTE le coppie vere, anche quelle perse dal blocking.
I parse failure non sono risposte: le metriche usano le risposte valide, *_fallimenti_come_no li conta come "no".

L'embedding (BAAI/bge-small-en-v1.5) usa il pacchetto fastembed: pip install fastembed==0.9.1.
Al primo uso scarica il modello (circa 130 MB). I vettori sono salvati in cache/emb/ e non si ricalcolano.
Il blocking si calibra SOLO sul dev set; sull'eval si usa il k scelto qui.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data_observations import _qid
from .tau import TauBuilder, load_cfg, token_stats
from .tau_study import find_cfg

KS = [1, 3, 5, 10, 20, 50]
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


# --- dati ------------------------------------------------------------------------------------
def load_join(data: Path, query: str, sets_cfg: dict):
    left_set, right_set = sets_cfg[query]
    sets = pd.read_csv(data / "sets.csv")
    left = sorted(sets[sets.set_id == left_set].qid.map(_qid))
    right = sorted(sets[sets.set_id == right_set].qid.map(_qid))
    gt = pd.read_csv(data / "gt" / f"{query.lower()}.csv")
    lc, rc = ("left", "right") if {"left", "right"} <= set(gt.columns) else gt.columns[:2]
    key = {(_qid(l), _qid(r)) for l, r in zip(gt[lc], gt[rc])}
    lset, rset = set(left), set(right)
    outside = [p for p in key if p[0] not in lset or p[1] not in rset]
    if outside:
        print(f"ATTENZIONE: {len(outside)} coppie della chiave fuori dai due insiemi (es. {outside[:2]})")
    return left, right, key


# --- embedding e blocking ----------------------------------------------------------------------
def embed(texts: list[str], model: str, cache_dir: Path) -> np.ndarray:
    h = hashlib.sha256(json.dumps([model, texts], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    path = cache_dir / f"{model.replace('/', '_')}_{h}.npy"
    if path.exists():
        return np.load(path)
    try:
        from fastembed import TextEmbedding
    except ImportError:
        raise SystemExit("Manca fastembed. Installa con: pip install fastembed==0.9.1")
    vecs = np.array(list(TextEmbedding(model_name=model).embed(texts)), dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(path, vecs)
    return vecs


def rank_right(lv: np.ndarray, rv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per ogni elemento di sinistra: indici di destra in ordine di similarità decrescente, e le similarità."""
    sim = lv @ rv.T
    order = np.argsort(-sim, axis=1, kind="stable")
    return order, sim


def blocking_table(v, left, right, key, order, ks):
    pos = {}   # rango (1 = il più simile) della destra vera, per ogni coppia della chiave
    li, ri = {q: i for i, q in enumerate(left)}, {q: i for i, q in enumerate(right)}
    for l, r in key:
        if l in li and r in ri:
            pos[(l, r)] = int(np.where(order[li[l]] == ri[r])[0][0]) + 1
    ranks = np.array(list(pos.values()))
    rows = []
    for k in ks:
        k_eff = min(k, len(right))
        rows.append({"variante": v, "k": k_eff, "coppie_candidate": k_eff * len(left),
                     "coppie_vere": len(key), "coppie_vere_tra_i_candidati": int((ranks <= k_eff).sum()),
                     "recall_blocking": round(float((ranks <= k_eff).sum() / len(key)), 3),
                     "frazione_del_nested_loop": round(k_eff / len(right), 3)})
    return rows, pos


# --- metriche --------------------------------------------------------------------------------
def prf_sets(pred: set, truth: set):
    tp = len(pred & truth)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(truth) if truth else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return tp, len(pred) - tp, len(truth) - tp, p, r, f


def bootstrap_f1_by_left(pred_a: set, pred_b: set, truth: set, left: list[str], B=1000, seed=0):
    """Differenza di F1 (b - a) ricampionando i film di sinistra (le coppie dello stesso film restano insieme)."""
    rng = np.random.default_rng(seed)
    by = lambda s: {l: {p for p in s if p[0] == l} for l in left}
    A, Bp, T = by(pred_a), by(pred_b), by(truth)
    d = np.empty(B)
    for i in range(B):
        idx = rng.integers(0, len(left), len(left))
        tpa = fpa = fna = tpb = fpb = fnb = 0
        for j in idx:
            l = left[j]
            t = T[l]
            tpa += len(A[l] & t); fpa += len(A[l] - t); fna += len(t - A[l])
            tpb += len(Bp[l] & t); fpb += len(Bp[l] - t); fnb += len(t - Bp[l])
        fa = 2 * tpa / (2 * tpa + fpa + fna) if tpa + fpa + fna else 0.0
        fb = 2 * tpb / (2 * tpb + fpb + fnb) if tpb + fpb + fnb else 0.0
        d[i] = fb - fa
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def authors(data: Path) -> dict[str, set[str]]:
    p = data / "statements.csv"
    if not p.exists():
        return {}
    st = pd.read_csv(p, usecols=["qid", "property", "value"])
    st = st[st.property == "P50"]
    out: dict[str, set[str]] = {}
    for q, v in zip(st.qid, st.value):
        out.setdefault(_qid(q), set()).add(_qid(v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--query", default="Q6", choices=["Q6", "Q7"])
    ap.add_argument("--variants", nargs="+", default=["t0"])
    ap.add_argument("--plan", choices=["nested", "topk"], default="topk")
    ap.add_argument("--k", type=int, default=10, help="romanzi candidati per film nel piano topk")
    ap.add_argument("--blocking-only", action="store_true", help="solo la tabella del blocking, nessuna chiamata al modello")
    ap.add_argument("--embed-model", default=EMBED_MODEL)
    ap.add_argument("--reference", help="file _decisioni.csv di un run nested, per le metriche contro il riferimento")
    ap.add_argument("--run-id", help="run_id nel registro del gateway (predefinito: GATEWAY_RUN_ID o data e ora)")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--prompt-file", default="join_v1.json")
    ap.add_argument("--limit-left", type=int, help="usa solo N film di sinistra (campione con seme fisso); la destra resta intera")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="conferma i run su una rotta cloud (a pagamento)")
    ap.add_argument("--out", default="eval")
    ap.add_argument("--emb-cache", default="cache/emb")
    a = ap.parse_args()

    data = Path(a.data)
    if "eval" in [p.lower() for p in data.parts]:
        raise SystemExit("Rifiuto: lo studio si fa solo sul dev set (mai sull'eval).")

    prompts = Path(a.prompts)
    jp = json.loads((prompts / a.prompt_file).read_text(encoding="utf-8"))
    langex = jp["criteria"][a.query]
    left, right, key = load_join(data, a.query, jp["sets"])
    if a.limit_left:
        rng = np.random.default_rng(0)
        left = sorted(rng.choice(left, size=min(a.limit_left, len(left)), replace=False))
        key = {p for p in key if p[0] in set(left)}
    print(f"{a.query}: {len(left)} film x {len(right)} romanzi = {len(left) * len(right)} coppie, "
          f"{len(key)} coppie vere")

    texts_l, texts_r = {}, {}
    for v in a.variants:
        cfg_path = find_cfg(prompts, v)
        b = TauBuilder(data, load_cfg(str(cfg_path)))
        texts_l[v] = [b.build(q) for q in left]
        texts_r[v] = [b.build(q) for q in right]
        print(f"{v}: {cfg_path.name}")

    out = Path(a.out)
    tag = a.query.lower()
    n_calls = len(left) * (len(right) if a.plan == "nested" else min(a.k, len(right)))

    if a.dry_run:
        for v in a.variants:
            ex = jp["template"].format(langex=langex, left=texts_l[v][0], right=texts_r[v][0])
            ts = token_stats([jp["template"].format(langex=langex, left=l, right=r)
                              for l in texts_l[v][:20] for r in texts_r[v][:20]])
            print(f"\n=== {v}: token per richiesta (stima su 400 coppie) medi {ts['mean']:.1f}, p90 {ts['p90']:.0f}"
                  + (" [stima]" if ts["approx"] else ""))
            print(ex[:900])
        print(f"\nPiano {a.plan}" + (f" (k={a.k})" if a.plan == "topk" else "") + f": {n_calls} richieste per variante.")
        return

    # --- blocking (sempre calcolato se serve: per topk e per la tabella) ---------------------------
    orders, sims, blk_rows = {}, {}, []
    if a.blocking_only or a.plan == "topk":
        for v in a.variants:
            t0 = time.time()
            lv = embed(texts_l[v], a.embed_model, Path(a.emb_cache))
            rv = embed(texts_r[v], a.embed_model, Path(a.emb_cache))
            orders[v], sims[v] = rank_right(lv, rv)
            rows, pos = blocking_table(v, left, right, key, orders[v], KS)
            blk_rows += rows
            lost = sorted((r, l, rr) for (l, rr), r in pos.items() if r > a.k)
            print(f"{v}: embedding in {time.time() - t0:.1f} s. Coppie vere fuori dai primi {a.k}: {len(lost)}"
                  + (f" (ranghi: {[x[0] for x in lost]})" if lost else ""))
        out.mkdir(parents=True, exist_ok=True)
        bdf = pd.DataFrame(blk_rows)
        bdf.to_csv(out / f"join_{tag}_blocking.csv", index=False)
        pd.set_option("display.width", 250, "display.max_columns", 30)
        print("\nBlocking (" + a.embed_model + "), nessuna richiesta al modello:\n" + bdf.to_string(index=False))
        if a.blocking_only:
            print(f"\nFile: {out / f'join_{tag}_blocking.csv'}")
            return

    # --- join con il modello -------------------------------------------------------------------------
    from .llm_client import LLMClient

    client = LLMClient(run_id=a.run_id)
    instr = jp["instructions"]
    li = {q: i for i, q in enumerate(left)}
    plans = {}
    for v in a.variants:
        if a.plan == "nested":
            cand = [(i, j) for i in range(len(left)) for j in range(len(right))]
        else:
            cand = [(i, int(j)) for i in range(len(left)) for j in orders[v][i, :a.k]]
        plans[v] = cand
    users = {v: [jp["template"].format(langex=langex, left=texts_l[v][i], right=texts_r[v][j]) for i, j in plans[v]]
             for v in a.variants}
    todo = sum(len(u) for u in users.values())
    print(f"\nRichieste al gateway: {todo} (run_id {client.run_id}). Quelle già nella sua cache non arrivano al modello.")
    if client.paid and not a.yes:
        approx_tok = sum(len(u) for v in a.variants for u in users[v]) // 4
        raise SystemExit(f"{client.model} è una rotta a pagamento: circa {approx_tok:,} token in ingresso. Rilancia con --yes per eseguire.")
    if not client.paid and todo > 1000:
        print(f"ATTENZIONE: {todo} richieste a un modello locale: con 4 workers circa {todo / 40 / 60:.1f} ore.")

    ref = None
    if a.reference:
        rd = pd.read_csv(a.reference)
        ref_col = [c for c in rd.columns if c.startswith("answer_")]
        if len(ref_col) != 1:
            raise SystemExit(f"{a.reference}: serve un file di decisioni con una sola variante (colonne {ref_col})")
        ref = {(l, r) for l, r, x in zip(rd.left, rd.right, rd[ref_col[0]]) if x == 1}
        print(f"Riferimento: {a.reference} ({ref_col[0]}), {len(ref)} coppie positive")

    auth = authors(data)
    true_auth = {l: set().union(*[auth.get(r, set()) for (ll, r) in key if ll == l]) for l in left}

    t_all = time.time()
    rows, preds, dec_frames = [], {}, []
    for v in a.variants:
        res = client.ask_many([(instr, u) for u in users[v]], workers=a.workers, label=v)
        valid = np.array([not r["parse_failure"] for r in res])
        pairs = [(left[i], right[j]) for i, j in plans[v]]
        pred = {p for p, r in zip(pairs, res) if not r["parse_failure"] and r["answer"]}
        preds[v] = pred
        valid_pairs = {p for p, ok in zip(pairs, valid) if ok}
        # metriche principali: le coppie con risposta non valida escono dal conteggio di precision;
        # la recall resta su tutte le coppie vere (una coppia persa dal blocking o non valida è un mancato)
        key_valid = {p for p in key if p in valid_pairs or p not in set(pairs)}
        tp, fp, fn, p_, r_, f_ = prf_sets(pred, key_valid)
        _, _, _, _, _, f_pess = prf_sets(pred, key)
        fp_same_author = sum(1 for (l, r) in pred - key if auth.get(r, set()) & true_auth.get(l, set()))
        tin = [r["tokens_in"] for r in res if r["tokens_in"] is not None]
        tout = [r["tokens_out"] for r in res if r["tokens_out"] is not None]
        secs = [r["seconds"] for r in res if r.get("seconds") is not None]   # comprese le risposte dalla cache del gateway
        row = {"variante": v, "piano": a.plan + (f" k={a.k}" if a.plan == "topk" else ""),
               "modello": client.model,
               "richieste": len(pairs), "n_validi": int(valid.sum()), "parse_failures": int((~valid).sum()),
               "coppie_vere": len(key), "coppie_vere_tra_i_candidati": len(key & set(pairs)),
               "tp": tp, "fp": fp, "fn": fn, "precision": round(p_, 3), "recall": round(r_, 3), "f1": round(f_, 3),
               "f1_fallimenti_come_no": round(f_pess, 3),
               "fp_stesso_autore": fp_same_author if auth else None,
               "token_ingresso_reali_medi": round(float(np.mean(tin)), 1) if tin else None,
               "token_ingresso_totali": int(np.sum(tin)) if tin else None,
               "token_uscita_medi": round(float(np.mean(tout)), 1) if tout else None,
               "secondi_per_richiesta": round(float(np.mean(secs)), 2) if secs else None}
        if ref is not None:
            _, _, _, rp, rr, rf = prf_sets(pred, ref)
            row.update({"precision_vs_riferimento": round(rp, 3), "recall_vs_riferimento": round(rr, 3),
                        "f1_vs_riferimento": round(rf, 3)})
        rows.append(row)
        dec_frames.append(pd.DataFrame({
            "left": [p[0] for p in pairs], "right": [p[1] for p in pairs],
            "in_key": [int(p in key) for p in pairs],
            f"sim_{v}": [round(float(sims[v][i, j]), 4) for i, j in plans[v]] if v in sims else None,
            f"answer_{v}": [(int(bool(r["answer"])) if not r["parse_failure"] else None) for r in res]}))
        bad = [r for r in res if r["parse_failure"]]
        if bad:
            print(f"  {v}: {len(bad)} risposte non valide. Esempi grezzi: {[r['raw'] for r in bad[:3]]}")

    if "t0" in preds:
        for row in rows:
            v = row["variante"]
            if v != "t0":
                m, lo, hi = bootstrap_f1_by_left(preds["t0"], preds[v], key, left)
                row.update({"f1_diff_vs_t0": round(m, 3), "ic95": f"[{lo:.3f}, {hi:.3f}]",
                            "dentro_il_rumore": lo <= 0 <= hi})

    out.mkdir(parents=True, exist_ok=True)
    run_tag = f"{tag}_{a.plan}{a.k if a.plan == 'topk' else ''}"
    df = pd.DataFrame(rows)
    df.to_csv(out / f"join_{run_tag}.csv", index=False)
    dec = dec_frames[0]
    for d in dec_frames[1:]:
        dec = dec.merge(d, on=["left", "right", "in_key"], how="outer")
    dec.to_csv(out / f"join_{run_tag}_decisioni.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print("\n" + df.to_string(index=False))
    print(f"\nTempo totale: {(time.time() - t_all) / 60:.1f} minuti. Richieste al gateway: {client.requests}. "
          f"File: {out / f'join_{run_tag}.csv'} e ..._decisioni.csv")

if __name__ == "__main__":
    main()