# Checklist di progetto

**Ruoli:** A = Dati e query · B = Modelli e gateway · C = Engine e piani
**Condiviso da tutti:** ottimizzazione, valutazione, report, presentazione.

Scadenze: **M1 19 nov** · **M2 10 dic** · **M3 21 dic** · **Consegna finale 8 gen**.
Dal 3 dicembre non c'è nuovo materiale d'esame: il progetto è il lavoro principale.
Ore pianificate per gruppo: M1 22 · M2 36 · M3 22 · Finale 25 (circa 105 in totale, 45 a testa). **Oltre 28 ore a M1 o 73 a M2 si parla con il professore.**

## Fase 0 – Setup comune (subito, tutti)
- [x] Dominio assegnato: **videogiochi con serie** (`games`), scritto nel `README.md`
- [ ] Verificare i checksum del pacchetto (`sha256sum -c MANIFEST.sha256`)
- [ ] Leggere `docs/dati_games.md` e il README del pacchetto `games`
- [ ] Leggere i tre paper: **LOTUS** (PVLDB 2025), **SemBench** (PVLDB 2026), Palimpzest (CIDR 2025, utile)
- [ ] Leggere slide parti 1-2, documento delle query (`query-set.pdf`) e README del pacchetto dati
- [ ] Aggiornare la struttura delle cartelle (`data/`, `docs/`, `src/`, `prompts/`, `queries/`, `keys/`, `runs/`, `cache/`, `eval/`, `rdf/`, `tools/`, `notebooks/`)
- [ ] Verificare che `.gitignore` escluda i dati del professore, la cache pesante e `.env`
- [ ] Aggiornare `requirements.txt` (`pyoxigraph==0.5.11`, `numpy`, `fastembed`, `jsonschema`, ...)
- [ ] Verificare che l'ambiente si installi su tutte e tre le macchine
- [ ] Compilare `CONVENZIONI.md` (fatto) e fissare il budget massimo per esperimento
- [ ] Decidere come ognuno gestisce la propria chiave (Google, Azure): mai nel repository
- [ ] Creare il log di lavoro condiviso `docs/log.md` (attività, ore, blocchi)
- [ ] Almeno un membro con modello locale (3-9 miliardi di parametri) funzionante
- [ ] Partecipare alla lezione sul gateway: **giovedì 12 novembre, ore 12**

## Fase 1 – M1, design note (scadenza 19 novembre)
**Obiettivo:** dati caricati, τ definita, query comuni scritte per l'engine, **una chiamata semantica end-to-end**, ottimizzazione scelta.

### Tutti
- [ ] Scegliere **engine** (Oxigraph consigliato) e **ottimizzazione** (O1, O2, O3, O4 o propria)
- [ ] Scrivere la **design note di 2 pagine** (definizione dei tre operatori, τ, engine, ottimizzazione, piano del budget)
- [ ] Consegnare M1 solo se il lavoro è buono (sloppy = −1 punto)
- [ ] Fissare un incontro con l'assistente (8 ore totali) con un problema concreto

### A – Dati e query
- [ ] Caricare **dev e eval** nell'engine, in **due store** (senza e con statement nascoste)
- [ ] Esplorare i dati: conteggi per set, colonne, tipo di testo, campi nascosti
- [ ] Definire **τ** (label + `description_screened` + lead, taglio a 1.200 caratteri) e renderla parametrica
- [ ] Controllare in `properties.csv` quali proprietà possono entrare in τ
- [ ] Calcolare le statistiche di τ (token medi e 90° percentile, tokenizer `cl100k_base`). Riferimento del professore sul dev: giochi 152 medi, 256 al 90° percentile
- [ ] Verificare che le answer key comuni (Q1-Q8) si riproducano dai file `gt/`
- [ ] Iniziare a scegliere le **6 query proprie**: usare `property_catalog.csv` (copertura, valori frequenti) per trovare generi frequenti e rari diversi da platformer e visual novel, e diversi dalle 8 etichette di Q4

