# Setup dell'ambiente

Guida per configurare il progetto su Linux, macOS e Windows. Tempo stimato: 45 minuti (più il download del modello locale).

> Le parti sul **gateway** vanno completate dopo la lezione del 12 novembre. Dove manca il dettaglio c'è l'indicazione *(da completare)*.

**Convenzione sui comandi.** Prima di attivare l'ambiente virtuale (passo 2) si usa `python3` su Linux/macOS e `py` su Windows. Dopo l'attivazione si usa sempre `python`, che è uguale su tutti i sistemi. Nei blocchi con tre varianti si esegue solo quella del proprio sistema.

## 0. Prerequisiti

- **Git**
- **Python 3.12 o superiore.** Verifica: `python3 --version` (Linux/macOS) oppure `py --version` (Windows). La procedura è stata provata con Python 3.14. Per `fastembed` (usato solo dal blocking, fase M2/M3) non è verificato che esista un pacchetto per tutte le versioni di Python.
- Accesso al repository (SSH configurato oppure token GitHub)
- **GraphDB Free 11.5.0** (l'engine scelto dal gruppo), con **Docker** oppure installato in locale; la Workbench è su `http://localhost:7200`. Per sviluppare l'estensione Java servono anche **JDK 21** e **Maven** (non servono per importare e interrogare i dati).
- Un **server di modelli locale** con indirizzo compatibile OpenAI: Unsloth Studio (usato dal gruppo), Ollama o `llama-server` di llama.cpp
- Pacchetto dati **films** (da Moodle/Drive del corso), che contiene anche i loader e il checker

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

# GraphDB (repository locali; le URL sono proprie di ogni macchina)
GRAPHDB_URL=http://localhost:7200
GRAPHDB_REPO_DEV=films-dev
GRAPHDB_REPO_DEV_GT=films-dev-gt
GRAPHDB_REPO_EVAL=films-eval
GRAPHDB_REPO_EVAL_GT=films-eval-gt

# Gateway (da completare dopo il 12 novembre)
GATEWAY_URL=http://127.0.0.1:8000/v1
```

Aggiungi a `.env.example` le stesse variabili con valori vuoti o segnaposto. Per **Ollama**, invece dei valori Unsloth dell'esempio, usa `LOCAL_MODEL_URL=http://localhost:11434/v1`, `LOCAL_MODEL_API_KEY=ollama`(segnaposto, non una vera chiave) e `LOCAL_MODEL=qwen2.5:3b` se è il modello installato.

Controlla che Git ignori `.env` (devono comparire la regola e nessun file nuovo):

```bash
git check-ignore -v .env
git status
```

Non incollare chiavi in chat, notebook, commit o messaggi. Nel repository non ci devono essere segreti, nemmeno nella cronologia.

## 6. Inserisci i dati e gli strumenti

Nel progetto ci sono **due cartelle `tools/` diverse**. Non vanno confuse.

| Cartella            | Dove                     | Contenuto                                                                                   | Su Git?                               |
| ------------------- | ------------------------ | ------------------------------------------------------------------------------------------- | ------------------------------------- |
| `data/films/tools/` | dentro il pacchetto dati | `semops_check.py` (i loader `load_*.py` del pacchetto non servono con GraphDB)              | no (`data/films/` è nel `.gitignore`) |
| `tools/`            | radice del repository    | copia di `semops_check.py` (fornito dal professore, non modificare) e `prices.example.json` | sì                                    |

Il pacchetto dati `films` va in `data/films/` e contiene `README.md`, `MANIFEST.sha256`, `dev/`, `eval/` e `tools/`. **Non va su Git.** Verifica che `.gitignore` contenga `data/films/` (e, se usi l’estensione Java, `graphdb-extension/target/`).

Dal materiale del professore si copiano così:

```text
data/films/tools/semops_check.py  ->  tools/semops_check.py      (checker, non modificare)
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

Dalla cartella `data/films/`:

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

L'altro dominio (games) arriva con il pool, il 21 dicembre.

### Avvia GraphDB

Scegli **una** delle due strade. Con tutte e due gli stessi quattro repository e gli stessi controlli valgono uguali.

**Con Docker (consigliata per chi non vuole installare GraphDB).** Il file `docker-compose.yml` nella radice del repository avvia GraphDB. Tre scelte da conoscere:

- **Versione.** L'immagine è `ontotext/graphdb`, con il tag in `GRAPHDB_TAG` (predefinito 10.7.4, quello già provato dal gruppo). Le slide del corso indicano GraphDB 11.5.0, che include RDF4J 5.3.1, la versione contro cui è compilato il `pom.xml`. Prima di sviluppare l'estensione Java, controlla che il tag 11.5.0 esista su Docker Hub e provalo con una **cartella dati nuova** (non riusare quella della 10.7.4: il formato potrebbe non essere compatibile). Controlla anche la versione di Java dentro il container, perché il `pom.xml` compila per Java 21: `docker exec graphdb java -version`.
- **Dati di GraphDB.** Il volume `GRAPHDB_HOME` (predefinito `docker-data/graphdb-home`, ignorato da Git) è dove GraphDB tiene i repository. Se hai già una cartella dati fuori dalla repo, metti nel `.env``GRAPHDB_HOME=/percorso/assoluto/graphdb-data`. I file lì dentro appartengono a `root` perché li scrive il container: è normale.
- **File da importare.** Il volume `GRAPHDB_IMPORT` (predefinito `data/films`, in sola lettura) è visibile nella Workbench in **Import → Server files**. Così `dev/graph.nt` ed `eval/graph.nt` si caricano senza passare dal browser.

Comandi, dalla radice del repository:

```bash
docker compose up -d
docker compose ps          # il servizio deve risultare in esecuzione
```

Poi apri `http://localhost:7200`: deve comparire la Workbench.

**Installazione locale.** Scarica GraphDB Free 11.5.0, avvialo e apri `http://localhost:7200`. Il jar dell'estensione si copierà nella cartella `lib/` della distribuzione.

**Licenza.** Le slide del corso avvertono che la valutazione delle query richiede una licenza e che, senza, ogni query fallisce. Con GraphDB 10.7.4 Free, senza file di licenza, il gruppo ha già eseguito query: se passi alla 11.5.0, ripeti la prova con una query qualsiasi dalla Workbench e, se fallisce, annota il messaggio in `docs/log.md`.

### Carica il grafo con GraphDB

Servono **due repository separati per ogni set (dev ed eval)**. Quello senza statement nascoste serve per far girare le query semantiche. Quello con le statement nascoste serve solo per il punteggio e per le answer key. Così si riduce il rischio di leakage.

1. Con GraphDB avviato (sezione precedente), apri `http://localhost:7200`.
2. In **Setup → Repositories → Create new repository → GraphDB Repository**, crea i quattro repository qui sotto. Seleziona **Ruleset: Empty (no inference)** per tutti, disabilita `owl:sameAs` se l'opzione è presente, e mantieni le altre impostazioni coerenti. Il ruleset Empty è una scelta del gruppo per avere una baseline senza inferenza automatica, non un vincolo delle slide.
3. Seleziona ciascun repository e vai su **Import → User data → Upload RDF files**. Importa i file N-Triples indicati nella tabella nel **default graph**. Non aggiungere `hidden.nt` ai repository usati dagli operatori.

| Repository      | File da importare                                        | Scopo                                |
| --------------- | -------------------------------------------------------- | ------------------------------------ |
| `films-dev`     | `data/films/dev/graph.nt`                                | Sviluppo, senza risposte nascoste    |
| `films-dev-gt`  | `data/films/dev/graph.nt` + `data/films/dev/hidden.nt`   | Ground truth sviluppo                |
| `films-eval`    | `data/films/eval/graph.nt`                               | Valutazione, senza risposte nascoste |
| `films-eval-gt` | `data/films/eval/graph.nt` + `data/films/eval/hidden.nt` | Ground truth valutazione             |

> GraphDB Free consente al massimo cinque repository utilizzabili: con questi quattro rimane uno slot. Non caricare ripetutamente gli stessi file nello stesso repository senza verificarne prima il contenuto.

**Controllo.** Nel pannello **SPARQL** di GraphDB, seleziona un repository alla volta ed esegui:

```sparql
PREFIX ex: <http://example.org/semop/>
SELECT (COUNT(DISTINCT ?e) AS ?n)
WHERE { ?e ex:inSet ex:set-main . }
```

Atteso: `1000` in `films-dev` e `films-dev-gt`; `4000` in `films-eval` e `films-eval-gt`.

Nei **soli** repository `-gt`, puoi verificare anche la ground truth espansa della Q1 (Seconda guerra mondiale):

```sparql
PREFIX ex: <http://example.org/semop/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT (COUNT(DISTINCT ?e) AS ?n)
WHERE {
  ?e ex:inSet ex:set-main ;
     wdt:P921/(wdt:P279|wdt:P361)* wd:Q362 .
}
```

Atteso: `200` in `films-dev-gt`, `852` in `films-eval-gt`. Usare `eval` solo per le verifiche iniziali e per la valutazione finale: non calibrare i modelli su quel set.

**Test Python → GraphDB** (dalla radice del repository, con `.venv` attivo; va bene anche in un notebook):

```python
import os, httpx
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
endpoint = os.environ["GRAPHDB_URL"].rstrip("/") + "/repositories/" + os.environ["GRAPHDB_REPO_DEV"]
query = """PREFIX ex: <http://example.org/semop/>
SELECT (COUNT(DISTINCT ?e) AS ?n) WHERE { ?e ex:inSet ex:set-main . }"""
r = httpx.post(endpoint, data={"query": query},
               headers={"Accept": "application/sparql-results+json"}, timeout=30)
r.raise_for_status()
print(r.json()["results"]["bindings"][0]["n"]["value"])  # atteso: 1000
```

### Estensione Java

**A cosa serve.** GraphDB non può chiamare codice Python dentro una query. Il suo punto di estensione è una funzione scritta in Java (RDF4J *Function SPI*) dentro un file `.jar`, che GraphDB carica all'avvio. Quando il jar è caricato, una query può scrivere `FILTER(sem:filter(...))` e GraphDB esegue la funzione. La funzione `sem:filter` riceve il testo τ, la condizione ℓ e il nodo del run, manda una richiesta HTTP al gateway e restituisce `true` o `false`. Non è un server separato: gira dentro GraphDB. Tutto il resto del progetto (operatori, piani, τ, valutazione) resta in Python.

**Stato attuale.** In `graphdb-extension/` c'è solo la funzione di prova `echo` (IRI `http://example.org/semop/function/echo`), che restituisce il proprio argomento. Serve a verificare che il jar venga caricato. Non implementa ancora nessun operatore semantico. L'integrazione con il gateway resta al passo 9.

**Come si compila.** Servono JDK 21 e Maven. Da `graphdb-extension/`:

```bash
mvn clean package
```

Il risultato è `target/graphdb-extension-0.1.0.jar`. Non mettere `target/` su Git.

**Come si carica in GraphDB.**

- *Installazione locale:* copia il jar nella cartella `lib/` della distribuzione e riavvia GraphDB.
- *Docker:* nel `docker-compose.yml` c'è già una riga commentata che monta il jar nella cartella `lib/` del container. Dopo `mvn clean package`, togli il commento e riavvia con `docker compose up -d --force-recreate`. Se il file non esiste quando avvii il container, Docker crea una **cartella** al suo posto. Il percorso `/opt/graphdb/dist/lib` è *da verificare*: `docker exec graphdb ls /opt/graphdb/dist/lib` deve mostrare i jar di GraphDB.

**Come si prova.** Dalla Workbench (pannello SPARQL), su qualsiasi repository:

```sparql
SELECT ?x WHERE { BIND(<http://example.org/semop/function/echo>("ciao") AS ?x) }
```

Se il jar è caricato, `?x` vale `ciao`. Se la query dà errore di funzione sconosciuta, il jar non è nella cartella giusta o GraphDB non è stato riavviato. Le slide del corso segnalano che il deployment dentro GraphDB non è stato provato dai docenti: **annotate in `docs/log.md` tutto quello che osservate**.

**Cosa verrà dopo (per il design note).** Si sviluppa `sem:filter` e si prova su un RDF4J in memoria, dove il ciclo di prova dura secondi; solo dopo si carica in GraphDB. Per leggere il JSON della risposta servirà probabilmente la libreria Jackson (scope `provided`, già presente in GraphDB secondo le slide). L'indirizzo del gateway si passa come proprietà di sistema. Con Docker, il gateway gira sul computer ospite e il container non lo raggiunge con `localhost`: nel compose ci sono, commentate, le righe per usare `host.docker.internal` e la proprietà `GDB_JAVA_OPTS` *(da verificare)*.

### τ come dati nel grafo *(da completare)*

La funzione Java gira dentro GraphDB e riceve τ come argomento: non può chiamare `src/tau.py`. Quindi uno script in `src/` (da scrivere) costruisce τ per ogni film con la funzione Python e scrive una tripla `ex:tau` per film in un **named graph per variante** (esempio: `ex:tau-t0_v1`), nei repository senza nascoste. Le query leggono τ da quel graph e la passano a `sem:filter`.

## 7. Modello locale per lo sviluppo

Durante lo sviluppo si usa un modello piccolo sulla propria macchina. Non si spende nulla e si testa l'architettura. Serve un server con indirizzo compatibile OpenAI (`.../v1/chat/completions`).

### Opzione A: Unsloth Studio (usata dal gruppo)

1. Avvia Unsloth Studio. L'interfaccia web è su `http://localhost:8889` (la porta può cambiare: controlla l'indirizzo mostrato all'avvio).
2. Carica un modello GGUF dall'interfaccia. Modelli provati: `unsloth/gemma-4-E2B-it-GGUF` (2,3 GB, molto compresso, veloce, risposte semplici) e `unsloth/Qwen3.5-9B-MTP-GGUF` (4,5 GB, più capace). Il campo `loaded` di `/v1/models` dice quale è caricato.
3. Il server richiede un **token Bearer**. Crea una chiave API dalle impostazioni dell'interfaccia (se non trovi la voce, guarda `http://localhost:8889/docs`: la rotta `/api/auth/api-keys` esiste). La chiave si vede una sola volta: copiala subito nel `.env` come `LOCAL_MODEL_API_KEY`.
4. Verifica con `notebooks/00_check_environment.ipynb` (vedi passo 10).

### Opzione B: Ollama

```bash
ollama pull <modello>        # un modello quantizzato da 0.8 a 9 miliardi di parametri
ollama run <modello> "ciao"  # prova rapida
```

Indirizzo tipico: `http://localhost:11434/v1`. Nessuna vera chiave locale: usa `LOCAL_MODEL_API_KEY=ollama`come segnaposto. Esempio verificato su macOS: `ollama pull qwen2.5:3b`, poi `LOCAL_MODEL=qwen2.5:3b` nel `.env`.

### Opzione C: llama-server (llama.cpp)

```bash
llama-server -m /percorso/al/modello.gguf --port 8080
```

Indirizzo: `http://localhost:8080/v1`. Espone anche le log-probabilità, utili per l'ottimizzazione O1 (cascade).

### Test del server locale (cella del notebook)

Il notebook `notebooks/00_check_environment.ipynb` esegue questo controllo leggendo `LOCAL_MODEL_URL`, `LOCAL_MODEL_API_KEY` e `LOCAL_MODEL` dal `.env`; funziona con Ollama o Unsloth Studio.

```python
import os, httpx
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
URL = os.getenv("LOCAL_MODEL_URL")
H = {"Authorization": f"Bearer {os.getenv('LOCAL_MODEL_API_KEY')}"}
MODEL = os.getenv("LOCAL_MODEL")

print(httpx.get(URL + "/models", headers=H, timeout=10).json())   # lista modelli; Unsloth può indicare "loaded"

casi = {
    "positivo (atteso true)": "Dunkirk follows Allied soldiers trapped on the beaches of France in 1940 during World War II.",
    "negativo (atteso false)": "A romantic comedy follows two people falling in love in modern-day Paris.",
}
for nome, testo in casi.items():
    body = {"model": MODEL, "temperature": 0, "max_tokens": 300,
            "messages": [{"role": "system", "content": 'Reply only with JSON containing a boolean field named "answer".'},
                         {"role": "user", "content": f"Criterion: the film deals with the Second World War\nInput: {testo}"}],
            "response_format": {"type": "json_object"}}
    r = httpx.post(URL + "/chat/completions", json=body, headers=H, timeout=120)
    print(nome, "->", r.status_code)
    print("   ", r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else r.text[:300])
```

Esito atteso: `200` e `{"answer": true}` / `{"answer": false}`. Il formato JSON va controllato: il campo `answer`deve essere booleano. Questo test mostra che il percorso funziona, non quanto il modello sia buono sui dati veri: con modelli molto compressi aspettatevi errori e qualche risposta fuori formato (parse failure).

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
            "Criterion: the film deals with the Second World War\n"
            "Input: Dunkirk follows Allied soldiers trapped on the beaches of France in 1940 during World War II."}],
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

