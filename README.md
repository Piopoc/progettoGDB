# Operatori semantici su graph database

Progetto del corso di Graph Databases (Università di Padova, A.A. 2026/2027).
Costruiamo una piccola libreria di **operatori semantici** (filter, classify, map, join) sopra un graph database. Misuriamo quanto **costano** (chiamate al modello, token, dollari) e quanto spesso sono **corretti**, rispetto a un algoritmo di riferimento e rispetto alla answer key del grafo.

## Decisioni di progetto

| Voce | Scelta | Note |
|---|---|---|
| Dominio | **film con romanzi** (`films`) | Proprietà nascoste dei film: *main subject* (P921), *genre* (P136), *based on* (P144), *derivative work* (P4969), *set in period* (P2408). Join: il film è basato sul romanzo (P144). |
| Engine | **GraphDB 11.5.0** (Free), in Docker Compose | Scelto il 9 novembre 2026 su indicazione del professore, al posto di Oxigraph. La funzione semantica è una classe Java (RDF4J Function SPI) in un jar caricato da GraphDB. |
| Linguaggio delle query | SPARQL | |
| τ (testo di un binding) | baseline τ0: label + `description_screened` + lead, tagliato a 1.200 caratteri | Statistiche sul main set dev (1.000 film, `cl100k_base`): media 167,6 token, 90° percentile 270. Coincidono con i valori del pacchetto dati. |
| Modelli | locale (Unsloth Studio) per lo sviluppo, Gemini per i run veri | Tutte le chiamate passano dal gateway. |
| Ottimizzazione | `<O1 \| O2 \| O3 \| O4 \| propria>` *(da decidere entro M1)* | |

### Come è fatto il sistema

La libreria Python (operatori, piani, valutazione) manda le query SPARQL a GraphDB via HTTP. Dentro la query, la funzione `sem:filter` (Java, nel jar) manda la richiesta al gateway, che usa la cache e chiama il modello. Il testo di ogni film (τ) lo costruisce Python (`src/tau.py`) e lo scrive nel grafo come triple `ex:tau`, un named graph per variante di τ. La query lo legge da lì e lo passa alla funzione.

Il numero di chiamate si conta nel **log del gateway**, non nel codice.

## Date importanti

| Data | Evento | Obbligatorio |
|---|---|---|
| 12 nov 2026, ore 12 | Lezione sul gateway (Alessandro Disarò) | consigliato |
| **19 nov 2026** | **M1**: design note (2 pagine) | no (+2/+1/0/−1 punti) |
| **10 dic 2026** | **M2**: sistema di riferimento + **6 query proprie** | no, ma le 6 query sì |
| **21 dic 2026** | **M3**: ottimizzazione + pubblicazione del pool | no (consegna interna) |
| **8 gen 2027** | **Consegna finale** + presentazione pubblica | sì |

Contenuto richiesto per la M1: engine installato, entrambi i set caricati, τ definita, query comuni scritte per l'engine, una chiamata end-to-end funzionante, ottimizzazione scelta.

## Struttura del repository

### Cartelle

| Cartella | Contenuto |
|---|---|
| `data/` | Pacchetto dati del professore in `data/films/` (`dev/`, `eval/`, `tools/`, `README.md`, `MANIFEST.sha256`). L'altro dominio (`data/games/`) arriva con il pool. **Non vanno su Git**: file pesanti, e i testi Wikipedia sono sotto licenza CC BY-SA (serve l'attribuzione se si ridistribuiscono). |
| `docs/` | Documentazione: design note M1, descrizione di τ con statistiche, studio dell'ordine di valutazione, log di lavoro (`log.md`), appunti per il report, dichiarazione d'uso degli assistenti di coding. |
| `src/` | Codice Python riutilizzabile: libreria degli operatori (`sem_filter`, `sem_classify`, `sem_map`, `sem_join`), piani (riferimento, blocking, cascade, block join), τ, client SPARQL verso GraphDB, client del gateway, metriche, materializzazione. |
| `java/` | Progetto Maven della funzione semantica per GraphDB (`sem:filter`, `sem:classify`, `sem:join`). Il jar compilato non va su Git. |
| `prompts/` | Tutti i prompt e le configurazioni di τ, **versionati** (fanno parte della specifica). Cambiare un prompt dopo la calibrazione invalida la calibrazione. |
| `queries/` | Query SPARQL: le 8 comuni e le 6 proprie, con le diverse forme usate nello studio dell'ordine di valutazione. |
| `keys/` | Answer key delle query proprie (`keys/<dominio>/<set>/<query_id>/key.json`). |
| `runs/` | File JSON di ogni run (`runs/<dominio>/<set>/<query_id>/<run_id>.json`), letti dal checker. |
| `cache/` | Cache delle risposte del gateway e log delle chiamate. Si consegnano con il repository. |
| `eval/` | `results.csv` (generato dal checker, mai scritto a mano), frontiera di costo/qualità, ispezione dei falsi positivi, controlli di leakage (`leakage.md`). |
| `rdf/` | Grafi derivati (un named graph per run) con la provenance degli archi materializzati. |
| `tools/` | `semops_check.py` copiato da `data/films/tools/` (non modificare). |
| `notebooks/` | Esplorazione e prototipi. Il codice stabile passa in `src/`. |

### File nella radice

| File | Scopo |
|---|---|
| `README.md` | Presentazione del progetto, decisioni, struttura, comando unico di riproduzione. |
| `SETUP.md` | Installazione dell'ambiente: Python, GraphDB con Docker, modello locale, gateway, chiavi API. |
| `CONVENZIONI.md` | Regole del team: τ parametrica, prompt versionati, naming dei run, niente valori hardcoded, flusso Git. |
| `docker-compose.yml` | Avvio di GraphDB. Nessun segreto dentro. |
| `requirements.txt` | Librerie Python con versioni pinnate. |
| `.env.example` | Modello del file `.env` (chiavi e indirizzi). Il `.env` vero non va mai su Git. |
| `.gitignore` | Esclude dati pesanti, repository di GraphDB, chiavi, cache dei notebook, ambienti virtuali, `java/target/`. |

## Riproduzione con un solo comando

*(da completare entro M3; il professore la esegue da un clone pulito, senza chiave API, usando la cache consegnata)*

```bash
python -m src.run --domain films --set eval --queries Q1,Q2,Q3,Q4,Q5,Q6,Q8
```

La riproduzione dovrà anche avviare GraphDB e caricare i dati. La procedura andrà scritta in `SETUP.md` e provata su una macchina diversa da quella di sviluppo.

## Regole da ricordare

- **Leakage = fallimento.** Il valore nascosto non deve mai arrivare al modello. Si ricontrolla dopo ogni modifica a τ.
- **Tuning solo sul dev set.** Il set di valutazione si esegue **una volta** per piano.
- Ogni chiamata al modello passa dal **gateway**.
- Gli assistenti di coding sono ammessi, ma vanno **dichiarati** nel report. Il report è scritto da noi (massimo 6 pagine).
- Ogni deviazione dalla consegna richiede **approvazione scritta** del professore prima della consegna.
