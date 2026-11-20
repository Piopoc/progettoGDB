"""Analisi del testo del lead: DOVE sta l'informazione che serve alle query, e quanta ne resta dopo un taglio.

Nessuna chiamata al modello. Serve a scegliere (e motivare) le varianti di taglio di τ prima di spendere chiamate:
il taglio per caratteri (max_chars) e quello per frasi (max_sentences, varianti s1, s2, s3, s5).

Uso (dalla radice del repository):
    python -m src.lead_analysis --data data/films/dev
    python -m src.lead_analysis --data data/films/dev --compare data/films/eval      # + confronto descrittivo
    python -m src.lead_analysis --data data/films/dev --no-ner --no-embedding        # solo le parti senza modelli

Sezioni (file in --out, più un riassunto lead_analysis.md):
  1. lunghezze        caratteri, frasi e token del lead; quanti τ0 vengono tagliati; quanto testo tengono le prime N frasi
  2. posizioni        in quale frase compare per la prima volta l'informazione esplicita:
                        Q1  la guerra (stessa espressione regolare del riferimento "parola chiave"), sui positivi
                        Q4  il nome del genere vero (film a etichetta singola)
                        Q6  il titolo del romanzo da cui è tratto il film (coppie della chiave)
                      e la curva di "ritenzione": quota di menzioni che sopravvive a ogni taglio
  3. estrazione       information extraction con regole sulla prima frase: "X is a 1962 American spy film"
                      -> la frase descrittiva ("American spy"), e "based on the novel T by A" -> titolo e autore
  4. NER (spaCy)      entità per tipo e per posizione della frase: che cosa c'è nella frase 1, 2, 3, ...
  5. embedding        similarità tra ogni frase e il criterio di Q1 (bge-small-en-v1.5): in quale frase sta il
                      segnale, e quanto separa positivi e negativi (AUC) usando solo le prime N frasi

Le chiavi (gt/) si leggono SOLO sul dev. Con --compare si legge dell'altro insieme soltanto il testo (sezione 1):
è una descrizione, non serve a scegliere niente.

Dipendenze facoltative: spaCy con il modello inglese per la sezione 4
    pip install spacy==3.8.*  &&  python -m spacy download en_core_web_sm
e fastembed per la sezione 5 (già in requirements.txt). Se mancano, la sezione viene saltata e lo si dice.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .data_observations import KW, _qid, load_key
from .tau import TauBuilder, split_sentences

CHAR_CUTS = [300, 600, 900, 1200, 1800, None]
SENT_CUTS = [1, 2, 3, 5, None]
Q1_CRITERION = "the film deals with the Second World War"
GENRES = {"Q130232": "drama", "Q93204": "documentary", "Q369747": "war film", "Q188473": "action",
          "Q157443": "comedy", "Q2484376": "thriller", "Q200092": "horror", "Q471839": "science fiction"}


# --- utilità ------------------------------------------------------------------------------------
def md_table(df: pd.DataFrame, index: bool = True) -> str:
    """Tabella Markdown senza dipendenze (DataFrame.to_markdown richiederebbe il pacchetto tabulate)."""
    d = df.reset_index() if index else df
    cols = [" / ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in d.columns]
    fmt = lambda x: "" if pd.isna(x) else (f"{x:.3f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(x) for x in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join(lines)


def sentence_index(sents: list[str], rx: re.Pattern) -> int | None:
    """Indice (1 = prima frase) della prima frase che contiene rx, oppure None."""
    for i, s in enumerate(sents, 1):
        if rx.search(s):
            return i
    return None


def char_offset_in_tau(tau_full: str, rx: re.Pattern) -> int | None:
    m = rx.search(tau_full)
    return m.end() if m else None


def retention(sent_idx: list, char_end: list) -> list[dict]:
    """Quota delle menzioni che sopravvivono a ogni taglio (le menzioni assenti non contano)."""
    si = [x for x in sent_idx if x is not None]
    ce = [x for x in char_end if x is not None]
    rows = []
    for n in SENT_CUTS:
        rows.append({"taglio": f"prime {n} frasi" if n else "lead intero", "tipo": "frasi",
                     "menzioni_conservate": round(sum(1 for x in si if n is None or x <= n) / max(len(si), 1), 3)})
    for c in CHAR_CUTS:
        rows.append({"taglio": f"{c} caratteri" if c else "nessun taglio", "tipo": "caratteri",
                     "menzioni_conservate": round(sum(1 for x in ce if c is None or x <= c) / max(len(ce), 1), 3)})
    return rows


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Area sotto la curva ROC con i ranghi (Mann-Whitney): 0,5 = nessun segnale, 1 = separazione perfetta."""
    allv = np.concatenate([pos, neg])
    ranks = pd.Series(allv).rank().to_numpy()
    rp = ranks[: len(pos)].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def tok_len(texts: list[str]) -> list[int]:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return [len(enc.encode(t)) for t in texts]
    except Exception:
        return [max(1, round(len(t) / 4)) for t in texts]


