# Operatori semantici su graph database

Progetto del corso di Graph Databases (Università di Padova, A.A. 2026/2027).
Costruiamo una piccola libreria di **operatori semantici** (filter, classify, map, join) sopra un graph database. Misuriamo quanto **costano** (chiamate al modello, token, dollari) e quanto spesso sono **corretti**, rispetto a un algoritmo di riferimento e rispetto alla answer key del grafo.

- **Dominio assegnato al gruppo:** **videogiochi con serie** (`games`). Proprietà nascosta: *genre* (P136). Join: *part of the series* (P179). Dettagli in `docs/dati_games.md`.
- **Engine scelto:** Oxigraph
- **Ottimizzazione scelta:** `<O1 | O2 | O3 | O4 | propria>` *(da decidere entro M1)*

## Date importanti

| Data | Evento | Obbligatorio |
|---|---|---|
| 12 nov 2026, ore 12 | Lezione sul gateway (Alessandro Disarò) | consigliato |
| **19 nov 2026** | **M1**: design note (2 pagine) | no (+2/+1/0/−1 punti) |
| **10 dic 2026** | **M2**: sistema di riferimento + **6 query proprie** | no, ma le 6 query sì |
| **21 dic 2026** | **M3**: ottimizzazione + pubblicazione del pool | no (consegna interna) |
| **8 gen 2027** | **Consegna finale** + presentazione pubblica | sì |

Dettaglio delle attività: `docs/CHECKLIST.md` (in italiano) e `docs/DEADLINES_STE.md` (in inglese tecnico semplificato).

## Struttura del repository

### Cartelle

| Cartella | Contenuto |
|---|---|
| `data/` | Pacchetto dati del professore in `data/games/` (`dev/`, `eval/`, `tools/`, `README.md`, `MANIFEST.sha256`). L'altro dominio (`data/films/`) arriva con il pool. **Non vanno su Git**: file pesanti, e i testi Wikipedia sono sotto licenza CC BY-SA (serve l'attribuzione se si ridistribuiscono). |
| `docs/` | Documentazione: checklist, scadenze, design note M1, descrizione di τ con statistiche, studio dell'ordine di valutazione, log di lavoro, appunti per il report, dichiarazione d'uso degli assistenti di coding. |
| `src/` | Codice Python riutilizzabile: libreria degli operatori (`sem_filter`, `sem_classify`, `sem_map`, `sem_join`), piani (riferimento, blocking, cascade, block join), τ, engine binding, client del gateway, metriche, materializzazione. |
| `prompts/` | Tutti i prompt, **versionati** (fanno parte della specifica). Cambiare un prompt dopo la calibrazione invalida la calibrazione. |
| `queries/` | Query SPARQL/Cypher: le 8 comuni e le 6 proprie, con le diverse forme usate nello studio dell'ordine di valutazione. |
| `keys/` | Answer key delle query proprie (`keys/<dominio>/<set>/<query_id>/key.json`). |
| `runs/` | File JSON di ogni run (`runs/<dominio>/<set>/<query_id>/<run_id>.json`), letti dal checker. |
| `cache/` | Cache delle risposte del gateway e log delle chiamate. Si consegnano con il repository. |
| `eval/` | `results.csv` (generato dal checker, mai scritto a mano), frontiera di costo/qualità, ispezione dei falsi positivi, controlli di leakage. |
| `rdf/` | Grafi derivati (un named graph per run) con la provenance degli archi materializzati. |
| `tools/` | `semops_check.py` copiato da `data/games/tools/` (non modificare). Gli script `load_oxigraph.py` e `load_neo4j.py` restano nel pacchetto dati. |
| `notebooks/` | Esplorazione e prototipi. Il codice stabile passa in `src/`. |

### File nella radice

| File | Scopo |
|---|---|
| `README.md` | Presentazione del progetto, struttura, comando unico di riproduzione. |
| `SETUP.md` | Installazione dell'ambiente: Python, engine, modello locale, gateway, chiavi API. |
| `CONVENZIONI.md` | Regole del team: τ parametrica, prompt versionati, naming dei run, niente valori hardcoded, flusso Git. |
| `requirements.txt` | Librerie Python con versioni pinnate. |
| `.env.example` | Modello del file `.env` (chiavi e indirizzi). Il `.env` vero non va mai su Git. |
| `.gitignore` | Esclude dati pesanti, chiavi, cache dei notebook, ambienti virtuali. |

## Riproduzione con un solo comando

*(da completare entro M3; il professore la esegue da un clone pulito, senza chiave API, usando la cache consegnata)*

```bash
python -m src.run --domain games --set eval --queries Q1,Q2,Q3,Q4,Q5,Q6,Q8
```

## Regole da ricordare

- **Leakage = fallimento.** Il valore nascosto non deve mai arrivare al modello. Si ricontrolla dopo ogni modifica a τ.
- **Tuning solo sul dev set.** Il set di valutazione si esegue **una volta** per piano.
- Ogni chiamata al modello passa dal **gateway**.
- Gli assistenti di coding sono ammessi, ma vanno **dichiarati** nel report. Il report è scritto da noi (massimo 6 pagine).
- Ogni deviazione dalla consegna richiede **approvazione scritta** del professore prima della consegna.