I notebook stanno in `notebooks/`. Apri `notebooks/00_check_environment.ipynb`, seleziona il kernel **Python (progetto GDB)** ed esegui.

Il notebook controlla:

1. **Ambiente Python e `.env`** — stampa il percorso di Python, le versioni di `pandas` e `httpx` e la presenza delle variabili di configurazione (non stampa le chiavi). `GOOGLE_API_KEY` è facoltativa durante lo sviluppo locale.
2. **Connessione a GraphDB** — usa `GRAPHDB_URL` e `GRAPHDB_REPO_DEV` per interrogare `films-dev`; il risultato atteso per il main set è **1000**.
3. **Server locale** — interroga l'endpoint `LOCAL_MODEL_URL/models` di Ollama o Unsloth Studio, secondo il `.env` personale.
4. **Test del modello locale** — invia due esempi *films* con il criterio Q1 (Seconda guerra mondiale), verifica che la risposta sia JSON e che `answer` sia un booleano. Non sono esempi del benchmark.
5. **Google (facoltativo)** — conserva i controlli per la chiave e i modelli Google. Il test che genera testo con un modello a pagamento è **disabilitato di default** (`ESEGUI_TEST_GOOGLE_A_PAGAMENTO = False`): abilitalo solo quando serve.

Per eseguire il notebook dalla radice del repository, avvia `jupyter notebook`, apri `notebooks/00_check_environment.ipynb` e seleziona il kernel corretto. In alternativa aprilo direttamente in VS Code con l'estensione Jupyter.

