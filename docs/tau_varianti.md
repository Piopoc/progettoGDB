# Varianti di τ: cosa sono, a che punto sono

τ trasforma un'entità del grafo (film o romanzo) nel testo che il modello legge. **Per la M1 il τ del progetto è τ0** (`prompts/tau_t0_v1.json`). Le altre varianti sono esperimenti sul dev set: ogni file in `prompts/` è la configurazione di un risultato in `eval/` e resta nel repository, anche se la variante è scartata (le regole del corso: i prompt fanno parte della specifica e sono versionati).

## Come si legge una configurazione

Tutte le varianti sono costruite da `TauBuilder` in `src/tau.py`. Un file `prompts/tau_<nome>_v1.json` contiene solo le chiavi che cambiano rispetto ai valori predefiniti.

| Chiave            | Significato                                                                                                                             | Valore predefinito |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| `use_description` | aggiunge `description_screened` (la descrizione Wikidata filtrata dal rilascio)                                                         | `true`             |
| `use_lead`        | aggiunge il lead di Wikipedia                                                                                                           | `true`             |
| `max_chars`       | taglio dell'intera stringa in caratteri; `null` = nessun taglio                                                                         | `1200`             |
| `max_sentences`   | tiene solo le prime N frasi del lead (titolo e descrizione restano interi)                                                              | `null`             |
| `format`          | `plain` (testo continuo) oppure `labeled` (`Title: … / Description: … / Text: …`)                                                       | `plain`            |
| `extra_props`     | proprietà del grafo aggiunte per classe (`Film`, `Novel`); ammesse solo quelle con `tau_allowed_for_common_queries` in `properties.csv` | nessuna            |

