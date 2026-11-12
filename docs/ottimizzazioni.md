# Le quattro ottimizzazioni: recap, pro e contro

Documento di lavoro per decidere quale ottimizzazione scegliere (la scelta va nel design note della M1, che è
facoltativo, ma serve comunque per organizzare il lavoro). Cosa viene dalle slide e dal professore è indicato
come tale; le valutazioni su sforzo e rischio sono **nostre**, qualitative, e vanno discusse nel gruppo.

## 1. Cosa chiede il corso

- **Almeno una ottimizzazione**, calibrata sul **dev set**, riportata come **frontiera** costo/qualità con
  **almeno tre punti operativi** (ognuno con chiamate al modello, costo, accordo con il piano di riferimento e F1
  contro la chiave). Si indica il punto che si consegnerebbe e che cosa cede. La calibrazione si verifica **una
  volta** sull'eval set.
- **Peso nella valutazione: 25 punti su 100** ("ottimizzazione e calibrazione").
- **Bonus (fino a 10 punti complessivi):** una garanzia statistica sulla cascata, una query facoltativa (Q7), una
  seconda ottimizzazione, un confronto con la libreria LOTUS.
- **Dal professore (lezione):** si scelgono una o due ottimizzazioni tra quelle proposte, le si implementa e le si
  prova; chi implementa bene una proposta può avere il massimo. Un'ottimizzazione inventata dal gruppo dà punti
  extra, ma non è richiesta.
- **Tagli già approvati se serve:** frontiera con due punti invece di tre, oppure una calibrazione in meno,
  con minore profondità attesa. Vanno confermati per iscritto.
- **Regola che pesa:** cambiare un prompt dopo la calibrazione la invalida. I prompt si congelano prima.

## 2. Tabella di sintesi

| Ottimizzazione | Idea | Cosa richiede | Con quello che abbiamo |
|---|---|---|---|
| **O1 cascata** | un modello piccolo risponde quando è sicuro, il grande decide negli altri casi | un modello piccolo con un **punteggio di confidenza**, un oracolo grande, due soglie calibrate sul dev | Abbiamo il modello locale (Qwen2.5 3B) e Gemini. **Manca il punteggio di confidenza**: log-probabilità dal server (da verificare), un metodo basato su prompt, o un decision model |
| **O2 blocking calibrato** | scegliere k (o una soglia di similarità) dai dati per raggiungere una recall dichiarata | embedding (`bge-small-en-v1.5`), join Q6 e idealmente Q7 | Embedding non ancora provati. Il top-10 tiene già il 99,0% delle coppie vere di Q7 dev |
| **O3 block join** | molti film e molti romanzi nello stesso prompt, il modello restituisce le coppie | solo il gateway e un modello con contesto sufficiente | Niente da costruire a parte i prompt a blocchi. Qualità da misurare con un modello piccolo |
| **O4 contesto dal grafo** | aggiungere a τ i vicini del grafo e anticipare una restrizione strutturale | proprietà ammesse, controllo di leakage, un filtro e la join piccola | **È già iniziata:** lo studio di τ (t3, t5, t6) è la prima metà, e ha già prodotto un caso di leakage |

## 3. Una per una

### O1. Cascata proxy + oracolo (filtro e classificazione)

**Come funziona (slide).** Per ogni binding il modello piccolo (proxy) produce un punteggio. Sotto la soglia θ⁻
risponde "falso", sopra θ⁺ risponde "vero", in mezzo si chiede all'oracolo (modello grande). Le soglie si
imparano sul dev usando le risposte dell'oracolo come etichette. Si riporta la quota inviata all'oracolo e
l'accordo con il riferimento a tre obiettivi. Le richieste all'oracolo sono quelle del piano di riferimento: se
si esegue prima il riferimento, sono già in cache e la cascata costa quasi niente da valutare.