### B – Modelli e gateway
- [ ] Installare il modello locale e provare una richiesta
- [ ] Capire il gateway (cache, log, prezzo, schema, tetto di budget) dopo il 12/11
- [ ] Configurare le chiavi Google/Azure e fare una chiamata di prova
- [ ] Stimare il costo del progetto con il listino prezzi (tabella delle chiamate di riferimento)
- [ ] Scrivere il piano del budget per membro

### C – Engine e piani
- [ ] Installare l'engine scelto e caricare dati qualsiasi
- [ ] Registrare una funzione `sem:filter` (Oxigraph: `custom_functions` di `Store.query`)
- [ ] Scrivere le 8 query comuni dei **giochi** nella sintassi dell'engine (Q3: sviluppatori P178 con paese P17 = Giappone Q17, poi Q1 platformer Q828322; Q6: giochi ↔ serie P179)
- [ ] Eseguire **una chiamata semantica end-to-end** su 10 entità: query → gateway → modello locale → risposta
- [ ] Scrivere `SEM-FILTER-REF` e `SEM-JOIN-REF` su un sottoinsieme

## Fase 2 – M2, sistema di riferimento (scadenza 10 dicembre)
**Obiettivo:** piani di riferimento, studio dell'ordine di valutazione, risultati dev, **sei query proprie (obbligatorie)**.

### A – Dati e query
- [ ] Scrivere le **6 query proprie** (tipi Q1, Q2, Q3, Q4, Q6, Q8; Q7 opzionale; nessuna Q5)
- [ ] Per ogni query: domanda in linguaggio, operatore, query di ground truth, espansione della gerarchia
- [ ] Per ogni query: **tasso di positivi** sull'eval set (Q1: valore frequente; Q2: valore raro)
- [ ] Per ogni query: **controllo di leakage** su 20 positivi, annotato in `eval/leakage.md`
- [ ] Controllare a mano i casi dubbi dell'espansione e scrivere la decisione
- [ ] Generare `key.json` in `keys/<dominio>/<set>/<query_id>/`
- [ ] Documentare τ con statistiche nel testo di specifica

### B – Modelli e gateway
- [ ] Validazione dello schema e conteggio dei **parse failure** a parte
- [ ] Conteggio costi: chiamate, token in/out, dollari, listino prezzi
- [ ] Routing tra modello locale e modello API
- [ ] Verificare che un re-run con cache emetta **zero richieste** al modello

### C – Engine e piani
- [ ] Implementare i **piani di riferimento** (filter, classify, map, join a ciclo annidato)
- [ ] **Studio dell'ordine di valutazione:** Q1 e Q3, almeno **3 forme di query** ciascuna con lo stesso risultato
- [ ] Contare le chiamate **nel log del gateway**; riportare le evidenze (conteggi per Oxigraph, `PROFILE` per Neo4j)
- [ ] Scegliere la forma con **una chiamata per binding distinto** e nominarla
- [ ] Eseguire Q3 in due ordini: struttura prima (live) e semantica prima (decisioni in cache)
- [ ] Implementare Q8 dalle decisioni in cache di Q1 (nessuna nuova chiamata)
- [ ] Implementare il blocking top-10 di base (embedding, VALUES) per il join. Nei giochi l'etichetta del gioco contiene quella della serie in 169 coppie su 200 (dev): misurare come cambia la recall senza quel segnale (31 coppie)

### Tutti
- [ ] Eseguire le query comuni sul **dev set** e produrre i run file
- [ ] Eseguire il checker `semops_check.py` e correggere errori e avvisi
- [ ] Calcolare precision, recall, F1 sulla answer key e sull'esecuzione di riferimento
- [ ] Ispezionare un campione di **falsi positivi** (il grafo può essere incompleto) e annotare il numero guardato
- [ ] Consegnare M2 (solo se buono) con le 6 query

## Fase 3 – M3, ottimizzazione e pool (scadenza 21 dicembre)
**Obiettivo:** ottimizzazione calibrata, frontiera, run finali su eval, join grande, provenance. Il professore pubblica il pool.

