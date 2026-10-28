# Checklist di progetto

**Ruoli:** A = Modellazione e validazione · B = Pipeline dati · C = LLM e valutazione

## Fase 0 – Setup comune (tutti)
- [ ] Creare il repository Git condiviso e invitare tutti i membri
- [ ] Creare la struttura delle cartelle (`data/`, `docs/`, `eval/`, `notebooks/`, `ontology/`, `rdf/`, `src/`)
- [ ] Scrivere `.gitignore` (dati pesanti, chiavi, cache, file temporanei)
- [ ] Scrivere `requirements.txt` (pandas, rdflib, ...)
- [ ] Verificare che l'ambiente si installi su tutte e tre le macchine
- [ ] Scrivere `CONVENZIONI.md` (namespace, schema URI, naming, formato Turtle UTF-8)
- [ ] Decidere chi gestisce la chiave Google Cloud e come condividerla (variabili d'ambiente, mai nel repo)
- [ ] Fissare un budget massimo per esperimento sui crediti
- [ ] Creare il log di lavoro condiviso (attività, tempi, blocchi)

## Fase 1 – Comprensione di dati e requisiti
### Tutti
- [ ] Leggere la consegna e annotare vincoli e deliverable
- [ ] Scrivere almeno 10-15 competency questions
### B
- [ ] Esplorare ogni CSV con Pandas (colonne, tipi, nulli, duplicati)
- [ ] Individuare chiavi primarie e esterne
- [ ] Verificare l'integrità referenziale tra i file
- [ ] Produrre il data dictionary (file, colonna, significato, esempio, qualità)
### C
- [ ] Individuare le colonne testuali libere
- [ ] Test minimo con LOTUS su 5-10 righe (annotare tempi e costi)
- [ ] Test minimo con modello locale o Google Cloud su 5-10 righe
### A
- [ ] Abbozzare lo schema concettuale (entità, relazioni, cardinalità)
- [ ] Confrontare lo schema con le competency questions

## Fase 2 – Ontologia
### A
- [ ] Creare classi e gerarchie in Protégé
- [ ] Definire object property e data property (domini, range, datatype XSD)
- [ ] Valutare il riuso di ontologie esistenti (FOAF, schema.org, ...)
- [ ] Aggiungere assiomi e vincoli solo dove servono (sottoclassi, disgiunzioni, inverse, funzionali)
- [ ] Documentare le scelte in `docs/ontologia.md`
- [ ] Esportare l'ontologia in `ontology/`
### B
- [ ] Verificare che ogni classe e proprietà sia mappabile sui CSV
### C
- [ ] Verificare che ogni competency question sia rispondibile con lo schema

## Fase 3 – Pipeline di ingestione
### B
- [ ] Scrivere le funzioni per generare gli URI in modo uniforme
- [ ] Scrivere lo script/notebook RDFLib per ogni CSV (binding prefissi, triple, `try/except`)
- [ ] Gestire la memoria (lettura a blocchi se i file sono grandi)
- [ ] Serializzare in Turtle (UTF-8) dentro `rdf/`
- [ ] Implementare normalizzazione e matching delle entità tra fonti
### C
- [ ] Costruire un gold standard (30-50 coppie corrette/errate)
- [ ] Calcolare precision, recall, F1 del matching di B
- [ ] Provare varianti (embedding, LLM come giudice sui casi dubbi) e confrontarle
- [ ] (Se servono) pipeline di estrazione NER/relation extraction con prompt few-shot e output JSON
- [ ] (Se servono) convertire l'estrazione in triple agganciate agli URI esistenti
- [ ] Valutare l'estrazione su un campione verificato a mano
### A
- [ ] Creare il repository in GraphDB e caricare ontologia e `.ttl`
- [ ] Controllare conteggio triple, URI orfani, nodi senza tipo, errori di datatype

## Fase 4 – Inferenza, interrogazione, validazione
### A
- [ ] Creare due repository GraphDB (senza e con inferenza RDFS-Plus)
- [ ] Confrontare il numero di triple nei due casi
- [ ] Scrivere le shape SHACL (cardinalità, datatype, valori ammessi)
- [ ] Validare il grafo e produrre il report delle violazioni
### B
- [ ] Correggere la pipeline in base a SHACL e alle query
### C
- [ ] Tradurre le competency questions in SPARQL
- [ ] Verificare i risultati a campione
- [ ] (Opzionale) generare SPARQL con un LLM e confrontarlo con quello scritto a mano

## Fase 5 – Valutazione e consegna
- [ ] (Tutti) Tabella riassuntiva di qualità (completezza, correttezza, tempi, costi)
- [ ] (C) Sezione su cosa ha funzionato con LLM/LOTUS, con numeri
- [ ] (A) Documentazione finale di ontologia e vincoli
- [ ] (B) Guida alla riproduzione (rigenerare i `.ttl` da zero)
- [ ] (Tutti) Revisione incrociata del report finale
- [ ] (Tutti) Prova di esecuzione completa su macchina pulita
- [ ] (Tutti) Preparare la presentazione

## Nel frattempo, prima del database
- [ ] (A) Replicare l'esempio calcio in Protégé e GraphDB
- [ ] (B) Replicare la pipeline CSV → RDFLib → Turtle della lezione
- [ ] (C) Esercitarsi su precision/recall/F1 e su prompt few-shot con output JSON
