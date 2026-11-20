# Analisi del lead

Dati: `data/films/dev`
Divisione in frasi: `split_sentences` di `src/tau.py` (la stessa delle varianti s1, s2, s3, s5).

## 1. Lunghezze (insieme main)

| index | dev |
|---|---|
| film | 1000 |
| lead_caratteri_mediana | 591 |
| lead_caratteri_p90 | 1556 |
| lead_frasi_mediana | 5 |
| lead_frasi_p90 | 11 |
| lead_token_media | 176.8 |
| tau0_tagliati_a_1200 | 0.188 |
| testo_tenuto_prime_1_frasi | 0.282 |
| testo_tenuto_prime_2_frasi | 0.512 |
| testo_tenuto_prime_3_frasi | 0.678 |
| testo_tenuto_prime_5_frasi | 0.852 |
| tau_tagliati_a_300 | 0.941 |
| tau_tagliati_a_600 | 0.538 |
| tau_tagliati_a_900 | 0.33 |

## 2. Dove compare l'informazione esplicita

| query | cosa | insieme | con_menzione | in_frase_1 | in_frasi_1_2 | nota |
|---|---|---|---|---|---|---|
| Q1 | guerra nominata (positivi) | 200 | 90 | 24 | 57 | nei 800 negativi la guerra è nominata in 16 |
| Q4 | nome del genere vero (etichetta singola) | 527 | 401 | 369 | 394 |  |
| Q6 | titolo del romanzo nel lead del film | 51 | 36 | 11 | 24 |  |

Quota delle menzioni che sopravvivono a ogni taglio (solo i film che la menzione ce l'hanno):

| tipo | taglio | Q1 | Q4 | Q6 |
|---|---|---|---|---|
| frasi | prime 1 frasi | 0.267 | 0.92 | 0.306 |
| frasi | prime 2 frasi | 0.633 | 0.983 | 0.667 |
| frasi | prime 3 frasi | 0.844 | 0.988 | 0.806 |
| frasi | prime 5 frasi | 0.933 | 0.99 | 0.917 |
| frasi | lead intero | 1 | 1 | 1 |
| caratteri | 300 caratteri | 0.422 | 0.98 | 0.611 |
| caratteri | 600 caratteri | 0.911 | 0.99 | 0.861 |
| caratteri | 900 caratteri | 0.989 | 0.995 | 0.917 |
| caratteri | 1200 caratteri | 0.989 | 0.998 | 0.944 |
| caratteri | 1800 caratteri | 1 | 0.998 | 1 |
| caratteri | nessun taglio | 1 | 1 | 1 |

## 3. Estrazione con regole

`is a [anno] <descrizione> film` nella prima frase (Q4) e `based on ... <titolo>` nel lead (Q6).

| regola | film | schema_trovato | genere_vero_nella_frase | coppie | frase_based_on_trovata | con_il_titolo_giusto |
|---|---|---|---|---|---|---|
| Q4_frase_is_a | 527 | 488 | 377 |  |  |  |
| Q6_based_on |  |  |  | 51 | 43 | 22 |

## 4. Entità nominate per posizione della frase (spaCy en_core_web_sm)

Numero medio di entità per frase; frasi per posizione: [1000, 985, 859, 674, 508, 387].

| entita | frase_1 | frase_2 | frase_3 | frase_4 | frase_5 | frase_6 |
|---|---|---|---|---|---|---|
| PERSON | 2.51 | 1.8 | 1.45 | 0.95 | 0.84 | 0.67 |
| DATE | 1.05 | 0.48 | 0.43 | 0.5 | 0.43 | 0.53 |
| ORG | 0.64 | 0.47 | 0.47 | 0.62 | 0.6 | 0.65 |
| NORP | 1 | 0.26 | 0.19 | 0.19 | 0.16 | 0.15 |
| GPE | 0.26 | 0.35 | 0.37 | 0.42 | 0.34 | 0.4 |
| CARDINAL | 0.11 | 0.09 | 0.11 | 0.12 | 0.15 | 0.23 |
| ORDINAL | 0.04 | 0.14 | 0.12 | 0.11 | 0.09 | 0.11 |
| WORK_OF_ART | 0.08 | 0.09 | 0.06 | 0.06 | 0.06 | 0.07 |
| EVENT | 0.05 | 0.08 | 0.09 | 0.08 | 0.04 | 0.06 |
| FAC | 0.03 | 0.04 | 0.04 | 0.04 | 0.04 | 0.05 |
| LOC | 0.03 | 0.04 | 0.03 | 0.04 | 0.03 | 0.02 |
| MONEY | 0 | 0 | 0.03 | 0.04 | 0.12 | 0.08 |
| PRODUCT | 0.02 | 0.02 | 0.02 | 0.01 | 0.02 | 0.02 |
| LANGUAGE | 0.04 | 0.02 | 0.01 | 0.01 | 0.01 | 0.02 |
| TIME | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.02 |
| LAW | 0.01 | 0 | 0 | 0 | 0.01 | 0.01 |
| QUANTITY | 0 | 0 | 0 | 0.01 | 0 | 0 |
| PERCENT | 0 | 0 | 0 | 0 | 0 | 0 |

## 5. Segnale semantico per Q1 (embedding, nessun LLM)

Similarità tra ogni frase del lead e il criterio *the film deals with the Second World War*.

| segnale | auc_positivi_vs_negativi |
|---|---|
| max similarità nelle prime 1 frasi | 0.825 |
| max similarità nelle prime 2 frasi | 0.815 |
| max similarità nelle prime 3 frasi | 0.822 |
| max similarità nelle prime 5 frasi | 0.805 |
| max similarità nel lead intero | 0.784 |

| frase_piu_simile_al_criterio | positivi |
|---|---|
| 1 | 51 |
| 2 | 63 |
| 3 | 46 |
| 4 | 19 |
| 5 | 10 |
| 6 | 3 |
| 7 | 2 |
| 8 | 2 |
| 9 | 1 |
| 10 | 1 |
| 13 | 1 |
| 14 | 1 |