# --- 1. lunghezze ---------------------------------------------------------------------------------
def lengths(data: Path, label: str) -> tuple[dict, pd.DataFrame]:
    sets = pd.read_csv(data / "sets.csv")
    qids = sorted(sets[sets.set_id == "main"].qid.map(_qid))
    full = TauBuilder(data, {"max_chars": None})
    t0 = TauBuilder(data, {})
    leads = [str(full.ent.loc[q, "lead"]) for q in qids]
    sents = [split_sentences(x) for x in leads]
    taus = [full.build(q) for q in qids]
    per = pd.DataFrame({"qid": qids, "lead_caratteri": [len(x) for x in leads],
                        "lead_frasi": [len(s) for s in sents], "lead_token": tok_len(leads),
                        "tau_intero_caratteri": [len(t) for t in taus]})
    row = {"insieme": label, "film": len(qids),
           "lead_caratteri_mediana": int(per.lead_caratteri.median()),
           "lead_caratteri_p90": int(per.lead_caratteri.quantile(0.9)),
           "lead_frasi_mediana": float(per.lead_frasi.median()),
           "lead_frasi_p90": float(per.lead_frasi.quantile(0.9)),
           "lead_token_media": round(float(per.lead_token.mean()), 1),
           "tau0_tagliati_a_1200": round(float((per.tau_intero_caratteri > 1200).mean()), 3)}
    for n in (1, 2, 3, 5):
        kept = [len(" ".join(s[:n])) / max(len(" ".join(s)), 1) for s in sents]
        row[f"testo_tenuto_prime_{n}_frasi"] = round(float(np.mean(kept)), 3)
    for c in (300, 600, 900):
        row[f"tau_tagliati_a_{c}"] = round(float((per.tau_intero_caratteri > c).mean()), 3)
    del t0
    return row, per


# --- 2. posizioni + 3. estrazione ----------------------------------------------------------------------
IS_A = re.compile(r"\bis (?:a|an) (?:\d{4} )?(?P<desc>[^.,;]{0,80}?)\b(?:film|documentary|movie)\b", re.I)
BASED_ON = re.compile(r"\b(?:based on|adapted from|adaptation of)\b(?P<rest>[^.]{0,160})", re.I)


