## The main numbers under five contract designs

base: barrier 90%, 3 months. barrier_85 / barrier_95: other barrier levels. tenor_1m / tenor_6m: other maturities.

| index                                      | base              | barrier_85        | barrier_95        | tenor_1m          | tenor_6m          |
|:-------------------------------------------|:------------------|:------------------|:------------------|:------------------|:------------------|
| contracts                                  | 1018              | 1018              | 1018              | 832               | 1007              |
| knocked in                                 | 145               | 67                | 332               | 45                | 241               |
| LV / Black-Scholes, strike vol             | 0.68 [0.56, 0.82] | 0.43 [0.30, 0.69] | 0.93 [0.83, 1.04] | 0.75 [0.66, 0.85] | 0.83 [0.75, 0.94] |
| LV / Black-Scholes, at-the-money vol       | 0.77 [0.70, 0.89] | 0.72 [0.64, 0.83] | 0.83 [0.73, 0.98] | 0.82 [0.76, 0.91] | 0.78 [0.70, 0.90] |
| LV / Black-Scholes, barrier vol            | 0.90 [0.82, 1.04] | 0.94 [0.86, 1.09] | 0.88 [0.80, 1.01] | 0.98 [0.95, 1.01] | 0.91 [0.81, 1.06] |
| days within 3 moves %                      | 2.8               | 1.1               | 6.9               | 3.1               | 2.0               |
| their share of squared P&L %               | 22.8              | 27.9              | 26.4              | 61.9              | 11.5              |
| near-miss mean                             | -83.0             | -70.0             | -34.0             | -76.0             | -60.0             |
| Static hedge minus LV                      | -168              | -191              | -117              | -137              | -195              |
| Static hedge, at mid minus LV              | 39                | 36                | 31                | 10                | 55                |
| Volatility hedge minus LV                  | 40                | 27                | 35                | 23                | 51                |
| Volatility hedge, at mid minus LV          | 65                | 56                | 59                | 43                | 75                |
| Put spread within 3 moves minus LV         | -12               | -21               | -5                | -11               | -11               |
| Put spread within 3 moves, at mid minus LV | 0                 | -1                | -1                | -1                | -1                |
