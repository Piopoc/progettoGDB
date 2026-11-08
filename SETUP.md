# Setup dell'ambiente

Guida per configurare il progetto su Linux, macOS e Windows. Tempo stimato: 45 minuti (più il download del modello locale).

> Le parti sul **gateway** vanno completate dopo la lezione del 12 novembre. Dove manca il dettaglio c'è l'indicazione *(da completare)*.

**Convenzione sui comandi.** Prima di attivare l'ambiente virtuale (passo 2) si usa `python3` su Linux/macOS e `py` su Windows. Dopo l'attivazione si usa sempre `python`, che è uguale su tutti i sistemi. Nei blocchi con tre varianti si esegue solo quella del proprio sistema.

## 0. Prerequisiti

- **Git**
- **Python 3.12 o superiore.** Verifica: `python3 --version` (Linux/macOS) oppure `py --version` (Windows). La procedura è stata provata con Python 3.14 e `pyoxigraph 0.5.11`. Per `fastembed` (usato solo dal blocking, fase M2/M3) non è verificato che esista un pacchetto per tutte le versioni di Python.
- Accesso al repository (SSH configurato oppure token GitHub)
- **Un engine** (ne basta uno): **Oxigraph** tramite `pyoxigraph 0.5.11`, scelto dal gruppo. GraphDB resta un possibile secondo engine, più avanti.
- Un **server di modelli locale** con indirizzo compatibile OpenAI: Unsloth Studio (usato dal gruppo), Ollama o `llama-server` di llama.cpp
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

Usa sempre `python -m pip`, mai `pip` da solo. Se pip si ferma su una riga, leggi il nome della libreria nell'errore (vedi la tabella dei problemi in fondo).

**Versioni pinnate.** Pinnare significa scrivere in `requirements.txt` la versione esatta (`numpy==2.5.4`) invece del solo nome, così tutte le macchine installano le stesse versioni. Per le librerie senza versione, dopo un'installazione riuscita:

Linux / macOS

```bash
python -m pip freeze | grep -i -E "^(numpy|fastembed|jsonschema|httpx|pytest)=="
```

Windows (PowerShell)

```powershell
python -m pip freeze | Select-String -Pattern "^(numpy|fastembed|jsonschema|httpx|pytest)=="
```

Copia le righe stampate in `requirements.txt` al posto dei nomi senza versione. Non incollare tutto l'output di `pip freeze`. Dopo un commit, i compagni rieseguono `python -m pip install -r requirements.txt`.

## 4. Registra il kernel per Jupyter

```bash
python -m ipykernel install --user --name progetto-gdb --display-name "Python (progetto GDB)"
```

Nei notebook seleziona **Kernel → Change kernel → Python (progetto GDB)**.

## 5. Configura le chiavi e gli indirizzi (file `.env`)

Ognuno usa **le proprie chiavi** e non le condivide con nessuno. `.env.example` va su Git e contiene solo segnaposto. `.env` contiene i valori veri e **non va mai su Git**.

Linux / macOS

```bash
cp .env.example .env
```

Windows (PowerShell o cmd)

```bat
copy .env.example .env
```

Apri `.env` e inserisci i valori dopo il simbolo `=`, senza spazi né virgolette:

```text
# Server locale (passo 7)
LOCAL_MODEL_URL=http://localhost:8889/v1
LOCAL_MODEL_API_KEY=la_tua_chiave_locale
LOCAL_MODEL=unsloth/gemma-4-E2B-it-GGUF

# Modello a pagamento (passo 8)
GOOGLE_API_KEY=la_tua_chiave

# Percorsi (relativi alla radice del repository)
STORE_DEV=data/games/store-dev
STORE_DEV_GT=data/games/store-dev-gt

# Gateway (da completare dopo il 12 novembre)
GATEWAY_URL=http://127.0.0.1:8000/v1
```

Aggiungi a `.env.example` le stesse variabili con valori vuoti o segnaposto.

Controlla che Git ignori `.env` (devono comparire la regola e nessun file nuovo):

```bash
git check-ignore -v .env
git status
```

Non incollare chiavi in chat, notebook, commit o messaggi. Nel repository non ci devono essere segreti, nemmeno nella cronologia.

