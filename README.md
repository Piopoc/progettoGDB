## Struttura del repository

### Cartelle

| Cartella | Contenuto |
|---|---|
| `data/` | Dati di input: i CSV originali forniti dal professore (`data/raw/`) ed eventuali versioni pulite o intermedie (`data/processed/`). I file pesanti non vanno su Git. |
| `docs/` | Documentazione: checklist di progetto, motivazione delle scelte di modellazione (`ontologia.md`), data dictionary, log di lavoro, appunti per la relazione finale. |
| `eval/` | Valutazione: gold standard, risultati delle metriche (precision, recall, F1), report di validazione SHACL, confronti tra metodi e tabelle di costi e tempi. |
| `notebooks/` | Notebook Jupyter di esplorazione e prototipazione (analisi dei CSV, prove di matching, test con LOTUS e LLM). Lo scopo è sperimentare; il codice stabile va poi in `src/`. |
| `ontology/` | Ontologia in formato OWL/Turtle (file di Protégé), eventuali ontologie riusate e le shape SHACL. |
| `rdf/` | Grafi RDF generati dalla pipeline (file `.ttl` per ogni entità o fonte). Sono output riproducibili: si possono rigenerare dagli script. |
| `src/` | Codice Python riutilizzabile: generazione degli URI, conversione CSV → RDF, normalizzazione e matching, funzioni di valutazione, chiamate ai modelli. |

### File nella radice

| File | Scopo |
|---|---|
| `README.md` | Presentazione del progetto, struttura del repository, istruzioni per installare l'ambiente ed eseguire la pipeline. |
| `CONVENZIONI.md` | Regole condivise dal team: namespace e schema degli URI (es. `prefix:club_<id>`), naming di classi e proprietà, formato Turtle UTF-8, stile del codice, flusso Git. |
| `requirements.txt` | Elenco delle librerie Python (con versioni) per ricreare lo stesso ambiente su ogni macchina: `pip install -r requirements.txt`. |
| `.gitignore` | Elenco di ciò che Git deve ignorare: dati pesanti, chiavi e credenziali (`.env`), cache, checkpoint dei notebook, ambienti virtuali, file temporanei. |
