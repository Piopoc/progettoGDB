# Recap cose fatte il 2026-11-08 12:23
- sistemato la repo
- testato modello locale sul dataset del provato con esito: positivo
- testato modello tramite API GEMINI con esito: positivo
- cambiato motore secondo consiglio del professore (da oxigrah a graphdb)
- creato SPARQL queries per q1 a q8 (normali + gt) DA TESTARE (missing sem operators + tau)

# 2026-11-17: catena end-to-end su GraphDB
- GraphDB in Docker non raggiungeva il server del modello su 127.0.0.1:8888 (Unsloth ascolta solo in locale). Soluzione: `docker-compose.override.yml` con `network_mode: host`, solo locale, escluso da Git.
- La FilterFunction mandava sempre la chiave "ollama" e non aveva timeout: con Unsloth le risposte erano vuote e le query restavano bloccate (fermate con Abort da Monitoring). Corretto: chiave da LOCAL_MODEL_API_KEY, timeout, errori nel log con prefisso [sem:filter] (commit cca0838).
- Decisioni del gruppo già prese: GraphDB come motore, ottimizzazioni O2 (principale) e O4 (seconda, 16 novembre), tau ancora da scegliere in maniera definitiva

# 2026-11-18: studio di τ per Q4 e Q6, blocking (ramo tabella-tau)
- Macchina: laptop, qwen2.5:3b su Unsloth, json_schema, senza ragionamento. Embedding bge-small-en-v1.5 con fastembed 0.9.1 (CPU).
- Nuovi script: `src/study_q4.py` (classificazione), `src/study_join.py` (blocking e join); prompt `classify_v1`, `join_v1`; `llm_client` accetta risposte {"label": ...}.
- Q4, t0, 839 film: hit rate 0,878, accuratezza 0,854, macro-F1 0,747, 0 parse failure, 0 fuori insieme. Riferimento gratuito (nome del genere nel testo, copertura 0,84): 0,738 / 0,715 / 0,697. Generi deboli: thriller (precisione 0,20 su 7 film), guerra, azione.
- Prova end-to-end (`run_e2e`) su 10 film di Q1 in films-dev: 0 errori, 22 s; le forme BIND e FILTER danno lo stesso insieme di film.
- Blocking Q6 e Q7: vedi docs/ottimizzazioni.md, sezione 7. Q6 recall 1,0 con k = 10; Q7 0,99 con k = 10.
- Join Q6 top-k: F1 0,744 / 0,662 / 0,564 per k = 3 / 5 / 10; precisione bassa, metà dei falsi positivi sono romanzi dello stesso autore.
- Unsloth è andato in crash per RAM satura verso la fine del run Q4; rilanciato lo stesso comando, la cache ha fatto ripartire il run (13 richieste nuove su 839).
- Da fare: nested loop Q6 (5.000 richieste) sul PC fisso, poi `--reference`; non mescolare le cache delle due macchine.