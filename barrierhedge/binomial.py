"""Binomial-tree price of a down-and-in put whose barrier is checked on chosen steps.

This was the first pricer in the project, built from the backward recursion taught in CMU 21-370.
Each node carries two values: what the option is worth if the barrier has already been hit
(a plain put) and what it is worth if it hasn't. On a checked step, any node at or below the
barrier switches from the second to the first. The PDE engine uses the same idea on a finer grid,
and the test suite checks the two agree.
"""


def price_down_and_in_tree(spot, strike, barrier, size, steps, up, down, probability_up, discount,
                           monitoring_steps, activated=False):
    monitoring_steps = set(monitoring_steps)

    terminal_spot_prices = [spot * up**k * down**(steps - k) for k in range(steps + 1)]
    active_values = [max(0, strike - s) for s in terminal_spot_prices]
    waiting_values = [0.0] * (steps + 1)
    if steps in monitoring_steps:
        waiting_values = [a if s <= barrier else 0.0 for a, s in zip(active_values, terminal_spot_prices)]

    # Work backwards one time level per pass. j counts up moves.
    while len(active_values) > 1:
        n = len(active_values) - 2   # time index of the parent level
        active_parents, waiting_parents = [], []
        for j in range(n + 1):
            active = discount * (probability_up * active_values[j + 1] + (1 - probability_up) * active_values[j])
            waiting = discount * (probability_up * waiting_values[j + 1] + (1 - probability_up) * waiting_values[j])
            node_spot = spot * up**j * down**(n - j)
            if n in monitoring_steps and node_spot <= barrier:
                waiting = active
            active_parents.append(active)
            waiting_parents.append(waiting)
        active_values, waiting_values = active_parents, waiting_parents

    root_value = active_values[0] if activated else waiting_values[0]
    return size * root_value


if __name__ == "__main__":
    # The four-path example the tree was first checked against: should print 750.0
    print(price_down_and_in_tree(spot=100.0, strike=105.0, barrier=95.0, size=100, steps=2, up=1.1, down=0.9,
                                 probability_up=0.5, discount=1.0, monitoring_steps={1, 2}))
