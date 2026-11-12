"""τ: il testo che rappresenta un binding (un film o un romanzo) davanti al modello.

La logica sta qui; le scelte (quali campi, quanto tagliare, che formato) stanno nei file
prompts/tau_<variante>_v<N>.json. Una variante nuova è un file nuovo, non una modifica a questo codice.

Chiavi della configurazione (tutte facoltative; i valori predefiniti riproducono il τ del rilascio):
  use_description        usa description_screened (mai la descrizione grezza)      predefinito true
  use_lead               usa il lead dell'articolo Wikipedia                         predefinito true
  max_chars              taglio sull'INTERA stringa; null = nessun taglio            predefinito 1200
  format                 "plain" (frasi di seguito) oppure "labeled" (campi con etichetta)
  normalize_whitespace   sostituisce ogni sequenza di spazi/a capo con uno spazio    predefinito false
  extra_props            {"Film": ["P57", "P495"], "Novel": ["P50"]}: proprietà del grafo da aggiungere.
                         Sono ammesse solo quelle con tau_allowed_for_common_queries in properties.csv.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

DEFAULTS = {
    "use_description": True,
    "use_lead": True,
    "max_chars": 1200,
    "format": "plain",
    "normalize_whitespace": False,
    "extra_props": {},
}


def load_cfg(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TauBuilder:
    def __init__(self, data_dir: str, cfg: dict):
        self.data_dir = Path(data_dir)
        self.cfg = {**DEFAULTS, **cfg}
        if self.cfg["format"] not in ("plain", "labeled"):
            raise ValueError(f"format sconosciuto: {self.cfg['format']!r} (usa 'plain' o 'labeled')")

        self.ent = pd.read_csv(self.data_dir / "entities.csv").set_index("qid")

        props = pd.read_csv(self.data_dir / "properties.csv")
        self.allowed: dict[str, set[str]] = {}
        for r in props.itertuples():
            v = r.tau_allowed_for_common_queries
            if isinstance(v, str):
                self.allowed[r.property] = set(v.split("|"))
        self.plabel = dict(zip(props.property, props.label))

        for cls, plist in self.cfg["extra_props"].items():
            for p in plist:
                if cls not in self.allowed.get(p, set()):
                    raise ValueError(
                        f"{p} ({self.plabel.get(p, '?')}) non è ammessa in τ per {cls}: "
                        "è nascosta o non è nell'elenco di properties.csv"
                    )
        self._extra = self._load_extra() if self.cfg["extra_props"] else {}

    def _load_extra(self) -> dict:
        wanted = {p for pl in self.cfg["extra_props"].values() for p in pl}
        st = pd.read_csv(self.data_dir / "statements.csv", usecols=["qid", "property", "value", "value_label"])
        st = st[st.property.isin(wanted)].copy()
        st["txt"] = st.value_label.where(st.value_label.notna(), st.value)
        st = st.dropna(subset=["txt"])
        out: dict = {}
        for (q, p), g in st.groupby(["qid", "property"], sort=False):
            out[(q, p)] = list(dict.fromkeys(str(x) for x in g.txt))
        return out

    # --- costruzione -----------------------------------------------------------------------
    def parts(self, qid: str) -> list[tuple[str, str, str]]:
        """Lista di (tipo, etichetta, testo). tipo: title | description | extra | lead."""
        r = self.ent.loc[qid]
        c = self.cfg
        out = [("title", "Title", str(r.label))]
        if c["use_description"]:
            d = r.description_screened
            if isinstance(d, str) and d.strip():  # vuota = descrizione scartata dallo screening
                out.append(("description", "Description", d.strip()))
        for p in c["extra_props"].get(r["class"], []):
            vals = self._extra.get((qid, p))
            if vals:
                lab = self.plabel[p]
                out.append(("extra", lab[:1].upper() + lab[1:], ", ".join(vals)))
        if c["use_lead"]:
            out.append(("lead", "Text", str(r.lead)))
        return out

    def build(self, qid: str) -> str:
        ps = self.parts(qid)
        if self.cfg["normalize_whitespace"]:
            ps = [(k, lab, re.sub(r"\s+", " ", t).strip()) for k, lab, t in ps]
        if self.cfg["format"] == "plain":
            chunks = []
            for kind, lab, t in ps:
                if kind == "lead":
                    chunks.append(t)
                elif kind == "extra":
                    chunks.append(f"{lab}: {t}.")
                else:
                    chunks.append(t + ".")
            text = " ".join(chunks)
        else:
            text = "\n".join(f"{lab}: {t}" for _, lab, t in ps)
        mc = self.cfg["max_chars"]
        return text[:mc].rstrip() if mc else text

    def extra_text(self, qid: str) -> str:
        """Solo la parte aggiunta dalle proprietà del grafo (serve al controllo di leakage)."""
        return " ".join(t for k, _, t in self.parts(qid) if k == "extra")


def token_stats(texts, encoding: str = "cl100k_base") -> dict:
    """Media e 90° percentile in token. Se il tokenizer non è disponibile stima caratteri/4 e lo dichiara."""
    import numpy as np

    try:
        import tiktoken

        enc = tiktoken.get_encoding(encoding)
        k = [len(enc.encode(t)) for t in texts]
        approx = False
    except Exception:
        k = [max(1, round(len(t) / 4)) for t in texts]
        approx = True
    return {"mean": float(np.mean(k)), "p90": float(np.percentile(k, 90)), "n": len(k), "approx": approx}
