## Hedged P&L per contract (basis points of notional)

1018 contracts issued weekly, 2005-01 to 2025-03; 145 knocked in. Worst 5% avg is the average of the worst 5% of contracts.

| rule                                     |   mean all |   std all |   mean 2005-16 |   std 2005-16 |   mean 2017-25 |   std 2017-25 |   worst 5% avg |
|:-----------------------------------------|-----------:|----------:|---------------:|--------------:|---------------:|--------------:|---------------:|
| No hedge                                 |       -133 |       495 |           -139 |           516 |           -125 |           463 |           -702 |
| Black-Scholes, strike vol                |        -40 |       185 |            -53 |           174 |            -21 |           198 |           -241 |
| Black-Scholes, at-the-money vol          |        -44 |       162 |            -52 |           161 |            -31 |           163 |           -241 |
| Black-Scholes, barrier vol               |        -22 |       139 |            -35 |           143 |             -2 |           130 |           -271 |
| Local vol                                |         -3 |       125 |            -18 |           131 |             19 |           112 |           -274 |
| Local vol, barrier moved 1 move closer   |         -2 |       127 |            -18 |           133 |             21 |           114 |           -319 |
| Local vol, barrier moved 0.5 move closer |         -2 |       125 |            -18 |           131 |             20 |           111 |           -289 |
| Local vol, barrier moved 0.5 move away   |         -4 |       127 |            -19 |           133 |             17 |           115 |           -277 |
| Local vol, barrier moved 1 move away     |         -6 |       132 |            -21 |           138 |             16 |           120 |           -286 |
| Put spread within 1 move                 |         -8 |       125 |            -25 |           132 |             17 |           111 |           -298 |
| Put spread within 2 moves                |        -12 |       125 |            -30 |           131 |             16 |           111 |           -311 |
| Put spread within 3 moves                |        -15 |       125 |            -35 |           129 |             15 |           111 |           -312 |
| Put spread within 5 moves                |        -19 |       125 |            -41 |           130 |             14 |           111 |           -314 |
| Put spread within 3 moves, at mid        |         -3 |       122 |            -19 |           127 |             19 |           111 |           -267 |
| Static hedge                             |       -172 |       345 |           -265 |           383 |            -36 |           218 |          -1281 |
| Static hedge, at mid                     |         36 |       117 |             31 |           112 |             44 |           125 |           -285 |
| Volatility hedge                         |         37 |       130 |             19 |           126 |             63 |           131 |           -324 |
| Volatility hedge, at mid                 |         62 |       125 |             55 |           123 |             72 |           127 |           -275 |
