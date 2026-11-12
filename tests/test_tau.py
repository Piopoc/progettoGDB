"""Test di correttezza tecnica di τ. Dalla radice del repository:  python -m pytest tests -v
Per un'altra cartella dati:  TAU_DATA=data/films/dev python -m pytest tests -v"""
import os
from pathlib import Path

import pandas as pd
import pytest

from src.tau import TauBuilder, load_cfg, token_stats

DATA = Path(os.getenv("TAU_DATA", "data/films/dev"))
pytestmark = pytest.mark.skipif(not (DATA / "entities.csv").exists(), reason=f"dati non trovati in {DATA}")
CFG = Path("prompts")


@pytest.fixture(scope="module")
def ent():
    return pd.read_csv(DATA / "entities.csv")


@pytest.fixture(scope="module")
def t0():
    return TauBuilder(DATA, load_cfg(str(CFG / "tau_t0_v1.json")))


def test_deterministica(t0, ent):
    q = ent.qid.iloc[0]
    assert t0.build(q) == t0.build(q)


def test_descrizione_vuota_saltata(t0, ent):
    vuote = ent[ent.description_screened.isna()]
    assert len(vuote), "attesi film con descrizione screened vuota"
    r = vuote.iloc[0]
    assert t0.build(r.qid).startswith(f"{r.label}. {str(r.lead)[:20]}")


def test_taglio_rispettato(ent):
    for name, limit in (("t0", 1200), ("t1", 600)):
        b = TauBuilder(DATA, load_cfg(str(CFG / f"tau_{name}_v1.json")))
        assert max(len(b.build(q)) for q in ent.qid[:300]) <= limit


def test_senza_lead(ent):
    b = TauBuilder(DATA, load_cfg(str(CFG / "tau_t4_v1.json")))
    r = ent[ent["class"] == "Film"].iloc[0]
    assert str(r.lead)[150:190] not in b.build(r.qid)


def test_formato_con_etichette(ent):
    b = TauBuilder(DATA, load_cfg(str(CFG / "tau_t2_v1.json")))
    t = b.build(ent.qid.iloc[0])
    assert t.startswith("Title: ") and "\nText: " in t


def test_proprieta_vietate_rifiutate():
    with pytest.raises(ValueError):
        TauBuilder(DATA, {"extra_props": {"Film": ["P921"]}})
    with pytest.raises(ValueError):
        TauBuilder(DATA, {"extra_props": {"Film": ["P840"]}})
    with pytest.raises(ValueError):
        TauBuilder(DATA, {"extra_props": {"Film": ["P50"]}})


def test_proprieta_ammesse_accettate():
    TauBuilder(DATA, {"extra_props": {"Film": ["P57", "P495"], "Novel": ["P50"]}})


def test_statistiche_baseline_come_il_rilascio(t0):
    sets = pd.read_csv(DATA / "sets.csv")
    main = sets[sets.set_id == "main"].qid
    ts = token_stats([t0.build(q) for q in main])
    if ts["approx"]:
        pytest.skip("tiktoken non disponibile: il confronto con 168/270 richiede il tokenizer vero")
    assert abs(ts["mean"] - 168) < 1.5 and abs(ts["p90"] - 270) < 5