**Perché farla**
- Risparmia chiamate al modello costoso su filtri e classificazione (Q1-Q4), dove la join non c'entra.
- Si appoggia su quello che abbiamo già: un modello locale e uno a pagamento.
- Ha l'unico bonus "statistico" del corso: una **garanzia sull'accordo con il riferimento** (con campionamento
  per importanza e intervallo corretto, come nell'Algoritmo 1 di LOTUS).
- Il professore la cita insieme ai modelli "System1" (decision model) che restituiscono confidenza, e a
  Microsoft-Decision-1 su Foundry.

**Perché no / rischi**
- **Il punteggio di confidenza non c'è ancora.** Le slide indicano le log-probabilità (llama.cpp le espone); se
  il nostro server non le dà, restano i metodi basati su prompt o un decision model, con interfaccia diversa dal
  nostro client.
- **Il guadagno dipende dalla qualità del proxy.** Se il proxy è poco affidabile quasi tutto va all'oracolo e il
  risparmio sparisce. Nel nostro campione da 150 film, Qwen2.5 3B ha recall 0,64 su Q1 e trova 8 positivi
  impliciti su 16: numeri preliminari, ma non entusiasmanti.
- **Serve un run di riferimento dell'oracolo sul dev** (circa 0,4 USD per il filtro su 1000 film, al prezzo
  "Pro" delle slide) e il gateway per la cache.
- Le soglie vanno ricalibrate se cambia il prompt.

**Punti operativi tipici:** tre obiettivi di accordo con il riferimento (per esempio 0,90 / 0,95 / 0,99), con
soglie e quota all'oracolo diverse.

### O2. Blocking calibrato (join)

**Come funziona (slide).** Il piano obbligatorio fissa k = 10. O2 sceglie k, o una soglia di similarità, dai dati
etichettati per raggiungere una recall dichiarata sulla join piccola, e verifica l'obiettivo sulla grande. Si
testa se la similarità è davvero correlata alla condizione (LOTUS avverte che non sempre lo è). Sulla frontiera,
k fissa il costo e la qualità è prima la recall del blocking, poi l'F1 finale. Per i film si analizzano anche le
coppie che il blocking perde.

**Perché farla**
- **È la più economica da sperimentare:** la recall del blocking si misura senza nessuna chiamata a pagamento.
- Frontiera molto leggibile (k contro chiamate contro recall) e rischio di leakage basso.
- Le chiamate sono molte per Q6 (5.000 con il riferimento, circa 3,3 USD) e moltissime per Q7 (100.000, circa
  66 USD sul dev): il blocking le porta a 500 e 2.000 con k = 10.
- Chiude Q7, che è la query facoltativa con punti bonus.
- Gli embedding costano poco (700 testi in 88 secondi su due CPU virtuali, secondo le slide).

**Perché no / rischi**
- **Poco margine:** con k = 10 il blocking tiene già il 99,0% delle coppie di Q7 dev e il 97,3% in eval
  (README del pacchetto). Il guadagno sta nel scendere a k più bassi, perdendo qualche coppia.
- **Riguarda solo la join.** Non cambia niente per filtri e classificazione.
- Per Q7 le slide richiedono comunque il top-10: O2 è utile soprattutto se facciamo Q7 o vogliamo ottimizzare Q6.
- **Gli embedding passano dal gateway** nei numeri del report: gli esperimenti locali vanno rifatti.
- Il segnale è forte qui perché il lead cita il romanzo o l'autore; su altre join potrebbe essere debole
  (nel pool arrivano query di altri gruppi).

**Punti operativi tipici:** tre valori di k (o tre soglie), per esempio 3, 5, 10, con recall del blocking,
chiamate e F1 finale.

### O3. Block join (join)

**Come funziona (slide).** Un prompt contiene un blocco di film e un blocco di romanzi e chiede le coppie che
corrispondono, sul modello del block nested loops dei database tradizionali. Si varia la dimensione del blocco e
si verifica che stia nella finestra di contesto. La qualità si misura contro il riferimento a coppie sulla join
piccola, dove il riferimento esiste.

**Perché farla**
- **Poca infrastruttura:** niente embedding, niente punteggi di confidenza, solo prompt a blocchi e il gateway.
- Riduce le **chiamate** in modo diretto.
- La slide dice che il calo di qualità all'aumentare dei blocchi "è il risultato, non un fallimento": la frontiera
  è comunque interessante da riportare.

**Perché no / rischi**
- **Cambia il compito del modello:** le risposte non sono confrontabili chiamata per chiamata con il
  riferimento. Si confrontano gli insiemi di coppie in uscita, e il report deve dirlo.
- Ogni chiamata ha più token. Il risparmio in **euro** va misurato, non dato per scontato.
- I modelli piccoli potrebbero reggere male contesti lunghi (da misurare con il nostro modello locale).
- Riguarda solo la join.

**Punti operativi tipici:** tre dimensioni del blocco, con chiamate, token, costo e qualità contro il riferimento.

### O4. Contesto dal grafo con restrizione anticipata (filtro e join)