## 6. Inserisci i dati e gli strumenti

Nel progetto ci sono **due cartelle `tools/` diverse**. Non vanno confuse.

| Cartella            | Dove                     | Contenuto                                              | Su Git?                               |
| ------------------- | ------------------------ | ------------------------------------------------------ | ------------------------------------- |
| `data/games/tools/` | dentro il pacchetto dati | `load_oxigraph.py`, `load_neo4j.py`, `semops_check.py` | no (`data/games/` è nel `.gitignore`) |
| `tools/`            | radice del repository    | copia di `semops_check.py` e `prices.example.json`     | sì                                    |

Il pacchetto dati `games` va in `data/games/` e contiene `README.md`, `MANIFEST.sha256`, `dev/`, `eval/` e `tools/`. **Non va su Git.**

Dal materiale del professore si copiano così:

```text
data/games/tools/semops_check.py  ->  tools/semops_check.py      (checker, non modificare)
prices.example.json               ->  tools/prices.example.json  (formato del listino prezzi)
fixtures.py, test_check.py, test_grade.py -> tools/tests/        (facoltativo: test del checker)
examples/                         ->  docs/examples/             (esempi di run file e key.json, solo riferimento)
```

**Non mettere gli esempi in `runs/` o `keys/`**: il checker legge quelle cartelle e due run per la stessa query sono un errore.

Crea le cartelle del progetto che mancano, se serve:

Linux / macOS

```bash
mkdir -p tools docs prompts queries keys runs cache
```

Windows (PowerShell)

```powershell
"tools","docs","prompts","queries","keys","runs","cache" | ForEach-Object { New-Item -ItemType Directory -Force $_ }
```

### Verifica l'integrità dei dati (facoltativo)

Dalla cartella `data/games/`:

Linux

```bash
sha256sum -c MANIFEST.sha256
```

macOS

```bash
shasum -a 256 -c MANIFEST.sha256
```

Windows e qualsiasi sistema, con Python (assume righe nel formato `<hash> <percorso>`, quello di `sha256sum`):

```python
import hashlib, pathlib
bad = 0
for line in pathlib.Path("MANIFEST.sha256").read_text().splitlines():
    if not line.strip():
        continue
    h, name = line.split(None, 1)
    name = name.strip().lstrip("*")
    if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() != h:
        print("DIVERSO:", name); bad += 1
print("Tutti i file corrispondono" if bad == 0 else f"{bad} file diversi")
```

L'altro dominio (film) arriva con il pool, il 21 dicembre.

### Carica il grafo con Oxigraph

Servono **due store separati**. Quello senza statement nascoste serve per far girare le query semantiche. Quello con le statement nascoste serve solo per il punteggio e per le answer key. Così si riduce il rischio di leakage.

Gli store nascono nella cartella da cui lanci il comando. Lancia i comandi da `data/games/`, così finiscono in `data/games/store-*` (cartella già ignorata da Git; la regola `store-*/` nel `.gitignore` è una rete di sicurezza).

