#!/usr/bin/env python3
"""SYS 301 team budget ledger — Schrute Bucks.

Edit ENTRIES below when something is bought, sold back, or charged. That is the whole file.

    ./inventory.py              current balance
    ./inventory.py --verbose    full statement

Class rules that matter here:
  - Starting budget is 100 SB.
  - Only the Supplier may buy, sell, or handle money.
  - Selling back to the store pays 90% of the listed price, ROUNDED DOWN. Use sellback() for that.
  - Meetings beyond the daily standup cost 1 SB per person per minute (2 SB/min for an outside guest).
  - Role violations cost 2 SB each.
"""

import sys

START_BALANCE = 100

# [date, description, quantity, unit cost]
#
# Cost is what it takes OUT of the budget, per unit.
# Money coming BACK IN (a sell-back, a refund) is a NEGATIVE cost.
#
# Store prices can change during the project, so record the price ACTUALLY PAID on each line.
# There is deliberately no price list to keep in sync.
ENTRIES = [
    ["2026-08-25", "Motors",                            2, 10],
    ["2026-08-25", "Wheels",                            2,  7],
    ["2026-08-25", "Project budget reallocation",       1, 10],
]

# Motors available from the store: Technic Large Angular Motor 45602, Small Angular Motor 45607.
# Sensors available: Color 45605, Distance 45604, Force 45606.
# Not yet owned as of 2026-08-25: any sensor, mounting blocks, axles.


def sellback(listed_price):
    """Return the negative cost of selling one item back: 90% of listed, rounded down."""
    return -(listed_price * 9 // 10)


def main():
    args = sys.argv[1:]
    verbose = args in (["-v"], ["--verbose"])
    if args and not verbose:
        sys.exit("usage: inventory.py [--verbose]")

    spent = sum(qty * cost for _, _, qty, cost in ENTRIES)
    balance = START_BALANCE - spent

    if verbose:
        print("SYS 301 — Team Budget (Schrute Bucks)\n")
        print(f"{'DATE':<12} {'DESCRIPTION':<36} {'QTY':>4} {'UNIT':>6} {'AMOUNT':>8} {'BALANCE':>8}")
        print("-" * 78)
        running = START_BALANCE
        print(f"{'':<12} {'Starting budget':<36} {'':>4} {'':>6} {'':>8} {running:>8}")
        for date, desc, qty, cost in ENTRIES:
            amount = qty * cost
            running -= amount
            print(f"{date:<12} {desc:<36} {qty:>4} {cost:>6} {-amount:>8} {running:>8}")
        print("-" * 78)
        print(f"{'':<12} {'Total spent':<36} {'':>4} {'':>6} {-spent:>8} {balance:>8}\n")

    print(f"Balance: {balance} SB")
    if balance < 0:
        print("OVERDRAWN — sell something back or the Supplier cannot cover the next bill.")


if __name__ == "__main__":
    main()
