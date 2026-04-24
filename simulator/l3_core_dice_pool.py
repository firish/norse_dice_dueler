"""L3 entrypoint for the core-dice pool sweep.

What this file does:
  - Preserves the level-oriented `simulator.l3_core_dice_pool` command.
  - Delegates the actual sweep implementation to `balance.l3_core_dice_pool`.

What this file does not do:
  - Hold the search logic itself.
  - Define benchmark results directly.

This level-oriented wrapper keeps the L3 harness discoverable under
`simulator/` while delegating the actual search implementation to `balance/`.
"""

from balance.l3_core_dice_pool import main


if __name__ == "__main__":
    main()
