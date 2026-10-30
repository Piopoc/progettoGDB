# Setup dell'ambiente

Guida per configurare il progetto su Linux, macOS e Windows. Tempo stimato: 15 minuti.

## 0. Prerequisiti

- **Git**
- **Python 3.10 o superiore** (`python3 --version` su Linux/macOS, `py --version` su Windows)
- Accesso al repository (SSH configurato oppure token GitHub)
- **Protégé** e **GraphDB** (scaricabili dai siti ufficiali)

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
Se PowerShell blocca lo script, esegui una volta:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Windows (cmd)**
```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

Se l'ambiente è attivo, il prompt mostra `(.venv)` all'inizio.

> **Non spostare né rinominare la cartella `.venv` o il repository dopo averla creata**: i venv contengono percorsi assoluti e si rompono. Se succede, cancella `.venv` e ripeti questo passaggio.

## 3. Installa le dipendenze

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Usa sempre `python -m pip`, mai `pip` da solo: garantisce di installare nell'ambiente attivo.

## 4. Registra il kernel per Jupyter

```bash
python -m ipykernel install --user --name progetto-gdb --display-name "Python (progetto GDB)"
```

Nei notebook seleziona **Kernel → Change kernel → Python (progetto GDB)**.

## 5. Configura la tua chiave API (file `.env`)

Ognuno usa **la propria chiave** e non la condivide con nessuno.

**Linux / macOS**
```bash
cp .env.example .env
```

**Windows**
```powershell
copy .env.example .env
```

Apri `.env` e inserisci la chiave dopo il simbolo `=`, senza spazi né virgolette:
```text
GOOGLE_API_KEY=la_tua_chiave
```

Il file `.env` è nel `.gitignore`: non verrà mai committato. Non incollare la chiave in chat, notebook o commit.

## 6. Inserisci i dati

I CSV non sono nel repository (o solo in parte). Copiali nella cartella indicata dal team (es. `data/example2_soccer/`). Controlla che i percorsi nei notebook funzionino.

## 7. Avvia Jupyter

Dalla radice del repository, con l'ambiente attivo:

```bash
jupyter notebook
```

## 8. Verifica che tutto funzioni

Crea una cella nel notebook ed eseguila:

```python
import sys, os
from dotenv import load_dotenv
import pandas, rdflib

load_dotenv()
print("Python:", sys.executable)          # deve contenere .venv
print("pandas:", pandas.__version__, "| rdflib:", rdflib.__version__)
print("Chiave presente:", bool(os.getenv("GOOGLE_API_KEY")))   # deve stampare True
```

Se tutto è corretto, sei pronto.

## Flusso di lavoro con Git

1. `git pull` prima di iniziare.
2. Commit piccoli con messaggi chiari.
3. Se aggiungi una libreria, aggiornala in `requirements.txt` e avvisa gli altri (devono rieseguire il passo 3).