Ogni variante con `extra_props` passa il controllo automatico di leakage di `tau_study`: se un valore di una proprietà nascosta (`hidden_statements.csv`) compare nel testo aggiunto, il film viene elencato in `tau_study_leakage_<variante>.csv` (il file esiste solo se c'è almeno un caso).

## Le varianti e i risultati sulla Q1

**Condizioni del run** (`eval/tau_q1_150/`, run_id `tau-q1-150`, 20 novembre 2026):

- query Q1 (sem_filter, *the film deals with the Second World War*), prompt `filter_v1`;
- campione fisso di **150 film** del main set del dev (`--limit 150`, seme 0): **28 positivi** nella chiave espansa, 26 nella diretta;
- modello: rotta del gateway `local/qwen2.5-coder:3b-unsloth` (Qwen2.5-Coder-3B-Instruct, GGUF, servito da Unsloth); tutte le richieste passano dal gateway del corso;
- tutte le varianti nello stesso run: ogni confronto con t0 è sugli stessi film, con lo stesso modello e lo stesso percorso;
- Δ F1: differenza rispetto a t0 con bootstrap appaiato, intervallo al 95%; "nel rumore" = l'intervallo contiene 0;
- token: media e 90° percentile di τ sul campione (tokenizzatore `cl100k_base`); "ingresso" = token reali della richiesta intera (istruzioni + criterio + τ) riportati dal modello.

| Variante | Configurazione                                   | P     | R     | F1        | Δ F1 vs t0 [IC 95%]     | Token τ (media / p90) | Token ingresso | Stato                                    |
| -------- | ------------------------------------------------ | ----- | ----- | --------- | ----------------------- | --------------------- | -------------- | ---------------------------------------- |
| **t0**   | titolo + descrizione + lead, 1200 caratteri      | 0,810 | 0,607 | **0,694** | —                       | 170,5 / 272           | 225,5          | **τ della M1**                           |
| c900     | come t0, **900 caratteri**                       | 0,810 | 0,607 | 0,694     | 0,000 [−0,041; 0,040]   | 152,6 / 217           | 206,7          | equivalente, **−10% token**              |
| t10      | come t0, **senza taglio**                        | 0,750 | 0,643 | 0,692     | −0,002 [−0,060; 0,062]  | 190,9 / 368           | 247,2          | equivalente, +12% token                  |
| t1       | come t0, **600 caratteri**                       | 0,812 | 0,464 | 0,591     | −0,105 [−0,241; 0,007]  | 124,0 / 156           | 176,8          | nel rumore, recall più bassa             |
| s5       | titolo + descrizione + **prime 5 frasi**         | 0,739 | 0,607 | 0,667     | −0,028 [−0,086; 0,024]  | 141,5 / 204           | 195,1          | nel rumore                               |
| s3       | … + **prime 3 frasi**                            | 0,714 | 0,536 | 0,612     | −0,083 [−0,191; 0,008]  | 106,4 / 147           | 158,7          | nel rumore, recall più bassa             |
| s2       | … + **prime 2 frasi**                            | 0,727 | 0,571 | 0,640     | −0,053 [−0,162; 0,059]  | 82,3 / 113            | 133,9          | nel rumore                               |
| s1       | … + **prima frase**                              | 0,750 | 0,321 | 0,450     | −0,247 [−0,451; −0,050] | 52,5 / 75             | 103,0          | **peggiore**                             |
| t2       | come t0, formato `labeled`                       | 0,760 | 0,679 | 0,717     | +0,026 [−0,100; 0,163]  | 175,0 / 274           | 230,2          | nel rumore                               |
| t3       | t0 + regista e paese (film), autore (romanzi)    | 0,625 | 0,714 | 0,667     | −0,026 [−0,136; 0,090]  | 181,6 / 274           | 236,4          | **esclusa: leakage sul dev intero**      |
| t6       | t0 + lingua e paese (film), autore (romanzi)     | 0,700 | 0,750 | 0,724     | +0,032 [−0,082; 0,162]  | 183,5 / 274           | 238,1          | **esclusa: leakage sul dev intero**      |
| t7       | t0 + paese (film)                                | 0,720 | 0,643 | 0,679     | −0,014 [−0,079; 0,060]  | 176,0 / 274           | 230,9          | **esclusa: leakage sul dev intero**      |
| t8       | t0 + autore (solo romanzi)                       | 0,810 | 0,607 | 0,694     | 0,000 [0,000; 0,000]    | 170,5 / 272           | 225,5          | identica a t0 sulla Q1 (vedi note)       |
| t9       | t0 + 14 proprietà dei film, **senza taglio**     | 0,404 | 0,821 | 0,541     | −0,149 [−0,288; −0,003] | 263,0 / 467           | 319,2          | **peggiore ed esclusa: leakage**         |
| t4       | titolo + descrizione, **senza lead**             | 0,778 | 0,250 | 0,378     | −0,316 [−0,552; −0,077] | 15,2 / 20             | 63,9           | **peggiore**                             |
| t5       | t0 + regista e **cast** (film), autore (romanzi) | —     | —     | —         | —                       | —                     | —              | **esclusa per leakage** (non rieseguita) |

Riferimenti senza modello sullo stesso campione: la parola chiave della guerra in τ0 ha F1 0,585 (precisione 0,923, recall 0,429).

Controllo di leakage sul campione: **0 film su 150** per t3, t6, t7, t8 e t9. **Sul dev intero no** (sezione seguente).

## Controllo di leakage sul dev intero

Comando (nessuna chiamata al modello): `python -m src.tau_study --data data/films/dev --variants t3 t6 t7 t8 t9 --dry-run`. File in `eval/leakage_dev/` (uno per variante con almeno un caso).

| Variante | Film con un valore nascosto nel testo aggiunto | Proprietà che lo porta                                                |
| -------- | ---------------------------------------------- | --------------------------------------------------------------------- |
| t3       | 5                                              | paese d'origine P495 (4), regista P57 (1)                             |
| t6       | 4                                              | paese d'origine P495                                                  |
| t7       | 4                                              | paese d'origine P495                                                  |
| t8       | 0                                              | —                                                                     |
| t9       | 17                                             | paese, regista, compositore, produttore, `instance of` (un genere), … |

Il caso tipico è un documentario su un paese: *Under the Dome* ha come soggetto nascosto (P921) la Cina ed è prodotto in Cina (P495), *Money-Driven Medicine* gli Stati Uniti, *The Importance of Being Icelandic* il Canada. Oppure un regista che racconta sé stesso (*Endless Poetry*, Alejandro Jodorowsky). In t9 *Wonder Woman* riceve "superhero film" da `instance of`, cioè il genere nascosto (P136). Tre casi di t9 sono falsi allarmi del controllo ("20th century", periodo nascosto, trovato dentro "20th Century Studios"); la variante resta esclusa per gli altri.

**Decisione: t3, t6, t7 e t9 sono escluse.** Nessuno di questi valori è la risposta di una query comune, ma: la regola del corso è che un valore nascosto non deve comparire "da nessuna parte" nel testo; la colonna `tau_allowed_for_common_queries` di `properties.csv` garantisce le proprietà solo per le query **comuni**, mentre le nostre query e quelle del pool possono interrogare proprio il soggetto (es. "film sugli Stati Uniti"); e non si può "ripulire" una variante togliendo i valori che coincidono con quelli nascosti, perché si userebbero i dati nascosti per costruire τ. **"Ammessa da** `properties.csv`**" non vuol dire "sicura"**: il controllo va fatto su tutto l'insieme, non su un campione (sui 150 film era a zero).

Le varianti che usano solo il testo del rilascio (t0, c900, t1, t2, t4, t10, s1–s5) non possono avere leakage per costruzione. t8 (autore dei soli romanzi) è pulita sul dev e resta utile per la Q6.

### Note

- **c900 e t10: il taglio a 1200 caratteri non conta.** Tagliare a 900 dà la stessa F1 di t0 con il 10% di token in meno; non tagliare affatto non migliora niente e costa il 12% in più. Coerente con l'analisi del lead: il 99% delle menzioni esplicite della guerra sta entro i primi 900 caratteri di τ (`eval/lead_analysis/`).
- **Varianti per frasi: peggio quanto più si taglia.** s1 è significativamente peggiore; s2, s3 e s5 restano sotto t0 con recall più bassa. Anche questo è coerente con l'analisi del lead: nella Q1 la guerra è nominata nella prima frase solo nel 27% dei casi. Per la Q1 il taglio per frasi non conviene; va provato sulla Q4, dove il genere sta quasi sempre nella prima frase.
- **t8 coincide con t0 sulla Q1, come atteso.** Aggiunge l'autore solo ai romanzi, e la Q1 riguarda solo film: i testi sono identici, e il gateway ha servito le risposte dalla cache. t8 va valutata sulla Q6 (join film–romanzo).
- **t5, leakage** (studio precedente, `eval/run_qwen3b_150/tau_study_leakage_t5.csv`). Il cast (P161) dei documentari contiene la persona che è il soggetto nascosto del film (P921): 4 film nel campione (*Anselm*, *Frida*, *Candyman*, *Fidel: The Untold Story*). La proprietà è ammessa da `properties.csv`, ma rivela la risposta di query sul soggetto: "non nascosta" non vuol dire "sicura".
- **t4.** Senza lead la recall crolla (0,25): quasi tutta l'informazione utile è nel lead.
- **t9.** Molte proprietà e nessun taglio: recall alta (0,821) ma precisione 0,404 (34 falsi positivi). Più contesto dal grafo rende il modello piccolo più incline a dire "sì".
- **Errori tipici di t0.** I falsi positivi visti finora sono film di spionaggio della Guerra fredda (James Bond) e documentari su altre guerre: il modello piccolo li confonde con la Seconda guerra mondiale. τ non c'entra (il testo non nomina la Seconda guerra mondiale); va verificato con il modello cloud.
- **Studio precedente.** Il 12 e il 17 novembre le stesse varianti erano state provate chiamando Unsloth senza gateway (`eval/run_qwen3b_150/`, `eval/run_qwen3b_150_o4/`). Con il gateway t0 passa da F1 0,706 a 0,694 (un film di differenza): per questo tutte le varianti sono state rieseguite nello stesso run, invece di mescolare i due studi.
- **Tempi.** La colonna `secondi_per_richiesta` del file di risultati comprende le risposte servite dalla cache del gateway, quindi non misura la velocità del modello.

## Su che base τ0 è il τ della M1

1. È il τ di riferimento del rilascio e usa solo testo del rilascio (`description_screened` esclude 74 descrizioni a rischio). Statistiche sul main set del dev: **167,6 token in media, 270 al 90° percentile** (come il riferimento del professore: 168 e 270), verificate da `tests/test_tau.py`.
2. Nessuna variante provata è significativamente migliore di t0; s1, t4 e t9 sono significativamente peggiori.
3. Il taglio a 1200 caratteri tocca il 19% dei film del dev e non cambia il risultato (t10 equivalente).
4. La ripetizione di t0 sullo stesso campione dà 0 decisioni diverse su 150 (`eval/ripetizione_t0/`).

**Candidata più economica: c900**, equivalente a t0 con il 10% di token in meno. Non cambia la scelta per la M1 (τ0 è il riferimento, e un pareggio su 150 film non basta per cambiare), ma va riprovata con il modello cloud.

**Limite.** Lo studio usa un modello piccolo e 150 film con 28 positivi: gli intervalli sono larghi e l'evidenza è debole. La scelta va confermata con il modello cloud durante la M2, e τ va fissato prima di calibrare O2 nella M3 (l'embedding del blocking si calcola su τ).

