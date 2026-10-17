## Hedges that use listed puts, compared with local-vol delta

Mean difference in bp per contract (90% interval) and ratio of standard deviations.

| rule                              | mean vs local vol, all years   |   std ratio, all years | mean vs local vol, 2005-16   |   std ratio, 2005-16 | mean vs local vol, 2017-25   |   std ratio, 2017-25 |
|:----------------------------------|:-------------------------------|-----------------------:|:-----------------------------|---------------------:|:-----------------------------|---------------------:|
| Put spread within 1 move          | -5 [-7, -3]                    |                   1    | -7 [-10, -4]                 |                 1.01 | -2 [-3, -1]                  |                 1    |
| Put spread within 2 moves         | -8 [-12, -5]                   |                   1    | -12 [-17, -7]                |                 1    | -3 [-5, -2]                  |                 0.99 |
| Put spread within 3 moves         | -12 [-16, -8]                  |                   1    | -17 [-24, -11]               |                 0.99 | -4 [-6, -2]                  |                 0.99 |
| Put spread within 5 moves         | -16 [-20, -12]                 |                   1    | -23 [-29, -16]               |                 0.99 | -5 [-8, -3]                  |                 0.99 |
| Put spread within 3 moves, at mid | -0 [-1, 0]                     |                   0.98 | -0 [-1, 0]                   |                 0.97 | 0 [-0, 1]                    |                 0.99 |
| Static hedge                      | -168 [-219, -123]              |                   2.76 | -246 [-323, -183]            |                 2.92 | -55 [-103, -12]              |                 1.95 |
| Static hedge, at mid              | 39 [25, 53]                    |                   0.94 | 49 [31, 67]                  |                 0.85 | 25 [2, 48]                   |                 1.11 |
| Volatility hedge                  | 40 [21, 57]                    |                   1.04 | 37 [15, 59]                  |                 0.96 | 44 [13, 75]                  |                 1.17 |
| Volatility hedge, at mid          | 65 [49, 81]                    |                   1    | 74 [54, 93]                  |                 0.94 | 53 [23, 83]                  |                 1.14 |