def positions(data: Path) -> tuple[list[dict], list[dict], dict]:
    full = TauBuilder(data, {"max_chars": None})
    sets = pd.read_csv(data / "sets.csv")
    summary, curves, ie = [], [], {}

    def lead_of(q):
        return str(full.ent.loc[q, "lead"])

    # Q1: la guerra nei positivi (chiave espansa) e nei negativi
    main = sorted(sets[sets.set_id == "main"].qid.map(_qid))
    key1 = load_key(data / "gt" / "q1.csv")
    pos = [q for q in main if key1.get(q, (False, False))[0]]
    neg = [q for q in main if not key1.get(q, (False, False))[0]]
    kw = KW["Q1"]
    si = [sentence_index(split_sentences(lead_of(q)), kw) for q in pos]
    ce = [char_offset_in_tau(full.build(q), kw) for q in pos]
    neg_any = sum(1 for q in neg if kw.search(full.build(q)))
    summary.append({"query": "Q1", "cosa": "guerra nominata (positivi)", "insieme": len(pos),
                    "con_menzione": sum(x is not None for x in si),
                    "in_frase_1": sum(x == 1 for x in si), "in_frasi_1_2": sum(x is not None and x <= 2 for x in si),
                    "nota": f"nei {len(neg)} negativi la guerra è nominata in {neg_any}"})
    curves += [{"query": "Q1", **r} for r in retention(si, ce)]

    # Q4: nome del genere vero, film a etichetta singola
    gt4 = pd.read_csv(data / "gt" / "q4.csv")
    idc = "qid" if "qid" in gt4.columns else gt4.columns[0]
    single = [(_qid(r[idc]), _qid(r["labels"])) for _, r in gt4.iterrows() if "|" not in str(r["labels"])]
    si4, ce4 = [], []
    for q, g in single:
        rx = re.compile(r"(?<!\w)" + re.escape(GENRES[g]) + r"(?!\w)", re.I)
        si4.append(sentence_index(split_sentences(lead_of(q)), rx))
        ce4.append(char_offset_in_tau(full.build(q), rx))
    summary.append({"query": "Q4", "cosa": "nome del genere vero (etichetta singola)", "insieme": len(single),
                    "con_menzione": sum(x is not None for x in si4), "in_frase_1": sum(x == 1 for x in si4),
                    "in_frasi_1_2": sum(x is not None and x <= 2 for x in si4), "nota": ""})
    curves += [{"query": "Q4", **r} for r in retention(si4, ce4)]

    # estrazione dalla prima frase: "is a 1962 American spy film"
    hits, agree = 0, 0
    for q, g in single:
        first = (split_sentences(lead_of(q)) or [""])[0]
        m = IS_A.search(first)
        if m:
            hits += 1
            if GENRES[g].replace(" film", "") in m.group("desc").lower() or (g == "Q93204" and "documentary" in m.group(0).lower()):
                agree += 1
    ie["Q4_frase_is_a"] = {"film": len(single), "schema_trovato": hits, "genere_vero_nella_frase": agree}

    # Q6: titolo del romanzo nel lead del film
    p6 = data / "gt" / "q6.csv"
    if p6.exists():
        gt6 = pd.read_csv(p6)
        lc, rc = ("left", "right") if {"left", "right"} <= set(gt6.columns) else gt6.columns[:2]
        si6, ce6, based, based_title = [], [], 0, 0
        for l, r in zip(gt6[lc].map(_qid), gt6[rc].map(_qid)):
            title = str(full.ent.loc[r, "label"])
            rx = re.compile(r"(?<!\w)" + re.escape(title) + r"(?!\w)", re.I)
            sents = split_sentences(lead_of(l))
            # il titolo del film coincide spesso con quello del romanzo: si cerca dopo il titolo del film in testa
            film_title = str(full.ent.loc[l, "label"])
            body = [s.replace(film_title, "", 1) if i == 0 else s for i, s in enumerate(sents)]
            idx = sentence_index(body, rx)
            si6.append(idx)
            # posizione in caratteri dentro τ della STESSA menzione trovata per frasi (non del titolo del film
            # all'inizio del testo, che spesso coincide con quello del romanzo)
            if idx is None:
                ce6.append(None)
            else:
                tau_full, lead_l = full.build(l), lead_of(l)
                start_lead = tau_full.find(lead_l[:40]) if lead_l else -1
                start_sent = lead_l.find(sents[idx - 1])
                m = rx.search(body[idx - 1])
                shift = len(sents[idx - 1]) - len(body[idx - 1])      # titolo del film tolto dalla prima frase
                ce6.append(start_lead + start_sent + shift + m.end() if start_lead >= 0 and start_sent >= 0 else None)
            m = BASED_ON.search(lead_of(l))
            if m:
                based += 1
                based_title += bool(rx.search(m.group("rest")))
        summary.append({"query": "Q6", "cosa": "titolo del romanzo nel lead del film", "insieme": len(gt6),
                        "con_menzione": sum(x is not None for x in si6), "in_frase_1": sum(x == 1 for x in si6),
                        "in_frasi_1_2": sum(x is not None and x <= 2 for x in si6), "nota": ""})
        curves += [{"query": "Q6", **r} for r in retention(si6, ce6)]
        ie["Q6_based_on"] = {"coppie": len(gt6), "frase_based_on_trovata": based, "con_il_titolo_giusto": based_title}
    return summary, curves, ie