## Regola di scelta (decisa il 20 novembre 2026, prima dei run sulle altre query)

Obiettivo: la qualità di t0 con meno token. La regola è fissata prima di vedere i nuovi risultati, così la scelta non dipende da quale numero sembra migliore per caso.

1. **Finaliste:** t0, c900, s2, t2 (t8 solo per la Q6). t6 era tra le finaliste ed è stata esclusa per leakage il 20 novembre, prima di qualunque run sulle altre query.
2. **Non inferiorità rispetto a t0, con un margine δ = 0,03.** Una variante è ammessa se, su **ogni** query provata, il limite inferiore dell'intervallo al 95% della differenza rispetto a t0 è almeno −0,03. Metrica per query: F1 per Q1, Q2 e Q6; accuratezza sui film a etichetta singola per Q4. Si usano i run sul **dev intero**: sui 150 film del campione gli intervalli sono troppo larghi (anche c900, con la stessa F1 di t0, ha limite inferiore −0,041), quindi la Q1 va rifatta sui 1000 film per le finaliste.
3. **Tra le ammesse si sceglie quella con meno token medi di ingresso**; a parità (entro il 5%), quella con la metrica media più alta.
4. **Se nessuna variante è ammessa, resta t0.** La scelta si conferma con il modello cloud prima di calibrare O2.