### Tutti
- [ ] **Congelare i prompt** (versioni) prima di calibrare
- [ ] Implementare l'ottimizzazione scelta (O1 cascade, O2 blocking calibrato, O3 block join o O4 contesto del grafo)
- [ ] **Calibrare sul dev set** e costruire la **frontiera con almeno 3 punti operativi** (aggressivo, bilanciato, conservativo)
- [ ] Per ogni punto: chiamate, costo, accordo con il riferimento, F1 sulla answer key
- [ ] Provare la calibrazione **una volta** sull'eval set
- [ ] Nominare il punto che si spedirebbe e cosa sacrifica
- [ ] (Bonus) garanzia statistica sul cascade, seconda ottimizzazione, confronto con LOTUS

### A
- [ ] Controllare di nuovo il leakage dopo ogni modifica a τ (O4 in particolare)
- [ ] Consegnare le query proprie definitive al professore per il pool

### B
- [ ] Run finali sull'eval set dentro il tetto di budget (una volta per piano)
- [ ] Per il run campionato: dichiarare il campione

### C
- [ ] Join grande Q7 (opzionale, bonus) con blocking: recall del blocking, precisione di 30 coppie controllate a mano
- [ ] **Materializzazione:** archi derivati in un named graph per run, con reificazione e annotazioni (operatore, espressione, modello, piano, punteggio, evidenza, run, timestamp)
- [ ] Scrivere le **due query miste** (derivato + asserito; derivato con alta confidenza e conferma in Wikidata)

## Fase 4 – Consegna finale (scadenza 8 gennaio)
- [ ] Ricevere il pool e l'eval set dei **film** (21 dicembre)
- [ ] Eseguire la **selezione del pool** sui film **così com'è** (stessi prompt, τ e piani). τ deve funzionare con le proprietà dei film (P921 nascosta, P144 per i romanzi)
- [ ] (Opzionale) ricalibrare sul dev set dell'altro dominio e riportare entrambi i risultati
- [ ] Eseguire la selezione del pool anche sul proprio dominio
- [ ] Analisi: query sbagliate da tutti i gruppi, trasferimento tra domini, soglia di costo
- [ ] Scrivere le **threats to validity** (incompletezza GT, leakage, non-determinismo, sensibilità al prompt, retrieval approssimato, specificità del dominio), ognuna con un numero
- [ ] **Report di massimo 6 pagine** (meglio 5), con sezione sugli assistenti di coding
- [ ] Dichiarazione dei contributi e valutazione tra pari (un paragrafo per membro)
- [ ] `results.csv` generato dal checker su un clone pulito
- [ ] **Riproduzione con un solo comando** su un'altra macchina, senza chiave API, con cache consegnata
- [ ] Versioni pinnate (engine, plugin, modelli, librerie, listino prezzi); nessun segreto nella cronologia
- [ ] Chiedere approvazione scritta per ogni deviazione **prima** della consegna
- [ ] Preparare la presentazione: **12 minuti + 8 di domande**, ogni membro presenta e risponde su tutto

## Controlli sempre attivi
- [ ] Nessuna chiamata al modello fuori dal gateway
- [ ] Tuning sul dev set, report sull'eval set
- [ ] Prompt versionati e congelati
- [ ] Ripetizioni volute riportate come varianza
- [ ] Ogni numero del report ha un run file e una riga in `results.csv`
- [ ] Ogni affermazione del report è giustificabile da chi la presenta

## Tagli pre-approvati (solo dopo conferma scritta)
- [ ] Join grande ridotto a 100 × 250 coppie
- [ ] Frontiera con due punti invece di tre
- [ ] Studio dell'ordine di valutazione su una sola query

**Non si taglia mai:** implementazione di riferimento, almeno un'ottimizzazione, riproducibilità di ogni numero.

## Nel frattempo (prima del database)
- [ ] (A) Caricare il pacchetto dati e rifare le answer key comuni con SPARQL
- [ ] (B) Fare una chiamata al modello locale e una al modello API con cache e log
- [ ] (C) Scrivere la query `sem:filter` su 10 entità con Oxigraph
