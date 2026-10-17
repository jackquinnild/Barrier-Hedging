## P&L by what happened to the contract

Near miss: came within 2 daily moves of the barrier but never closed below it. This grouping uses hindsight; it describes outcomes and is not a trading rule.

| outcome     | rule                       |   contracts | mean              |   worst 5% avg |
|:------------|:---------------------------|------------:|:------------------|---------------:|
| knocked in  | No hedge                   |         145 | 654 [357, 1003]   |           -795 |
| knocked in  | Local vol                  |         145 | 23 [-39, 83]      |           -292 |
| knocked in  | Black-Scholes, strike vol  |         145 | 182 [110, 260]    |           -254 |
| knocked in  | Black-Scholes, barrier vol |         145 | 153 [74, 232]     |           -234 |
| knocked in  | Volatility hedge           |         145 | -160 [-198, -122] |           -498 |
| knocked in  | Volatility hedge, at mid   |         145 | -118 [-159, -78]  |           -427 |
| near miss   | No hedge                   |          75 | -342 [-397, -286] |           -874 |
| near miss   | Local vol                  |          75 | -83 [-132, -33]   |           -378 |
| near miss   | Black-Scholes, strike vol  |          75 | 72 [-11, 167]     |           -319 |
| near miss   | Black-Scholes, barrier vol |          75 | -95 [-135, -54]   |           -357 |
| near miss   | Volatility hedge           |          75 | -19 [-51, 14]     |           -271 |
| near miss   | Volatility hedge, at mid   |          75 | 33 [4, 63]        |           -179 |
| stayed away | No hedge                   |         798 | -257 [-282, -233] |           -659 |
| stayed away | Local vol                  |         798 | -0 [-12, 13]      |           -227 |
| stayed away | Black-Scholes, strike vol  |         798 | -91 [-100, -82]   |           -227 |
| stayed away | Black-Scholes, barrier vol |         798 | -47 [-57, -36]    |           -251 |
| stayed away | Volatility hedge           |         798 | 78 [67, 90]       |            -89 |
| stayed away | Volatility hedge, at mid   |         798 | 98 [88, 108]      |            -45 |
