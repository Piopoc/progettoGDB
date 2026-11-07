# Convenzioni del team

Regole condivise per codice, dati e Git. Se una regola non basta, si discute e si aggiorna questo file.

## 1. Codice

- Il codice è **modulare e senza valori hardcoded**. Chiavi API, indirizzi, nomi di modello, query e percorsi stanno in file `.env`, file di configurazione o file di query, mai dentro le classi.
- **τ è parametrica.** La funzione che costruisce il testo di un binding legge dalla configurazione quali campi usare. Così funziona sia su film sia su videogiochi (serve per il pool).
- Una funzione fa una cosa. Gli operatori non conoscono l'engine: parlano con l'engine tramite il **binding**.
- Python: nomi in `snake_case`, classi in `PascalCase`, type hint sulle funzioni pubbliche, docstring brevi.
- Pattern consigliati: file di proprietà per le query preparate, *factory* per creare oggetti (engine, client del gateway), nessuna logica nei notebook.
- Se un assistente di coding scrive del codice, **lo si legge e lo si capisce** prima del commit. Ogni uso va annotato in `docs/uso_assistenti.md` (serve per la sezione del report).

## 2. Chiamate al modello

- **Ogni chiamata passa dal gateway.** Niente chiamate dirette al modello dal codice.
- Il gateway dà cache, log, prezzo e validazione dello schema. Una risposta che non rispetta lo schema è un **parse failure**: si registra a parte e non è mai un negativo.
- Temperatura 0 e seed fisso. Le ripetizioni volute si riportano come varianza.
- Si sviluppa con il **modello locale**. Il modello a pagamento si usa solo per i run che contano.
- Budget massimo per esperimento: `<da fissare>`. Un run che lo supera diventa un **run campionato**, con la dimensione del campione scritta nel report.

## 3. Prompt

- Tutti i prompt stanno in `prompts/`, un file per prompt, con numero di versione nel nome (esempio: `filter_v1.txt`).
- Il testo della condizione ℓ di ogni query comune è **fisso** (vedi il documento delle query) ed entra nel prompt come `Criterion: <ℓ>`.
- **Si congelano i prompt prima di calibrare.** Se si cambia un prompt dopo la calibrazione, si ricalibra e lo si scrive nel report.
- Ogni run file registra la versione del prompt usata.

## 4. Dati e leakage

- Le statement nascoste (`hidden.nt`, `--with-hidden` in Neo4j) si caricano **solo** per le answer key e per il punteggio. Non entrano mai in τ. Si usano due store distinti: `store-*` per le query semantiche e `store-*-gt` per lo scoring.
- Per i **videogiochi** le proprietà nascoste sono: sui giochi *P136* (genere), *P179* (serie), *P155* (segue), *P156* (seguito da), *P8345* (media franchise); sulle serie *P527* (ha parte). Non si ricostruiscono mai da altre fonti dentro τ.
- In `properties.csv` la colonna "may enter τ" dice quali proprietà possono entrare in τ nelle query comuni. Si rispetta, anche per O4.
- Per τ si usa `description_screened` (non `description`): la descrizione grezza nomina spesso il genere (visual novel: 110 su 659 giochi con articolo inglese).
- Dopo ogni modifica a τ: controllo manuale su **20 positivi** e annotazione in `eval/leakage.md`.
- Con O4 (iniezione del vicinato) il rischio è alto: ogni configurazione si controlla prima del run.
- Sviluppo e tuning sul **dev set**. L'eval set si esegue **una volta per piano**.
- Le answer key delle nostre query seguono la stessa costruzione di quelle comuni: espansione lungo `subclass of` (P279) e `part of` (P361).

## 5. Query e piani

- Si fissa la **forma della query** prima di confrontare gli algoritmi. Altrimenti un piano sembra più economico solo perché manca un `DISTINCT` nell'altro.
- La forma di riferimento fa **una chiamata per binding distinto** (SPARQL: sottoquery `DISTINCT` con `LIMIT` come barriera; Cypher: `WITH DISTINCT` poi `WHERE`).
- Le chiamate si contano **nel log del gateway**, non nel codice Python. Si riportano sempre `n_function_calls` e `n_llm_calls`.
- Una variabile che cambia da un piano all'altro (k, soglie, dimensione del blocco) è un parametro del piano e finisce in `plan_params`.

## 6. Namespace e identificatori

| Prefisso | IRI | Uso |
|---|---|---|
| `wd:` | `http://www.wikidata.org/entity/` | entità Wikidata |
| `wdt:` | `http://www.wikidata.org/prop/direct/` | proprietà dirette |
| `ex:` | `http://example.org/semop/` | termini del progetto (`ex:inSet`, `ex:tau`, `ex:run-...`) |
| `prov:` | `http://www.w3.org/ns/prov#` | provenance dei run |
| `sem:` | *(da definire con il binding)* | funzioni semantiche (`sem:filter`, `sem:classify`, `sem:join`) |

- Identificatori di run: `g<NN>-<set>-<query>-<piano>` (esempio: `g07-eval-q1-ref`). Il nome del file deve coincidere con l'id nel file (il checker lo verifica).
- Query proprie: prefisso del gruppo nell'id (esempio: `g07-Q2`).
- Archi derivati: proprietà `ex:derived<Nome>`, un named graph per run, una reificazione per arco.
- File RDF: Turtle o TriG, UTF-8.

## 7. Git

1. `git pull` prima di iniziare.
2. Commit piccoli, messaggio all'imperativo e specifico (esempio: `Add sem_filter reference plan`).
3. Un ramo per attività grande, revisione di un altro membro prima del merge.
4. **Mai** su Git: chiavi, `.env`, dati del professore, modelli, ambienti virtuali.
5. Nuova libreria: aggiornare `requirements.txt` (versione pinnata) e avvisare il gruppo.
6. Prima di una consegna: **clone pulito** su un'altra macchina e prova della riproduzione.

## 8. Log di lavoro

Un file condiviso (`docs/log.md`). Per ogni sessione: data, chi, cosa, ore, blocchi. Serve per la dichiarazione dei contributi e per rispettare il limite di ore (**28 ore a M1, 73 a M2**: oltre, si parla con il professore).