Perché la non inferiorità e non "non significativamente peggiore": con pochi film gli intervalli sono larghi, e quasi tutte le varianti risultano "non significativamente peggiori" anche quando probabilmente lo sono (per esempio s2 sulla Q1: −0,053 [−0,162; 0,059]). La non inferiorità chiede la prova che la perdita sia piccola, non l'assenza di prova che sia grande. È la stessa idea delle ottimizzazioni "corrette" di LOTUS: un'accuratezza garantita rispetto al riferimento, con un margine fissato in anticipo.

Il parametro unico della regola è **δ**, la perdita di qualità che si accetta in cambio di meno token. Un punteggio come "F1 per token" non funziona: premia i testi cortissimi (s1 avrebbe il punteggio migliore pur essendo significativamente peggiore).

## Prossimi passi (M2)

- Q4 sul dev intero con t0, s1, s2 (il genere sta nella prima frase: possibile risparmio di token).
- t8 sulla Q6, dove l'autore del romanzo può aiutare il join.
- Le finaliste (t0, c900, s2, t2) sulla Q1 del dev intero, sulla Q2 e sulla Q4 (modello locale), poi le migliori con il modello cloud.
- Ogni nuova variante con proprietà del grafo passa il controllo di leakage su tutto il dev prima di qualunque run.
- O4 (contesto dal grafo) va ripensata: t7 e t9 sono escluse; restano proprietà che non coincidono con valori nascosti, come l'autore dei romanzi (t8).
- Una nuova variante si aggiunge come nuovo file (`tau_<nome>_v1.json`); se una configurazione cambia dopo un risultato, si crea `_v2` invece di modificare `_v1`.