**Come funziona (slide).** Il parametro del piano è quanta parte del vicinato a un passo entra in τ: nessuna,
due proprietà scelte (per esempio regista e paese), tutte le etichette a un passo. Si misura la frontiera su un
filtro e sulla join piccola, con token e costo da una parte e qualità dall'altra. Poi si combina l'impostazione
migliore con una **restrizione strutturale anticipata** su una query diversa da Q3 e si riportano le chiamate
risparmiate. Attenzione al leakage: se il vicinato contiene la proprietà nascosta, la configurazione non è valida.

**Perché farla**
- **È quella che sfrutta il grafo:** le slide dicono che "qui il grafo si guadagna il posto" e che nessun sistema
  tabellare può aggiungere un vicinato a una riga a costo zero.
- **È già a metà strada:** lo studio di τ con t3, t5 e t6 è la sua prima parte, con gli script e la tabella dei
  risultati già pronti, e non richiede embedding né punteggi di confidenza.
- **Ha già un risultato interessante, quello che le slide chiamano "il risultato più interessante":** il leakage
  tramite i vicini. Nel nostro studio il cast (P161) ha portato in τ il soggetto nascosto di quattro
  documentari (per esempio Frida Kahlo), pur essendo una proprietà ammessa dal professore.
- Funziona su filtro e join, quindi copre più query delle altre.

**Perché no / rischi**
- **Sul filtro Q1 il contesto non sembra migliorare la qualità** (campione da 150 film, preliminare):
  regista e paese sono già nel testo, e le varianti con proprietà aggiungono falsi positivi. Il risparmio non
  viene dall'iniezione ma dalla **restrizione anticipata**, che va costruita su un'altra query.
- **La definizione di "corretta" non si applica direttamente.** Le slide la descrivono come riduzione del costo
  con accordo al riferimento; O4 migliora la qualità o riduce chiamate solo tramite la restrizione. Se la
  frontiera mostra "nessun guadagno", non sappiamo come venga valutata: da chiedere al professore o al TA.
- Il rischio di leakage è il più alto: ogni configurazione va controllata, anche in modo automatico.
- Sulla join il vicinato può **ingannare**: metà dei romanzi del lato destro sono distrattori che condividono
  l'autore con un partner vero, quindi aggiungere l'autore può confondere.

**Punti operativi (dalle slide):** nessun vicinato, due proprietà scelte, tutte le etichette ammesse a un passo.

## 4. Confronto

| Criterio | O1 | O2 | O3 | O4 |
|---|---|---|---|---|
| Query coinvolte | filtri, classificazione | join (Q6, Q7) | join (Q6, Q7) | filtri e join |
| Riduce le chiamate | sì | sì | sì | solo con la restrizione anticipata |
| Richiede embedding | no | **sì** | no | no |
| Richiede un punteggio di confidenza | **sì** | no | no | no |
| Rischio di leakage | basso | basso | basso | **alto** |
| Confrontabile col riferimento chiamata per chiamata | sì | sì | **no** | sì |
| Bonus possibile (slide) | garanzia statistica | Q7 | - | - |
| Stato oggi | modello piccolo da valutare | non iniziata | non iniziata | **iniziata** |
| Sforzo (stima nostra) | medio-alto | medio | medio-basso | medio |

## 5. Combinazioni

- **O4 come principale, O2 come seconda (bonus).** Parte da quello che abbiamo e aggiunge la join, se facciamo Q7.
- **O2 sola.** La più economica da misurare, ma con margine ridotto e solo sulla join.
- **O1 da sola o con O2.** La più ambiziosa, con il bonus statistico. Va decisa solo dopo aver verificato
  come ottenere un punteggio di confidenza.
- **O3 come seconda ottimizzazione** facile da aggiungere, ma con un risultato probabilmente "la qualità cala".

## 6. Cosa decidere prima della M1

1. L'ottimizzazione principale (e l'eventuale seconda, per il bonus).
2. **Facciamo Q7?** Cambia il valore di O2 e il budget (circa 66 USD con il riferimento sul dev).
3. **Il segnale usato** (per O1: log-probabilità, prompt o decision model; per O2: il modello di embedding).
4. **I tre punti operativi previsti** e **il budget** da scrivere nel design note.
5. Chi se ne occupa, tenendo conto delle 22 ore di gruppo previste per la fase di ottimizzazione (M3).

Domande da fare al professore o al TA: se un risultato "nessun guadagno di qualità" in O4 è valutato come
frontiera valida, e se il confronto con la libreria LOTUS conta come bonus anche con un solo operatore.
