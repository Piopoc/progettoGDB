# Convenzioni del team

Regole condivise per codice, dati e Git. Se una regola non basta, si discute e si aggiorna questo file.

## 1. Codice

- Il codice è **modulare e senza valori hardcoded**. Chiavi API, indirizzi, nomi di modello, nomi dei repository di GraphDB, query e percorsi stanno in file `.env`, file di configurazione o file di query, mai dentro le classi.
- **τ è parametrica.** La funzione che costruisce il testo di un binding legge dalla configurazione (`prompts/tau_<variante>_v<N>.json`) quali campi usare. Così funziona sia su film sia su videogiochi (serve per il pool).
- Una funzione fa una cosa. Gli operatori non conoscono l'engine: parlano con GraphDB tramite il **binding** (client SPARQL in Python e funzione `sem:*` in Java).
- **Divisione dei linguaggi.** Java solo per la funzione semantica che GraphDB carica (cartella `java/`). Tutto il resto (operatori, piani, τ, valutazione, materializzazione) è Python.
- Python: nomi in `snake_case`, classi in `PascalCase`, type hint sulle funzioni pubbliche, docstring brevi.
- Pattern consigliati: file di proprietà per le query preparate, *factory* per creare oggetti (client di GraphDB, client del gateway), nessuna logica nei notebook.
- Se un assistente di coding scrive del codice, **lo si legge e lo si capisce** prima del commit. Ogni uso va annotato in `docs/uso_assistenti.md` (serve per la sezione del report).

## 2. Chiamate al modello

- **Ogni chiamata passa dal gateway.** Niente chiamate dirette al modello dal codice del progetto. Fino alla lezione del 12 novembre si usa un client sottile (`src/llm_client.py`) con la stessa interfaccia del gateway, da sostituire dopo la lezione. I test del notebook che chiamano il modello direttamente servono solo a verificare l'ambiente.
- La funzione Java chiama l'indirizzo del gateway, preso dalla configurazione (`GATEWAY_URL`), non dal codice.
- Il gateway dà cache, log, prezzo e validazione dello schema. Una risposta che non rispetta lo schema è un **parse failure**: si registra a parte e non è mai un negativo.
- Temperatura 0 e seed fisso. Le ripetizioni volute si riportano come varianza.
- Si sviluppa con il **modello locale**. Il modello a pagamento si usa solo per i run che contano.
- Budget massimo per esperimento: `<da fissare>`. Un run che lo supera diventa un **run campionato**, con la dimensione del campione scritta nel report.

## 3. Prompt e τ come dati versionati

- Tutti i prompt stanno in `prompts/`, un file per prompt, con numero di versione nel nome (esempio: `filter_v1.txt`).
- Le configurazioni di τ stanno in `prompts/`, una per variante (esempio: `tau_t0_v1.json`, dove `t0` è la baseline e `v1` la versione).
- Il testo della condizione ℓ di ogni query comune è **fisso** (vedi il documento delle query) ed entra nel prompt come `Criterion: <ℓ>`.
- **Si congelano prompt e τ prima di calibrare.** Il testo di τ entra nella chiave della cache: cambiarlo dopo aver raccolto risposte significa rifare le chiamate. Se si cambia un prompt o una τ dopo la calibrazione, si ricalibra e lo si scrive nel report.
- Una modifica a una τ già usata non si fa sul file esistente: si crea una nuova versione (`_v2`) o una nuova variante.
- Ogni run file registra la versione del prompt e della τ usate.

## 4. Dati e leakage