# --- 4. NER ------------------------------------------------------------------------------------
def ner(data: Path, max_sent: int = 6) -> pd.DataFrame | None:
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except Exception as e:
        print(f"Sezione NER saltata: {e}. Installa con: pip install 'spacy==3.8.*' && python -m spacy download en_core_web_sm")
        return None
    full = TauBuilder(data, {"max_chars": None})
    sets = pd.read_csv(data / "sets.csv")
    qids = sorted(sets[sets.set_id == "main"].qid.map(_qid))
    counts: dict = {}
    n_sent = np.zeros(max_sent)
    texts, pos_of = [], []
    for q in qids:
        for i, s in enumerate(split_sentences(str(full.ent.loc[q, "lead"]))[:max_sent]):
            texts.append(s)
            pos_of.append(i)
    for doc, i in zip(nlp.pipe(texts, batch_size=64), pos_of):
        n_sent[i] += 1
        for e in doc.ents:
            counts[(e.label_, i)] = counts.get((e.label_, i), 0) + 1
    labels = sorted({k[0] for k in counts}, key=lambda l: -sum(v for (ll, _), v in counts.items() if ll == l))
    rows = []
    for l in labels:
        row = {"entita": l}
        for i in range(max_sent):
            row[f"frase_{i + 1}"] = round(counts.get((l, i), 0) / max(n_sent[i], 1), 2)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.attrs["n_frasi"] = n_sent.astype(int).tolist()
    return df