**Con i loader del pacchetto** (stessi comandi su tutti i sistemi, con l'ambiente attivo):

```bash
cd data/games
python tools/load_oxigraph.py dev store-dev                  # senza nascoste: per le query
python tools/load_oxigraph.py dev store-dev-gt --with-hidden # con nascoste: solo scoring
python tools/load_oxigraph.py eval store-eval
python tools/load_oxigraph.py eval store-eval-gt --with-hidden
cd ../..
```

**In alternativa ai loader**, `graph.nt` e `hidden.nt` sono N-Triples e si caricano direttamente (verificare il nome dei parametri nella documentazione di pyoxigraph 0.5.11):

```python
import pyoxigraph as ox
store = ox.Store("data/games/store-dev")
store.bulk_load(path="data/games/dev/graph.nt", format=ox.RdfFormat.N_TRIPLES)
gt = ox.Store("data/games/store-dev-gt")
gt.bulk_load(path="data/games/dev/graph.nt", format=ox.RdfFormat.N_TRIPLES)
gt.bulk_load(path="data/games/dev/hidden.nt", format=ox.RdfFormat.N_TRIPLES)
```

**Controllo.** Dopo il caricamento verifica che le triple `ex:inSet` ci siano (nel notebook, i percorsi sono relativi a `notebooks/`):

```python
import pyoxigraph as ox
store = ox.Store.read_only("../data/games/store-dev")
q = """PREFIX ex: <http://example.org/semop/>
SELECT (COUNT(DISTINCT ?e) AS ?n) WHERE { ?e ex:inSet ex:set-main }"""
print(list(store.query(q))[0]["n"].value)   # atteso: 1000
```

Se stampa 0, le triple `ex:inSet` non sono in `graph.nt` e bisogna capire dove stanno.

### Carica il grafo con Neo4j (solo se si sceglie Cypher)

Copia `dev/*.csv` nella cartella `import` di Neo4j, poi:

```bash
python tools/load_neo4j.py bolt://localhost:7687 neo4j <password> --import-dir=<cartella import> [--with-hidden]
```

I nodi hanno le etichette `:Item`, `:VideoGame` o `:VideoGameSeries`, e un'etichetta per ogni insieme (`:Main`, `:Q4Input`, `:Q6Left`, `:Q6Right`, `:Q7Left`, `:Q7Right`, `:PoolMain`, `:PoolQ7Left`). Le relazioni hanno il nome della proprietà (`neo4j_rel_type` in `statements.csv`).

## 7. Modello locale per lo sviluppo

Durante lo sviluppo si usa un modello piccolo sulla propria macchina. Non si spende nulla e si testa l'architettura. Serve un server con indirizzo compatibile OpenAI (`.../v1/chat/completions`).

### Opzione A: Unsloth Studio (usata dal gruppo)

1. Avvia Unsloth Studio. L'interfaccia web è su `http://localhost:8889` (la porta può cambiare: controlla l'indirizzo mostrato all'avvio).
2. Carica un modello GGUF dall'interfaccia. Modelli provati: `unsloth/gemma-4-E2B-it-GGUF` (2,3 GB, molto compresso, veloce, risposte semplici) e `unsloth/Qwen3.5-9B-MTP-GGUF` (4,5 GB, più capace). Il campo `loaded` di `/v1/models` dice quale è caricato.
3. Il server richiede un **token Bearer**. Crea una chiave API dalle impostazioni dell'interfaccia (se non trovi la voce, guarda `http://localhost:8889/docs`: la rotta `/api/auth/api-keys` esiste). La chiave si vede una sola volta: copiala subito nel `.env` come `LOCAL_MODEL_API_KEY`.
4. Verifica con una cella del notebook (vedi sotto).

### Opzione B: Ollama

```bash
ollama pull <modello>        # un modello quantizzato da 0.8 a 9 miliardi di parametri
ollama run <modello> "ciao"  # prova rapida
```

Indirizzo tipico: `http://localhost:11434/v1`. Nessuna chiave: lascia `LOCAL_MODEL_API_KEY` con un valore qualsiasi.

### Opzione C: llama-server (llama.cpp)

```bash
llama-server -m /percorso/al/modello.gguf --port 8080
```

Indirizzo: `http://localhost:8080/v1`. Espone anche le log-probabilità, utili per l'ottimizzazione O1 (cascade).

### Test del server locale (cella del notebook)

```python
import os, httpx
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
URL = os.getenv("LOCAL_MODEL_URL")
H = {"Authorization": f"Bearer {os.getenv('LOCAL_MODEL_API_KEY')}"}
MODEL = os.getenv("LOCAL_MODEL")

print(httpx.get(URL + "/models", headers=H, timeout=10).json())   # modelli e campo "loaded"

schema = {"name": "answer", "schema": {"type": "object",
          "properties": {"answer": {"type": "boolean"}}, "required": ["answer"]}}
casi = {
    "positivo (atteso true)": "Super Mario Bros. is a 1985 side-scrolling game where the player jumps across platforms.",
    "negativo (atteso false)": "Gran Turismo is a 1997 racing game where the player drives licensed cars on circuits.",
}
for nome, testo in casi.items():
    body = {"model": MODEL, "temperature": 0, "max_tokens": 300,
            "messages": [{"role": "user", "content": f"Criterion: the game is a platformer\nInput: {testo}"}],
            "response_format": {"type": "json_schema", "json_schema": schema}}
    r = httpx.post(URL + "/chat/completions", json=body, headers=H, timeout=120)
    print(nome, "->", r.status_code)
    print("   ", r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else r.text[:300])
```

Esito atteso: `200` e `{"answer": true}` / `{"answer": false}`. Questo test mostra che il percorso funziona, non quanto il modello sia buono sui dati veri: con modelli molto compressi aspettatevi errori e qualche risposta fuori formato (parse failure).

## 8. Modello a pagamento: Google (da usare solo quando la pipeline funziona)

Il modello a pagamento si usa solo per i run che contano. Budget indicativo del corso: 50 $ a testa su Google (credito "Graph Databases", valido dal 13 ottobre 2026 al 1 ottobre 2027) più 100 $ su Azure.

### 8.1 Crediti e fatturazione

1. In Console Cloud apri **Fatturazione → Crediti** e controlla che il credito sia "Disponibile" (importo, scadenza, ambito).
2. Il credito sta sull'**account di fatturazione**. Un progetto lo usa solo se è collegato: nella pagina del progetto, se compare "Questo progetto non è associato a un account di fatturazione", premi **Collega un account di fatturazione** e scegli quello con i crediti.
3. Evita di creare altre risorse nel progetto (macchine virtuali, database): consumerebbero gli stessi crediti.

### 8.2 Limite di spesa

In **Fatturazione → Budgets & caps** crea un budget con *Applicazione del limite di spesa*, sul progetto e sul servizio **Gemini API** (`generativelanguage.googleapis.com`), mensile, con importo basso (2 $ per i primi test) e avvisi al 50%, 80% e 100%.

- L'applicazione non è immediata: una piccola eccedenza può essere addebitata.
- Il servizio viene messo in pausa fino alla rimozione del limite: se le chiamate falliscono all'improvviso, controlla qui.
- Il limite copre solo Gemini API. Se si usasse Vertex AI, servirebbe un altro limite.
- Quando passate ai run veri, alzate il limite in base alla stima dei costi.
- Facoltativo: un budget *Solo avvisi* su tutto l'account (per esempio 20-25 $).

### 8.3 API e chiave

1. Con il progetto attivo cerca **Gemini API** (Prodotto Marketplace, Google) e premi **Abilita**. È il servizio `generativelanguage.googleapis.com`.
2. **API e servizi → Credenziali → Crea credenziali → Chiave API**. Nome riconoscibile (esempio: `gdb-gemini`).
3. Nel pannello, "API selezionate" deve mostrare **Gemini API**.
4. Google richiede di associare la chiave a un **service account**. Creane uno (esempio: `gdb-gemini-sa`). Il ruolo è facoltativo: **non assegnarne** (evita Writer e Admin). **Non creare né scaricare un file di chiave JSON.**
5. Lascia le restrizioni delle applicazioni su "Nessuna" (una restrizione per IP ti blocca se il tuo IP cambia).
6. Copia la chiave subito nel `.env` come `GOOGLE_API_KEY=...`. Non incollarla in chat, notebook o commit. Controlla con `git check-ignore -v .env`.
7. Se una chiamata risponde `403`, il messaggio indica il permesso mancante: assegnalo al service account da *IAM e amministrazione*.

### 8.4 Test senza costo: elenco dei modelli

```python
import os, httpx
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
key = os.getenv("GOOGLE_API_KEY")
r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models",
              headers={"x-goog-api-key": key}, timeout=30)
print(r.status_code)
print([m["name"] for m in r.json().get("models", [])][:15] if r.status_code == 200 else r.text[:300])
```

Esito atteso: `200` e un elenco di modelli. Verificato dal gruppo con la procedura sopra.

### 8.5 Test di generazione (una sola chiamata)

Scegli un modello **flash** dall'elenco e togli il prefisso `models/`. Poche parole di risposta, costo trascurabile. Usa l'indirizzo compatibile OpenAI di Gemini (non verificato per tutte le chiavi: se risponde con un errore, annota il messaggio).

```python
import os, httpx
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
key = os.getenv("GOOGLE_API_KEY")
MODEL = "nome-del-modello-flash"

body = {"model": MODEL, "temperature": 0, "max_tokens": 300,
        "messages": [{"role": "user", "content":
            "Criterion: the game is a platformer\n"
            "Input: Super Mario Bros. is a 1985 side-scrolling game where the player jumps across platforms."}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "answer", "schema": {"type": "object",
            "properties": {"answer": {"type": "boolean"}}, "required": ["answer"]}}}}
r = httpx.post("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               json=body, headers={"Authorization": f"Bearer {key}"}, timeout=60)
print(r.status_code)
print(r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else r.text[:300])
```

Se il contenuto esce vuoto o troncato, il modello sta ragionando e consuma i token: alza `max_tokens`. Dopo il test controlla in **Fatturazione → Crediti** che il consumo compaia (i dati possono arrivare con qualche ora di ritardo).

Le chiamate fuori dal gateway servono solo a verificare la chiave. Gli esperimenti passano dal gateway (cache e log).

## 9. Avvia il gateway

*(da completare dopo il 12 novembre: comando di avvio, configurazione di cache, log, listino prezzi e tetto di budget; come si collega al server locale con token)*

## 10. Avvia Jupyter e verifica l'ambiente

Dalla radice del repository, con l'ambiente attivo:

```bash
jupyter notebook
```

I notebook stanno in `notebooks/`. Crea `notebooks/00_check_ambiente.ipynb`, seleziona il kernel **Python (progetto GDB)** ed esegui:

```python
import sys, os
from dotenv import load_dotenv, find_dotenv
import pandas, pyoxigraph

load_dotenv(find_dotenv(usecwd=True))     # il notebook parte da notebooks/, il .env sta nella radice
print("Python:", sys.executable)          # deve contenere .venv
print("pandas:", pandas.__version__, "| pyoxigraph:", pyoxigraph.__version__)
for v in ["LOCAL_MODEL_URL", "LOCAL_MODEL_API_KEY", "GOOGLE_API_KEY"]:
    print(v, "presente:", bool(os.getenv(v)))
```

Poi, quando il gateway è pronto, esegui il **test M1**: una chiamata semantica da una query, attraverso il gateway, fino al modello locale e ritorno, su dieci entità.

Infine controlla il checker (dalla radice):

```bash
python tools/semops_check.py . --data games=data/games --results eval/results.csv
```

Con un solo dominio non è verificato che funzioni: il comando del professore usa `films` e `games`.

## Problemi comuni

| Sintomo                                           | Causa e rimedio                                                                                                                                              |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `No matching distribution found for numpy==...`   | Quella versione non esiste. Metti `numpy` senza versione, installa, poi pinna la versione installata (passo 3)                                               |
| Errore su `fastembed` o `onnxruntime`             | Può mancare un pacchetto per la tua versione di Python. Commenta la riga con `#`: serve solo al blocking (M2/M3). Poi usa un ambiente con Python 3.12 o 3.13 |
| PowerShell non attiva `.venv`                     | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, poi riprova                                                                                           |
| `presente: False` per una variabile               | Il `.env` non esiste o non è nella radice. Crealo con `cp`/`copy` e riavvia il kernel del notebook                                                           |
| Il server locale risponde `401 Not authenticated` | Manca il token Bearer: crea la chiave (passo 7) e mettila in `LOCAL_MODEL_API_KEY`                                                                           |
| `/v1/models` mostra `loaded: False`               | Carica il modello nell'interfaccia di Unsloth prima della chiamata                                                                                           |
| Un file di dati compare in `git status`           | Non fare commit. `.gitignore` non toglie file già tracciati: usa `git rm -r --cached <percorso>`                                                             |

## Flusso di lavoro con Git

1. `git pull` prima di iniziare.
2. Commit piccoli con messaggi chiari. Prima di `git add` guarda `git status`: niente dati, store o `.env`.
3. Se aggiungi una libreria, aggiornala in `requirements.txt` e avvisa gli altri (devono rieseguire il passo 3).
4. Se cambi un prompt, aggiorna la sua versione e annotalo nel log (vedi `CONVENZIONI.md`).
5. Prima di ogni consegna: clone pulito, su un'altra macchina, e prova della riproduzione.