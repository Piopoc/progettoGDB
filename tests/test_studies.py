"""Test delle parti di calcolo di study_q4, study_join e llm_client che non richiedono dati né modello."""
import numpy as np

from src.llm_client import LLMClient
from src.study_join import blocking_table, prf_sets
from src.study_q4 import macro_f1, name_in_text_baseline


def test_macro_f1_perfetto_e_sbagliato():
    t = np.array(["A", "B", "A", "C"])
    assert macro_f1(t, t, ["A", "B", "C"]) == 1.0
    assert macro_f1(np.array(["", "", "", ""]), t, ["A", "B", "C"]) == 0.0   # fuori insieme = errore


def test_macro_f1_non_pesata():
    # A: 3 film tutti giusti; B: 1 film sbagliato -> macro = (F1_A + F1_B) / 2, non la accuracy
    t = np.array(["A", "A", "A", "B"])
    p = np.array(["A", "A", "A", "A"])
    assert abs(macro_f1(p, t, ["A", "B"]) - (2 * 3 / (2 * 3 + 1) + 0) / 2) < 1e-9


def test_parse_label():
    assert LLMClient._parse_label('{"label": "comedy film"}') == ("comedy film", False)
    assert LLMClient._parse_label('```json\n{"label": " war film "}\n```') == ("war film", False)
    assert LLMClient._parse_label('{"answer": true}') == (None, True)
    assert LLMClient._parse_label("") == (None, True)


def test_nome_nel_testo_prende_il_primo():
    labels = {"Q1": "drama film", "Q2": "comedy film", "Q3": "war film"}
    out = name_in_text_baseline(["a 1999 comedy drama", "a film about the World War", "nothing"], labels)
    assert out == ["Q2", "", ""]   # "World War" non è "war film"


def test_prf_sets_recall_su_tutte_le_coppie():
    truth = {("a", "x"), ("b", "y")}
    tp, fp, fn, p, r, f = prf_sets({("a", "x"), ("a", "z")}, truth)
    assert (tp, fp, fn) == (1, 1, 1) and p == 0.5 and r == 0.5


def test_blocking_recall():
    left, right = ["a", "b"], ["x", "y", "z"]
    order = np.array([[0, 1, 2], [2, 0, 1]])           # a: x,y,z   b: z,x,y
    rows, pos = blocking_table("t0", left, right, {("a", "x"), ("b", "y")}, order, [1, 3])
    assert pos == {("a", "x"): 1, ("b", "y"): 3}
    assert [r["recall_blocking"] for r in rows] == [0.5, 1.0]


# --- taglio per frasi (varianti s1, s2, ...) e richiesta al gateway ----------------------------------
from src.tau import split_sentences


def test_frasi_abbreviazioni_e_iniziali():
    assert split_sentences("Dr. No is a 1962 spy film. It stars Sean Connery.") == [
        "Dr. No is a 1962 spy film.", "It stars Sean Connery."]
    assert split_sentences("Based on J. R. R. Tolkien. Shot in the U.S. Army base.\nSecond paragraph.") == [
        "Based on J. R. R. Tolkien.", "Shot in the U.S. Army base.", "Second paragraph."]


def test_frasi_numeri_e_virgolette():
    assert split_sentences("Released in 1999. 2001 saw a sequel.") == ["Released in 1999.", "2001 saw a sequel."]
    assert split_sentences('He said "Go." Then left.') == ['He said "Go."', "Then left."]


def test_gateway_body_rispetta_il_contratto():
    c = LLMClient.__new__(LLMClient)
    c.model, c.run_id, c.namespace = "local/x", "r1", "ns"
    b = c.body("istruzioni", "testo")
    assert set(b) == {"model", "instructions", "input", "text", "metadata", "temperature"}
    f = b["text"]["format"]
    assert f["strict"] is True and f["schema"]["additionalProperties"] is False
    assert b["metadata"] == {"run_id": "r1", "cache_namespace": "ns"}
    lab = c.body("i", "t", ["drama film", "war film"])["text"]["format"]["schema"]
    assert lab["properties"]["label"]["enum"] == ["drama film", "war film"]