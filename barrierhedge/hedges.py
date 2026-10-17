"""Hedging rules for a dealer who is long a down-and-in put.

Each close, a rule looks at a View of the market and returns the number of index units it wants to
hold plus any listed-put trades. The ledger does the bookkeeping. Deltas are in index units per
option; the long put has negative delta, so hedges buy index units: units = -(total delta held).
"""

from dataclasses import dataclass
from typing import Callable

from barrierhedge.market import Chain


@dataclass
class View:
    """Everything a rule is allowed to know at one close."""
    day: int                      # 0 on the issue date
    spot: float
    activated: bool               # the barrier has been hit at this close or an earlier one
    deltas: dict                  # model name -> delta of the barrier option
    vega: float                   # local-vol vega of the barrier option, per volatility point
    gap: float                    # local-vol knock-in jump at today's spot: value if hit minus value if not
    distance: float               # ln(spot / barrier) measured in typical daily moves
    chain: Chain                  # listed puts with the same expiry
    put_vega: Callable            # strike -> vega of one listed put, per volatility point
    is_last: bool = False


def static_weights(K, B, hi, lo):
    """Puts that replicate a down-and-in put (strike K above barrier B) if put-call symmetry holds.

    Carr, Ellis and Gupta (1998): with a symmetric smile, paths that touch B and end at S are worth the
    same as paths that end at the mirror point B^2 / S. That turns the barrier option into an
    ordinary payoff at expiry, zero above B and (K - S) + (K / B)(S - B^2 / K)+ below it, which is

        2 (K - B) x digital(S < B)  -  (K / B - 1) x put(B)  +  (K / B) x put(B^2 / K)

    The digital is built as a put spread between the listed strikes hi > B > lo.
    """
    digital = 2 * (K - B) / (hi - lo)
    legs = {}
    for strike, qty in ((hi, digital), (lo, -digital), (B, -(K / B - 1)), (B * B / K, K / B)):
        legs[strike] = legs.get(strike, 0.0) + qty
    return legs


class Rule:
    name = "rule"

    def __init__(self, K, B, at_mid=False):
        self.K, self.B = K, B
        self.at_mid = at_mid      # trade listed puts at mid instead of crossing the bid/ask
        self.held = {}            # listed put strike -> quantity

    def option_delta(self, view):
        return sum(qty * view.chain.quote(k).delta for k, qty in self.held.items())

    def trade_to(self, view, wanted):
        """Move the listed-put position to `wanted`; buys pay the ask and sells receive the bid."""
        trades = {}
        for k in set(self.held) | set(wanted):
            change = wanted.get(k, 0.0) - self.held.get(k, 0.0)
            if abs(change) > 1e-12:
                q = view.chain.quote(k)
                price = q.mid if self.at_mid else (q.ask if change > 0 else q.bid)
                trades[k] = (change, price)
        self.held = {k: v for k, v in wanted.items() if abs(v) > 1e-12}
        return trades

    def step(self, view):
        raise NotImplementedError


class Unhedged(Rule):
    name = "unhedged"

    def step(self, view):
        return 0.0, {}


class DeltaHedge(Rule):
    """Index only, using one model's delta. The replay supplies the deltas by name: Black-Scholes at a
    few choices of volatility, local vol, and local vol with the barrier shifted for hedging purposes."""

    def __init__(self, K, B, model):
        super().__init__(K, B)
        self.model = model
        self.name = model

    def step(self, view):
        return -view.deltas[self.model], {}


class StaticHedge(Rule):
    """Sell the put-call-symmetry portfolio on the issue date and hold it, delta-hedging what's left with
    local-vol deltas. If the barrier is hit, buy the portfolio back and keep delta-hedging the plain put."""

    def __init__(self, K, B, width, at_mid=False):
        super().__init__(K, B, at_mid)
        self.width = width
        self.name = "static_mid" if at_mid else "static"
        self.closed = False

    def step(self, view):
        trades = {}
        if view.day == 0:
            hi, lo = view.chain.bracket(self.B, self.width)
            legs = static_weights(self.K, self.B, hi, lo)
            # Map the two theoretical strikes onto listed ones before selling.
            listed = {}
            for k, qty in legs.items():
                k = k if k in (hi, lo) else view.chain.nearest(k)
                listed[k] = listed.get(k, 0.0) - qty
            trades = self.trade_to(view, listed)
        elif view.activated and not self.closed and not view.is_last:
            trades = self.trade_to(view, {})
            self.closed = True
        return -(view.deltas["local_vol"] + self.option_delta(view)), trades


class SpreadOverlay(Rule):
    """Local-vol delta hedge, plus a put spread around the barrier while spot is close to it.

    When spot comes within `enter` daily moves of the barrier, sell a put spread straddling it, sized so
    its payoff matches the model's knock-in jump. Buy it back if spot moves more than `enter + 1` daily
    moves away, or when the barrier is hit.
    """

    def __init__(self, K, B, enter, width, at_mid=False):
        super().__init__(K, B, at_mid)
        self.enter, self.exit, self.width = enter, enter + 1.0, width
        self.name = f"spread_{enter:g}" + ("_mid" if at_mid else "")

    def step(self, view):
        trades = {}
        if not self.held and not view.activated and not view.is_last and view.distance < self.enter:
            hi, lo = view.chain.bracket(self.B, self.width)
            n = view.gap / (hi - lo)
            trades = self.trade_to(view, {hi: -n, lo: n})
        elif self.held and not view.is_last and (view.activated or view.distance > self.exit):
            trades = self.trade_to(view, {})
        return -(view.deltas["local_vol"] + self.option_delta(view)), trades


class VegaHedge(Rule):
    """Local-vol delta hedge plus a volatility hedge: sell listed puts struck near the barrier so the
    position's sensitivity to a parallel move in volatility is close to zero.

    To keep trading costs down, the put position is only resized when it is more than `band` (as a
    fraction) away from target. Once the barrier is hit the puts are bought back.
    """

    def __init__(self, K, B, band=0.25, at_mid=False):
        super().__init__(K, B, at_mid)
        self.band = band
        self.strike = None
        self.name = "vega_mid" if at_mid else "vega"

    def step(self, view):
        trades = {}
        if view.activated or view.is_last:
            if self.held and not view.is_last:
                trades = self.trade_to(view, {})
        else:
            if self.strike is None:
                self.strike = view.chain.nearest(self.B)
            put_vega = view.put_vega(self.strike)
            if put_vega > 1e-6:
                target = -view.vega / put_vega
                current = self.held.get(self.strike, 0.0)
                if abs(target - current) > self.band * max(abs(target), 1e-9):
                    trades = self.trade_to(view, {self.strike: target})
        return -(view.deltas["local_vol"] + self.option_delta(view)), trades
