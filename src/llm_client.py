"""Client sottile per interrogare un modello con risposta {"answer": true/false}.

È provvisorio: serve fino alla lezione sul gateway (12 novembre) e ha la stessa idea del gateway:
una cache su file (stessa richiesta = zero costo) e il conteggio delle richieste vere.
Le risposte raccolte qui NON finiscono nella cache del gateway.

Backend:
  local   server OpenAI-compatibile locale   (LOCAL_MODEL_URL, LOCAL_MODEL, LOCAL_MODEL_API_KEY)
  google  Gemini via endpoint OpenAI-compatibile (GOOGLE_API_KEY, GOOGLE_MODEL)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import find_dotenv, load_dotenv

GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
SCHEMA = {"type": "object", "properties": {"answer": {"type": "boolean"}}, "required": ["answer"]}


class LLMClient:
    def __init__(self, backend: str, cache_path: str = "cache/study_cache.jsonl",
                 base_url: str | None = None, model: str | None = None, timeout: float = 120):
        load_dotenv(find_dotenv(usecwd=True))
        self.backend = backend
        self.timeout = timeout
        if backend == "local":
            self.base = (base_url or os.environ["LOCAL_MODEL_URL"]).rstrip("/")
            self.model = model or os.environ["LOCAL_MODEL"]
            self.key = os.getenv("LOCAL_MODEL_API_KEY") or "ollama"            
            self.thinking = os.getenv("LOCAL_ENABLE_THINKING", "true").lower() != "false"
            self.max_tokens = int(os.getenv("LOCAL_MAX_TOKENS", "300"))
            self.format_name = os.getenv("LOCAL_RESPONSE_FORMAT", "json_object")
            if self.format_name == "json_schema":
                self.response_format = {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA}}
            elif self.format_name == "json_object":
                self.response_format = {"type": "json_object"}
            else:
                raise ValueError("LOCAL_RESPONSE_FORMAT deve essere json_object o json_schema")
        elif backend == "google":
            self.base = (base_url or GOOGLE_BASE).rstrip("/")
            self.model = model or os.environ["GOOGLE_MODEL"]
            self.key = os.environ["GOOGLE_API_KEY"]
            self.format_name = "json_schema"
            self.thinking = True
            self.max_tokens = 300
            self.response_format = {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA}}
        else:
            raise ValueError("backend deve essere 'local' o 'google'")

        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    if not rec["value"].get("parse_failure"):   # un fallimento non è una risposta: si richiede
                        self._cache[rec["key"]] = rec["value"]
        self.new_requests = 0

    # --- chiave e cache ------------------------------------------------------------------
    def key_for(self, system: str, user: str) -> str:
        parts = [self.backend, self.model, system, user, 0]
        if not self.thinking:
            parts.append("no-thinking")   # aggiunto solo se spento, così le vecchie risposte in cache restano valide
        payload = json.dumps(parts, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def is_cached(self, system: str, user: str) -> bool:
        return self.key_for(system, user) in self._cache

    def build_body(self, system: str, user: str) -> dict:
        body = {
            "model": self.model, "temperature": 0, "max_tokens": self.max_tokens, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": self.response_format,
        }
        if self.backend == "local":
            body["seed"] = 0
            if not self.thinking:
                body["chat_template_kwargs"] = {"enable_thinking": False}
        return body

    # --- chiamata --------------------------------------------------------------------------
    def ask_bool(self, system: str, user: str) -> dict:
        k = self.key_for(system, user)
        with self._lock:
            if k in self._cache:
                return {**self._cache[k], "cached": True}
        body = self.build_body(system, user)
        headers = {"Authorization": f"Bearer {self.key}"}
        last = None
        t_start = time.time()
        for attempt in range(4):
            try:
                r = httpx.post(self.base + "/chat/completions", json=body, headers=headers, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                data = r.json()
                break
            except (httpx.HTTPError, ValueError) as e:  # rete, 429/5xx, JSON illeggibile
                last = e
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"richiesta fallita dopo 4 tentativi verso {self.base}/chat/completions: {last}")

        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        answer, failure = self._parse(content)
        usage = data.get("usage") or {}
        finish = ((data.get("choices") or [{}])[0]).get("finish_reason")
        rec = {"answer": answer, "parse_failure": failure, "finish_reason": finish,
               "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
               "raw": (content or "")[:200], "seconds": round(time.time() - t_start, 2)}
        with self._lock:
            self.new_requests += 1
            if not failure:
                self._cache[k] = rec
                with self.cache_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"key": k, "value": rec}, ensure_ascii=False) + "\n")
        return {**rec, "cached": False}

    @staticmethod
    def _parse(content):
        """Una risposta fuori schema è un parse failure: non diventa mai un negativo."""
        if not content:
            return None, True
        txt = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        try:
            a = json.loads(txt).get("answer")
        except (ValueError, AttributeError):
            return None, True
        return (a, False) if isinstance(a, bool) else (None, True)

    def ask_many(self, pairs: list[tuple[str, str]], workers: int = 1, label: str = "") -> list[dict]:
        done = 0

        def one(p):
            nonlocal done
            res = self.ask_bool(*p)
            done += 1
            if done % 100 == 0:
                print(f"  {label} {done}/{len(pairs)}", flush=True)
            return res

        if workers <= 1:
            return [one(p) for p in pairs]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(one, pairs))