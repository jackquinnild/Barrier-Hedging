"""Bookkeeping for one hedged barrier option: cash, trades, positions and P&L, day by day.

The dealer is long one down-and-in put per unit of the index. Amounts are in index points; positive
means we own it or hold cash.
"""

from dataclasses import dataclass, field
import math

@dataclass
class DayInput:
    """Everything known at one close, after the hedge rule has decided what to hold."""
    date: str
    spot: float                  # index close
    dip_value: float             # model value of our down-and-in put at this close; on the last day: its payoff
    target_units: float          # index units the hedge rule wants to hold after this close (ignored on the last day: we sell everything)
    option_trades: dict = field(default_factory=dict)   # {name: (quantity, price)}: qty > 0 buy at price (the ask), qty < 0 sell at price (the bid)
    option_marks: dict = field(default_factory=dict)    # {name: mid price at this close} for every option held; on the last day: payoff at expiry
    dt_next: float = 0.0         # years until the next close (0 on the last day)
    rate: float = 0.0            # continuously compounded rate earned/paid on cash until the next close
    div_yield: float = 0.0       # dividend yield earned on index units held until the next close


def run_ledger(days, premium, index_cost):
  """Walk through the closes and keep the books.

  days:        list[DayInput], first = issue day, last = expiry day
  premium:     price we paid for the down-and-in put on the issue day (index points)
  index_cost:  trading cost on the index as a fraction of traded value (0.0005 = 5 basis points)

  Returns one dict per day with: units, cash, option_value, portfolio_value, daily_pnl, cum_costs.
  """
  cash = -premium
  units = 0.0
  positions = {}
  results = []
  prev_day = None
  prev_value = 0.0
  cum_costs = 0.0
  for i, day in enumerate(days):
    option_value = 0.0
    last = (i == len(days) - 1)
    target = 0.0 if last else day.target_units
    # 1. if prev_day exists: dividends on units held, interest on cash
    if prev_day != None:
      cash += units * prev_day.spot * prev_day.div_yield * prev_day.dt_next
      cash *= math.exp(prev_day.rate * prev_day.dt_next) 
    
    # 2. index trade towards target (0 on the last day), commission
    adjust_units = target - units
    cash -= adjust_units * day.spot
    units = target

    incurred_trading_cost = abs(adjust_units) * day.spot * index_cost
    cash -= incurred_trading_cost
    cum_costs += incurred_trading_cost

    for name, (quantity, price) in day.option_trades.items():
          cash -= quantity * price
          positions[name] = positions.get(name, 0) + quantity # positive denotes long, negative denotes short

    # 3. option trades -> update positions and cash
    # This only includes the options we hold as hedges (not the barrier)
    for name, quantity in positions.items():
          # 4. option_value = sum of quantity * mark over positions
          option_value += quantity * day.option_marks[name]

    if last:
      barrier_value = day.dip_value # Shouldn't have to condition because it's zero if barrier not activated. 
      cash += option_value + barrier_value
      portfolio_value = cash
      option_value = 0
      positions = {}
    else:
       portfolio_value = day.dip_value + units * day.spot + option_value + cash

    if prev_day is None:
       daily_pnl = portfolio_value
    else:
       daily_pnl = portfolio_value - prev_value

    # 5. portfolio value, daily P&L, append dict, update prev_day / prev_value
    results.append({"units": units, "cash": cash, "option_value": option_value, "portfolio_value": portfolio_value, 
                    "daily_pnl": daily_pnl, "cum_costs": cum_costs})
    prev_day = day
    prev_value = portfolio_value # The position in the index, positions in options, and barrier are all cash settled by now so all portfolio value is in cash

    
  return results
