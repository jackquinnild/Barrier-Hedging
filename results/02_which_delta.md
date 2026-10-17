## Spread of hedged P&L: local vol relative to other deltas

Ratio of standard deviations, with 90% intervals from a block bootstrap by issue quarter. Below 1 means local vol hedged better.

| compared with                            | local vol / rule, all years   | local vol / rule, 2005-16   | local vol / rule, 2017-25   |
|:-----------------------------------------|:------------------------------|:----------------------------|:----------------------------|
| Black-Scholes, strike vol                | 0.68 [0.57, 0.81]             | 0.75 [0.66, 0.90]           | 0.57 [0.42, 0.80]           |
| Black-Scholes, at-the-money vol          | 0.77 [0.69, 0.89]             | 0.81 [0.72, 1.04]           | 0.69 [0.58, 0.86]           |
| Black-Scholes, barrier vol               | 0.90 [0.82, 1.04]             | 0.91 [0.84, 1.06]           | 0.86 [0.71, 1.14]           |
| Local vol, barrier moved 0.5 move closer | 1.00 [0.97, 1.04]             | 1.00 [0.95, 1.05]           | 1.00 [0.98, 1.02]           |
| Local vol, barrier moved 1 move closer   | 0.98 [0.92, 1.05]             | 0.98 [0.89, 1.08]           | 0.98 [0.94, 1.02]           |
| Local vol, barrier moved 0.5 move away   | 0.98 [0.97, 1.00]             | 0.98 [0.96, 1.00]           | 0.98 [0.96, 0.99]           |
| Local vol, barrier moved 1 move away     | 0.95 [0.91, 0.98]             | 0.95 [0.89, 1.00]           | 0.94 [0.91, 0.97]           |