Poi, quando il gateway è pronto, esegui il **test M1**: una chiamata semantica da una query, attraverso il gateway, fino al modello locale e ritorno, su dieci entità.

Infine controlla il checker (dalla radice):

```bash
python tools/semops_check.py . --data films=data/films --results eval/results.csv
```

Con un solo dominio non è verificato che funzioni: il comando del professore usa `films` e `games`. Se il checker richiede entrambi, eseguirlo solo quando sarà disponibile anche `data/games/`.

## Problemi comuni

| Sintomo                                              | Causa e rimedio                                                                                                                                              |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `No matching distribution found for numpy==...`      | Quella versione non esiste. Metti `numpy` senza versione, installa, poi pinna la versione installata (passo 3)                                               |
| Errore su `fastembed` o `onnxruntime`                | Può mancare un pacchetto per la tua versione di Python. Commenta la riga con `#`: serve solo al blocking (M2/M3). Poi usa un ambiente con Python 3.12 o 3.13 |
| PowerShell non attiva `.venv`                        | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, poi riprova                                                                                           |
| `presente: False` per una variabile                  | Il `.env` non esiste o non è nella radice. Crealo con `cp`/`copy` e riavvia il kernel del notebook                                                           |
| Il server Unsloth risponde `401 Not authenticated`   | Manca il token Bearer: crea la chiave (passo 7) e mettila in `LOCAL_MODEL_API_KEY`                                                                           |
| `/v1/models` mostra `loaded: False`                  | Carica il modello nell'interfaccia di Unsloth prima della chiamata                                                                                           |
| `Connection refused` verso `localhost:7200`          | GraphDB non è avviato: con Docker `docker compose up -d`, poi `docker compose ps`e `docker compose logs`                                                     |
| Ogni query a GraphDB fallisce                        | Probabile problema di licenza (le slide lo segnalano): leggi il messaggio e annotalo in `docs/log.md`                                                        |
| La funzione `echo` dà errore di funzione sconosciuta | Il jar non è nella cartella `lib/` giusta, oppure GraphDB non è stato riavviato dopo la copia                                                                |
| Docker ha creato una cartella al posto del jar       | Il jar non esisteva al primo avvio: costruiscilo con `mvn clean package`, cancella la cartella creata e riavvia                                              |
| Un file di dati compare in `git status`              | Non fare commit. `.gitignore` non toglie file già tracciati: usa `git rm -r --cached <percorso>`                                                             |

## Flusso di lavoro con Git

1. `git pull` prima di iniziare.
2. Commit piccoli con messaggi chiari. Prima di `git add` guarda `git status`: niente dati, store o `.env`.
3. Se aggiungi una libreria, aggiornala in `requirements.txt` e avvisa gli altri (devono rieseguire il passo 3).
4. Se cambi un prompt, aggiorna la sua versione e annotalo nel log (vedi `CONVENZIONI.md`).
5. Prima di ogni consegna: clone pulito, su un'altra macchina, e prova della riproduzione.