# --- 5. embedding ----------------------------------------------------------------------------------
def embedding_signal(data: Path, model: str = "BAAI/bge-small-en-v1.5") -> tuple[pd.DataFrame, pd.DataFrame] | None:
    try:
        from fastembed import TextEmbedding
    except ImportError:
        print("Sezione embedding saltata: manca fastembed (pip install fastembed==0.9.1)")
        return None
    full = TauBuilder(data, {"max_chars": None})
    sets = pd.read_csv(data / "sets.csv")
    qids = sorted(sets[sets.set_id == "main"].qid.map(_qid))
    key1 = load_key(data / "gt" / "q1.csv")
    truth = np.array([key1.get(q, (False, False))[0] for q in qids])
    sents = [split_sentences(str(full.ent.loc[q, "lead"])) or [""] for q in qids]
    flat = [s for ss in sents for s in ss]
    try:
        emb = TextEmbedding(model_name=model)
    except Exception as e:
        print(f"Sezione embedding saltata: il modello {model} non si carica ({e}).")
        return None
    v = np.array(list(emb.embed(flat)), dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    c = np.array(list(emb.embed([Q1_CRITERION])), dtype=np.float32)[0]
    c /= np.linalg.norm(c)
    sims, k = [], 0
    for ss in sents:
        sims.append(v[k:k + len(ss)] @ c)
        k += len(ss)
    best = [int(np.argmax(s)) + 1 for s in sims]
    where = pd.Series([b for b, t in zip(best, truth) if t]).value_counts().sort_index()
    where_df = pd.DataFrame({"frase_piu_simile_al_criterio": where.index, "positivi": where.values})
    rows = []
    for n in SENT_CUTS:
        score = np.array([float(np.max(s[:n] if n else s)) for s in sims])
        rows.append({"segnale": f"max similarità nelle prime {n} frasi" if n else "max similarità nel lead intero",
                     "auc_positivi_vs_negativi": round(auc(score[truth], score[~truth]), 3)})
    return pd.DataFrame(rows), where_df


# --- main -----------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="il dev set (si leggono le chiavi)")
    ap.add_argument("--compare", help="un altro insieme, di cui si descrive SOLO il testo (sezione 1)")
    ap.add_argument("--out", default="eval/lead_analysis")
    ap.add_argument("--no-ner", action="store_true")
    ap.add_argument("--no-embedding", action="store_true")
    a = ap.parse_args()

    data = Path(a.data)
    if "eval" in [p.lower() for p in data.parts]:
        raise SystemExit("Rifiuto: le chiavi si leggono solo sul dev. Per l'eval usa --compare (solo testo).")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    md = ["# Analisi del lead", "", f"Dati: `{a.data}`" + (f", confronto descrittivo con `{a.compare}`" if a.compare else ""),
          "Divisione in frasi: `split_sentences` di `src/tau.py` (la stessa delle varianti s1, s2, s3, s5).", ""]

    row0, per = lengths(data, data.name)
    rows = [row0]
    per.to_csv(out / "lunghezze_per_film.csv", index=False)
    if a.compare:
        rows.append(lengths(Path(a.compare), Path(a.compare).name)[0])
    ldf = pd.DataFrame(rows).set_index("insieme").T
    ldf.to_csv(out / "lunghezze.csv")
    print("\n1. Lunghezze (insieme main)\n" + ldf.to_string())
    md += ["## 1. Lunghezze (insieme main)", "", md_table(ldf), ""]

    summary, curves, ie = positions(data)
    sdf, cdf = pd.DataFrame(summary), pd.DataFrame(curves)
    sdf.to_csv(out / "posizioni.csv", index=False)
    piv = cdf.pivot_table(index=["tipo", "taglio"], columns="query", values="menzioni_conservate", sort=False)
    piv.to_csv(out / "ritenzione.csv")
    print("\n2. Posizione della prima menzione esplicita\n" + sdf.to_string(index=False))
    print("\n   Quota di menzioni conservate per taglio\n" + piv.to_string())
    md += ["## 2. Dove compare l'informazione esplicita", "", md_table(sdf, index=False), "",
           "Quota delle menzioni che sopravvivono a ogni taglio (solo i film che la menzione ce l'hanno):", "",
           md_table(piv), ""]

    iedf = pd.DataFrame([{"regola": k, **v} for k, v in ie.items()])
    iedf.to_csv(out / "estrazione.csv", index=False)
    print("\n3. Estrazione con regole\n" + iedf.to_string(index=False))
    md += ["## 3. Estrazione con regole", "",
           "`is a [anno] <descrizione> film` nella prima frase (Q4) e `based on ... <titolo>` nel lead (Q6).", "",
           md_table(iedf, index=False), ""]

    if not a.no_ner:
        ndf = ner(data)
        if ndf is not None:
            ndf.to_csv(out / "ner_per_frase.csv", index=False)
            print(f"\n4. Entità per frase (media per frase; frasi analizzate per posizione: {ndf.attrs['n_frasi']})\n"
                  + ndf.to_string(index=False))
            md += ["## 4. Entità nominate per posizione della frase (spaCy en_core_web_sm)", "",
                   f"Numero medio di entità per frase; frasi per posizione: {ndf.attrs['n_frasi']}.", "",
                   md_table(ndf, index=False), ""]

    if not a.no_embedding:
        res = embedding_signal(data)
        if res is not None:
            edf, where = res
            edf.to_csv(out / "embedding_auc.csv", index=False)
            where.to_csv(out / "embedding_frase_migliore.csv", index=False)
            print("\n5. Segnale semantico per Q1 (bge-small-en-v1.5, nessun LLM)\n" + edf.to_string(index=False)
                  + "\n\n   Frase più simile al criterio, nei positivi\n" + where.to_string(index=False))
            md += ["## 5. Segnale semantico per Q1 (embedding, nessun LLM)", "",
                   f"Similarità tra ogni frase del lead e il criterio *{Q1_CRITERION}*.", "",
                   md_table(edf, index=False), "", md_table(where, index=False), ""]

    (out / "lead_analysis.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nFile in {out}/ (riassunto: lead_analysis.md)")


if __name__ == "__main__":
    main()
