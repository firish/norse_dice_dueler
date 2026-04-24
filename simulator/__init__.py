"""Level-oriented simulator entrypoints for Norse Dice Dueler.

What this package is:
  - The user-facing home for L0-L4 benchmark and diagnostic harnesses.
  - The place to run fixed validation checks by progression level.

What this package is not:
  - The home of parameter searches or balance sweeps.
  - The home of core game rules or agent implementations.

Some simulator entrypoints are thin wrappers around `balance/` modules so the
level-based layout stays intuitive while the search logic lives elsewhere.
"""
