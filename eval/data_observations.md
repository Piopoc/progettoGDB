| # | Osservazione | Popolazione | Valore | Riferimento | Come si calcola |
|---|---|---|---|---|---|
| 1 | Entità nel dev set | tutte | 1250 film, 600 romanzi | README: 1.250 film, 600 romanzi | righe di entities.csv per colonna class |
| 2 | Film senza anno di prima uscita | film | 2 | - | first_year vuoto in entities.csv |
| 3 | Descrizioni scartate dallo screening | film | 74 su 1250 (5.9%) | lol.md: 74 entità | description_screened vuota. Motivi (description_flags): {'documentary film': 44, 'drama film': 10, 'horror film': 6, 'comedy film': 5, 'war film': 5, 'World War II': 2, 'science fiction film': 1, 'action film': 1} |
| 4 | Lunghezza di τ0 senza taglio (caratteri) | film | mediana 635; oltre 1200: 18.2%; oltre 600: 53.0%; oltre 2000: 5.8% | - | lunghezza di titolo + descrizione screened + lead, senza taglio |
| 5 | Token di τ0 (con taglio a 1200) | main set (1000 film) | media 167.6; 90° percentile 270 | README: media 168, p90 270 (cl100k_base) | token_stats su τ0 per i film del main set |
| 6 | L'anno di uscita compare già nel testo | film | in descrizione+lead: 99.0%; solo nella descrizione: 92.5% | - | first_year come sottostringa di description_screened e lead |
| 7 | Lead con a capo interni | film | 62.0% | - | presenza di \n nel lead (conta per la chiave della cache) |
| 8 | La descrizione screened contiene 'directed by' | film | 33.2% | - | ricerca della stringa nella descrizione |
| 9 | Il regista (statement del grafo) compare già in τ0 | main set, film con P57 | 944 su 970 (97.3%) | - | almeno una label di P57 come sottostringa del testo di τ0 |
| 10 | Il paese di origine (statement del grafo) compare già in τ0 | main set, film con P495 | 366 su 999 (36.6%) | - | almeno una label di P495 come sottostringa del testo di τ0 |
| 11 | Positivi Q1 (chiave espansa) | main set (1000 film) | 200 su 1000 | slide: 200 su 1000 | righe di gt/q1.csv con path vero |
| 12 | Positivi che nominano la guerra | main set (1000 film) | 90 su 200 (45.0%) | slide: 90 su 200 | parole chiave: World War II | Second World War | WWII | World War Two (senza distinzione di maiuscole); testo di τ0 senza taglio |
| 13 | Negativi che nominano la guerra | main set (1000 film) | 16 su 800 (2.0%) | slide: 16 su 800 | come sopra |
| 14 | Recall del filtro per parola chiave | main set (1000 film) | 0.45 | slide: 0,45 | positivi che nominano la guerra / positivi |
| 15 | Positivi impliciti (non nominano la guerra) | main set (1000 film) | 110 su 200 (55.0%) | slide: circa 110 su 200 | positivi senza parole chiave nel testo: solo l'inferenza li trova |
| 16 | Prima menzione della guerra oltre il taglio | main set (1000 film), film che la nominano | oltre 1200 car.: 1 su 106; oltre 600: 12 su 106 | - | posizione della prima occorrenza nel testo di τ0 senza taglio. Misura le parole chiave, non la comprensione del modello. |
