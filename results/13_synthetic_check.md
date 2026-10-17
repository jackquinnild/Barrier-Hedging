## Synthetic check: local vol is the true model

2000 paths simulated from the local-vol surface fitted on 2024-03-01. Standard deviation of hedged P&L (bp of notional), by outcome.

|                                 |   knocked in |   near miss |   stayed away |   all paths |
|:--------------------------------|-------------:|------------:|--------------:|------------:|
| Black-Scholes, strike vol       |          430 |         645 |            79 |         224 |
| Local vol (the true model here) |          181 |         330 |            51 |          95 |
| No hedge                        |         1060 |           0 |             0 |         501 |
| number of paths                 |          212 |          59 |          1729 |        2000 |
