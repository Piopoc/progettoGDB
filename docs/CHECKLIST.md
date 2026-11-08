# Setup dell'ambiente

Guida per configurare il progetto su Linux, macOS e Windows. Tempo stimato: 30 minuti (più il download del modello locale).

> Le parti sul **gateway** vanno completate dopo la lezione del 12 novembre. Dove manca il dettaglio c'è l'indicazione *(da completare)*.

## 0. Prerequisiti

- **Git**

- **Python 3.10 o superiore** (`python3 --version` su Linux/macOS, `py --version` su Windows). Verificare la compatibilità con `pyoxigraph 0.5.11`.

- Accesso al repository (SSH configurato oppure token GitHub)

- **Un engine** (ne basta uno, scelto entro M1):

  - **Oxigraph** tramite `pyoxigraph 0.5.11` (consigliato: solo un pacchetto Python)
  - **Neo4j Community 2026.08.0** con il plugin GenAI 2026.08.0 *(solo se si sceglie Cypher)*
  - **GraphDB Free 11.5.0** *(il più laborioso: serve un jar Java)*

- **Ollama** (o altro server locale) per un modello piccolo quantizzato

- Pacchetto dati **games** (da Moodle/Drive del corso), che contiene anche i loader e il checker

## 1. Clona il repository

```bash
git clone git@github.com:Piopoc/progettoGDB.git
cd progettoGDB
```

## 2. Crea l'ambiente virtuale (nella radice del repository)

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Se PowerShell blocca lo script, esegui una volta: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Windows (cmd)**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

Se l'ambiente è attivo, il prompt mostra `(.venv)` all'inizio.

> **Non spostare né rinominare la cartella `.venv` o il repository dopo averla creata**: i venv contengono percorsi assoluti e si rompono. Se succede, cancella `.venv` e ripeti questo passaggio.

## 3. Installa le dipendenze

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Usa sempre `python -m pip`, mai `pip` da solo.

Librerie previste (da aggiungere a `requirements.txt` con versione pinnata, avvisando il team):`pyoxigraph==0.5.11`, `numpy`, `fastembed` (embedding per il blocking), `jsonschema`, `httpx` o `requests`, `pytest`.

## 4. Registra il kernel per Jupyter

```bash
python -m ipykernel install --user --name progetto-gdb --display-name "Python (progetto GDB)"
```

Nei notebook seleziona **Kernel → Change kernel → Python (progetto GDB)**.

## 5. Configura le chiavi e gli indirizzi (file `.env`)

Ognuno usa **la propria chiave** e non la condivide con nessuno.

**Linux / macOS**

```bash
cp .env.example .env
```

**Windows**

```powershell
copy .env.example .env
```

Apri `.env` e inserisci i valori dopo il simbolo `=`, senza spazi né virgolette:

```text
GOOGLE_API_KEY=la_tua_chiave
AZURE_OPENAI_API_KEY=la_tua_chiave
GATEWAY_URL=http://127.0.0.1:8000/v1
```

Il file `.env` è nel `.gitignore`: non verrà mai committato. Non incollare la chiave in chat, notebook o commit. Nel repository non ci devono essere segreti, nemmeno nella cronologia.

*(da completare: nomi esatti delle variabili e porta del gateway, dopo la lezione del 12/11)*

## 6. Inserisci i dati e gli strumenti

Nel progetto ci sono **due cartelle `tools/` diverse**. Non vanno confuse.

| Cartella            | Dove                     | Contenuto                                              | Su Git?                               |
| ------------------- | ------------------------ | ------------------------------------------------------ | ------------------------------------- |
| `data/games/tools/` | dentro il pacchetto dati | `load_oxigraph.py`, `load_neo4j.py`, `semops_check.py` | no (`data/games/` è nel `.gitignore`) |
| `tools/`            | radice del repository    | copia di `semops_check.py` (e `prices.example.json`)   | sì                                    |

Il pacchetto dati `games` va in `data/games/` e contiene `README.md`, `MANIFEST.sha256`, `dev/`, `eval/` e `tools/`. **Non va su Git.**

Dal materiale del professore si copiano così:

```text
data/games/tools/semops_check.py  ->  tools/semops_check.py      (checker, non modificare)
prices.example.json               ->  tools/prices.example.json  (formato del listino prezzi)
fixtures.py, test_check.py, test_grade.py -> tools/tests/        (facoltativo: test del checker)
examples/                         ->  docs/examples/             (esempi di run file e key.json, solo riferimento)
```

**Non mettere gli esempi in `runs/` o `keys/`**: il checker legge quelle cartelle e due run per la stessa query sono un errore.

