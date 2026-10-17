## Leaving out the 2008 and 2020 crises

Contracts alive at any point in Sep 2008 - Mar 2009 or Feb - Apr 2020 are dropped.

| rule                            |   contracts | local vol std / rule std   | mean minus local vol (bp)   |
|:--------------------------------|------------:|:---------------------------|:----------------------------|
| Black-Scholes, strike vol       |         952 | 0.63 [0.51, 0.83]          | nan                         |
| Black-Scholes, at-the-money vol |         952 | 0.85 [0.75, 0.98]          | nan                         |
| Black-Scholes, barrier vol      |         952 | 1.05 [0.98, 1.13]          | nan                         |
| Static hedge                    |         952 | nan                        | -124 [-158, -89]            |
| Volatility hedge                |         952 | nan                        | 54 [41, 68]                 |
