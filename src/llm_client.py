"""Client del gateway del corso: manda le richieste a POST /v1/responses e legge le risposte.
Tutte le chiamate al modello del progetto passano da qui (studi di τ, join, prova end-to-end), quindi finiscono
nella cache e nel registro del gateway: una seconda esecuzione identica non fa richieste al modello, e il registro
alimenta i file di run. Questo client non ha una cache sua.
Due forme di risposta:
  {"answer": true/false}       filtro e join (ask senza choices)
  {"label": <una di choices>}  classificazione (ask con choices=[...]); una risposta fuori dall'elenco è una
                               risposta VALIDA ma sbagliata (out_of_set), non un parse failure.
Un fallback del gateway (parse_ok false) è una risposta NON valida: non diventa mai un "no".
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from dotenv import find_dotenv, load_dotenv

SCHEMA = {"type": "object", "properties": {"answer": {"type": "boolean"}}, "required": ["answer"]}


def label_schema(choices: list[str]) -> dict:
    return {"type": "object", "properties": {"label": {"type": "string", "enum": list(choices)}},
            "required": ["label"]}


class LLMClient:
    def __init__(self, run_id: str | None = None, model: str | None = None, base_url: str | None = None,
                 timeout: float = 300):
        load_dotenv(find_dotenv(usecwd=True))
        url = (base_url or os.getenv("GATEWAY_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.base = url[:-3] if url.endswith("/v1") else url
        self.model = model or os.getenv("GATEWAY_MODEL")
        if not self.model:
            raise SystemExit("Manca GATEWAY_MODEL nel .env: il nome della rotta in models.toml del gateway.")
        self.namespace = os.getenv("GATEWAY_CACHE_NAMESPACE", "progettogdb")
        self.run_id = run_id or os.getenv("GATEWAY_RUN_ID") or time.strftime("run-%Y%m%d-%H%M%S")
        self.paid = not self.model.startswith("local/")     # le rotte cloud costano: gli script chiedono --yes
        self.timeout = timeout
        self.requests = 0                                   # richieste al gateway (dalla cache o no)
        self._lock = threading.Lock()

    # --- richiesta ------------------------------------------------------------------------------
    def body(self, system: str, user: str, choices: list[str] | None = None) -> dict:
        if choices is None:
            name, schema = "boolean_answer", {**SCHEMA, "additionalProperties": False}
        else:
            name, schema = "label", {**label_schema(choices), "additionalProperties": False}
        return {
            "model": self.model, "instructions": system,
            "input": [{"role": "user", "content": user}],
            "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
            "metadata": {"run_id": self.run_id, "cache_namespace": self.namespace},
            "temperature": 0,
        }

    def ask(self, system: str, user: str, choices: list[str] | None = None) -> dict:
        body = self.body(system, user, choices)
        t_start, last, data = time.time(), None, None
        for attempt in range(5):
            try:
                r = httpx.post(self.base + "/v1/responses", json=body, timeout=self.timeout)
            except httpx.HTTPError as e:            # gateway spento o irraggiungibile
                last = e
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429:                # limite locale di concorrenza o tentativi del run
                last = f"HTTP 429 {r.text[:200]}"
                if "attempt" in r.text.lower():     # tentativi esauriti per (run_id, modello): inutile riprovare
                    break
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:                # 404 modello, 422 corpo, 502 provider, 503 cache corrotta
                raise RuntimeError(f"gateway HTTP {r.status_code} su {self.model}: {r.text[:300]}")
            data = r.json()
            break
        if data is None:
            raise RuntimeError(f"gateway: nessuna risposta da {self.base}/v1/responses ({self.model}): {last}")
        try:
            text = data["output"][0]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            text = None
        if data.get("parse_ok") is not True:
            answer, failure = None, True
        else:
            answer, failure = self._parse(text) if choices is None else self._parse_label(text)
        tin, tout = self._usage(data.get("provider_response"))
        with self._lock:
            self.requests += 1
        return {"answer": answer, "parse_failure": failure,
                "out_of_set": (not failure and choices is not None and answer not in choices),
                "error_type": data.get("error_type"), "tokens_in": tin, "tokens_out": tout,
                "raw": (text or "")[:200], "seconds": round(time.time() - t_start, 2)}

    def ask_many(self, pairs: list[tuple[str, str]], workers: int = 1, label: str = "",
                 choices: list[str] | None = None) -> list[dict]:
        done = 0

        def one(p):
            nonlocal done
            res = self.ask(*p, choices=choices)
            done += 1
            if done % 100 == 0:
                print(f"  {label} {done}/{len(pairs)}", flush=True)
            return res

        if workers <= 1:
            return [one(p) for p in pairs]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(one, pairs))

    # --- lettura della risposta -------------------------------------------------------------------
    @staticmethod
    def _usage(prov: dict) -> tuple:
        """Token dalla risposta grezza del provider: il gateway non li normalizza (li ha il suo registro).
        Su una risposta dalla cache sono quelli della chiamata originale."""
        u = (prov or {}).get("usage") or {}
        if u:
            return u.get("prompt_tokens") or u.get("input_tokens"), u.get("completion_tokens") or u.get("output_tokens")
        g = (prov or {}).get("usage_metadata") or (prov or {}).get("usageMetadata") or {}
        return (g.get("prompt_token_count") or g.get("promptTokenCount"),
                g.get("candidates_token_count") or g.get("candidatesTokenCount"))

    @staticmethod
    def _parse(content):
        """Filtro e join: serve un booleano nel campo "answer", altrimenti è un parse failure."""
        if not content:
            return None, True
        txt = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        try:
            a = json.loads(txt).get("answer")
        except (ValueError, AttributeError):
            return None, True
        return (a, False) if isinstance(a, bool) else (None, True)

    @staticmethod
    def _parse_label(content):
        """Classificazione: serve una stringa nel campo "label". Se manca, è un parse failure.
        Se c'è ma non è nell'elenco, la risposta è valida e viene contata come errore (out_of_set)."""
        if not content:
            return None, True
        txt = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        try:
            a = json.loads(txt).get("label")
        except (ValueError, AttributeError):
            return None, True
        return (a.strip(), False) if isinstance(a, str) and a.strip() else (None, True)