Verifica l'integrità dei dati (dalla cartella `data/games/`):

```bash
sha256sum -c MANIFEST.sha256        # macOS: shasum -a 256 -c MANIFEST.sha256
```

L'altro dominio (film) arriva con il pool, il 21 dicembre.

### Carica il grafo con Oxigraph (consigliato)

Servono **due store separati**. Quello senza statement nascoste serve per far girare le query semantiche. Quello con le statement nascoste serve solo per il punteggio e per le answer key. Così si riduce il rischio di leakage.

**Con i loader del pacchetto:**

```bash
cd data/games
python3 tools/load_oxigraph.py dev store-dev                  # senza nascoste: per le query
python3 tools/load_oxigraph.py dev store-dev-gt --with-hidden # con nascoste: solo scoring
python3 tools/load_oxigraph.py eval store-eval
python3 tools/load_oxigraph.py eval store-eval-gt --with-hidden
```

**In alternativa ai loader** (o se non funzionano), `graph.nt` e `hidden.nt` sono N-Triples e si caricano direttamente (verificare il nome dei parametri nella documentazione di pyoxigraph 0.5.11):

```python
import pyoxigraph as ox
store = ox.Store("store-dev")
store.bulk_load(path="data/games/dev/graph.nt", format=ox.RdfFormat.N_TRIPLES)
gt = ox.Store("store-dev-gt")
gt.bulk_load(path="data/games/dev/graph.nt", format=ox.RdfFormat.N_TRIPLES)
gt.bulk_load(path="data/games/dev/hidden.nt", format=ox.RdfFormat.N_TRIPLES)
```

Dopo il caricamento controllate con una query che le triple `ex:inSet` ci siano (il README dice che gli insiemi sono visibili in RDF come `ex:inSet`, ma non dice in quale file stanno).

Gli store sono cartelle pesanti: restano fuori da Git (`store-*/` è nel `.gitignore`).

### Carica il grafo con Neo4j (solo se si sceglie Cypher)

Copia `dev/*.csv` nella cartella `import` di Neo4j, poi:

```bash
python3 tools/load_neo4j.py bolt://localhost:7687 neo4j <password> --import-dir=<cartella import> [--with-hidden]
```

I nodi hanno le etichette `:Item`, `:VideoGame` o `:VideoGameSeries`, e un'etichetta per ogni insieme (`:Main`, `:Q4Input`, `:Q6Left`, `:Q6Right`, `:Q7Left`, `:Q7Right`, `:PoolMain`, `:PoolQ7Left`). Le relazioni hanno il nome della proprietà (`neo4j_rel_type` in `statements.csv`).

## 7. Modello locale per lo sviluppo

Durante lo sviluppo si usa un modello piccolo sulla propria macchina. Non si spende nulla e si testa l'architettura.

```bash
ollama pull <modello>        # un modello quantizzato da 0.8 a 9 miliardi di parametri
ollama run <modello> "ciao"  # prova rapida
```

Il modello a pagamento (Google Cloud, Azure) si usa solo quando la pipeline funziona. Budget approssimativo: circa 50 $ a testa su Google più 100 $ su Azure.

## 8. Avvia il gateway

*(da completare dopo il 12 novembre: comando di avvio, configurazione di cache, log, listino prezzi e tetto di budget)*

## 9. Avvia Jupyter

Dalla radice del repository, con l'ambiente attivo:

```bash
jupyter notebook
```

## 10. Verifica che tutto funzioni

Crea una cella nel notebook ed eseguila:

```python
import sys, os
from dotenv import load_dotenv
import pandas, pyoxigraph

load_dotenv()
print("Python:", sys.executable)          # deve contenere .venv
print("pandas:", pandas.__version__, "| pyoxigraph:", pyoxigraph.__version__)
print("Chiave presente:", bool(os.getenv("GOOGLE_API_KEY")))   # deve stampare True
```

Poi esegui il **test M1**: una chiamata semantica da una query, attraverso il gateway, fino al modello locale e ritorno, su dieci entità.

Infine controlla il checker:

```bash
python3 tools/semops_check.py . --data games=data/games --results eval/results.csv   # con un solo dominio: da verificare; il comando del professore usa films e games
```

## Flusso di lavoro con Git

1. `git pull` prima di iniziare.
2. Commit piccoli con messaggi chiari.
3. Se aggiungi una libreria, aggiornala in `requirements.txt` e avvisa gli altri (devono rieseguire il passo 3).
4. Se cambi un prompt, aggiorna la sua versione e annotalo nel log (vedi `CONVENZIONI.md`).
5. Prima di ogni consegna: clone pulito, su un'altra macchina, e prova della riproduzione.