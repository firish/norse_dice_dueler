"""L4 entrypoint for the single-condition drift sweep.

What this file does:
  - Preserves the level-oriented `simulator.l4_condition_drift` command.
  - Delegates the actual sweep implementation to `balance.l4_condition_drift`.

What this file does not do:
  - Hold the search logic itself.
  - Define benchmark results directly.

This level-oriented wrapper keeps the L4 harness discoverable under
`simulator/` while delegating the actual search implementation to `balance/`.
"""

from balance.l4_condition_drift import main


if __name__ == "__main__":
    main()
