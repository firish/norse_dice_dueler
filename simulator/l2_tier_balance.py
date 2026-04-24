"""L2 entrypoint for the tier-balance sweep.

What this file does:
  - Preserves the level-oriented `simulator.l2_tier_balance` command.
  - Delegates the actual sweep implementation to `balance.l2_tier_balance`.

What this file does not do:
  - Hold the search logic itself.
  - Define benchmark results directly.

This level-oriented wrapper keeps the L2 harness discoverable under
`simulator/` while delegating the actual search implementation to `balance/`.
"""

from balance.l2_tier_balance import main


if __name__ == "__main__":
    main()