- Le statement nascoste (`hidden.nt`) si caricano **solo** per le answer key e per il punteggio. Non entrano mai in τ. Si usano repository GraphDB distinti: `films-dev` e `films-eval` per le query semantiche, `films-dev-gt` e `films-eval-gt` (con le nascoste) solo per lo scoring.
- Per i **film** le proprietà nascoste sono: *P921* (main subject), *P136* (genre), *P144* (based on), *P4969* (derivative work), *P2408* (set in period). Sui romanzi *P4969*. Non si ricostruiscono mai da altre fonti dentro τ.
- In `properties.csv` la colonna `tau_allowed_for_common_queries` dice quali proprietà possono entrare in τ nelle query comuni. Per i film: P31, P57, P58, P86, P161, P162, P272, P344, P364, P462, P495, P577, P750, P1040, P1431, P1657. Per i romanzi: P31, P50, P123, P407, P495, P577, P7937. Una proprietà non in elenco non entra in τ, anche se non è nascosta (esempio: P840, il bersaglio di Q5). Si rispetta anche per O4. `TauBuilder` rifiuta le proprietà non ammesse.
- Per τ si usa `description_screened` (non `description`): la descrizione grezza nomina spesso un valore nascosto, e per questo 74 film dev hanno la descrizione screened vuota. In quel caso il campo si salta, non si scrive "nan".
- Dopo ogni modifica a τ: controllo manuale su **20 positivi** e annotazione in `eval/leakage.md`. Una frase del lead che nomina la guerra è evidenza legittima. Un campo strutturato che nomina il valore nascosto non lo è.
- Con O4 (iniezione del vicinato) il rischio è alto: ogni configurazione si controlla prima del run, anche in modo automatico (il testo aggiunto non contiene i valori nascosti del film).
- Sviluppo e tuning sul **dev set**. L'eval set si esegue **una volta per piano**.
- Le answer key delle nostre query seguono la stessa costruzione di quelle comuni: espansione lungo `subclass of` (P279) e `part of` (P361).
- Le query che usano le answer key girano solo sui repository `-gt`. Sullo store senza nascoste le answer key di Q1 e Q6 devono restituire zero righe: è un controllo di leakage a livello di dati.

## 5. Query e piani

- Si fissa la **forma della query** prima di confrontare gli algoritmi. Altrimenti un piano sembra più economico solo perché manca un `DISTINCT` nell'altro.
- La forma di riferimento fa **una chiamata per binding distinto**: sottoquery `SELECT DISTINCT ?film ?tau` con `LIMIT` come barriera, e il `FILTER` fuori dalla sottoquery.
- Le chiamate si contano **nel log del gateway**, non nel codice Python. Si riportano sempre `n_function_calls` e `n_llm_calls`.
- Su GraphDB il piano di valutazione non si assume: si verifica contando le chiamate nel log. Le query `EXPLAIN` di GraphDB sono da provare e, se si usano, vanno annotate come osservazione.
- Una variabile che cambia da un piano all'altro (k, soglie, dimensione del blocco) è un parametro del piano e finisce in `plan_params`.

## 6. Namespace e identificatori

| Prefisso | IRI | Uso |
|---|---|---|
| `wd:` | `http://www.wikidata.org/entity/` | entità Wikidata |
| `wdt:` | `http://www.wikidata.org/prop/direct/` | proprietà dirette |
| `ex:` | `http://example.org/semop/` | termini del progetto (`ex:inSet`, `ex:tau`, `ex:run-...`) |
| `prov:` | `http://www.w3.org/ns/prov#` | provenance dei run |
| `sem:` | *(da definire con il binding)* | funzioni semantiche (`sem:filter`, `sem:classify`, `sem:join`). Lo stesso IRI va nel jar Java e nelle query. |

- **τ nel grafo.** Per ogni variante di τ, le triple `ex:tau` stanno in un named graph dedicato (esempio: `ex:tau-t0_v1`). Le query scelgono la variante indicando il graph.
- Identificatori di run: `g<NN>-<set>-<query>-<piano>` (esempio: `g07-eval-q1-ref`). Il nome del file deve coincidere con l'id nel file (il checker lo verifica).
- Query proprie: prefisso del gruppo nell'id (esempio: `g07-Q2`).
- Archi derivati: proprietà `ex:derived<Nome>`, un named graph per run, una reificazione per arco.
- File RDF: Turtle o TriG, UTF-8.

## 7. Git e Docker

1. `git pull` prima di iniziare.
2. Commit piccoli, messaggio all'imperativo e specifico (esempio: `Add sem_filter reference plan`).
3. Un ramo per attività grande, revisione di un altro membro prima del merge.
4. **Mai** su Git: chiavi, `.env`, dati del professore, modelli, ambienti virtuali, volumi di GraphDB, jar compilati (`java/target/`).
5. Su Git invece: `docker-compose.yml` (senza segreti, con la versione dell'immagine pinnata) e i sorgenti Java.
6. Nuova libreria: aggiornare `requirements.txt` (versione pinnata) e avvisare il gruppo. Per Java, le versioni stanno nel `pom.xml`.
7. Prima di una consegna: **clone pulito** su un'altra macchina e prova della riproduzione, compreso l'avvio di GraphDB.

## 8. Log di lavoro

Un file condiviso (`docs/log.md`). Per ogni sessione: data, chi, cosa, ore, blocchi. Le decisioni importanti (come il cambio di engine) vanno registrate con data e motivo. Serve per la dichiarazione dei contributi e per rispettare il limite di ore (**28 ore a M1, 73 a M2**: oltre, si parla con il professore).
