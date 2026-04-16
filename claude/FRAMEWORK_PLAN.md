# FRAMEWORK_PLAN.md - Reusable Game Balance Toolkit

> **Purpose:** This file documents the long-term architecture for turning the Fjöld simulator
> into a reusable game balance testing toolkit. It should be read alongside CLAUDE.md.
> When building the simulator, every interface decision should be checked against this file.
> If a simulator decision conflicts with or enables this plan, flag it to the developer.

---

## 1. The Vision

The three repos being built here are not just Fjöld tools - they are the foundation of a
**game balance testing toolkit** that any developer with a Gymnasium-compatible game environment
can plug into.

The pitch:
> "If your turn-based game implements reset/step/legal_actions and tags its actions with
> semantic labels, you get a full suite of agents and Optuna-driven balance optimization for free."

There is no widely-adopted open-source equivalent of this for indie game developers. PettingZoo
standardized multi-agent environments but nobody owns the balance testing layer on top of it.

---

## 2. The Three-Repo Architecture

### Repo 1 - Simulator (this repo)
Fjöld-specific: GameState, die types, God Powers, Runes, Conditions, Battlefield logic.
**Cannot be reused as-is** - but its external interface MUST be designed for reusability.
The interface contract (see Section 3) is what the other two repos depend on.

### Repo 2 - Agent Framework
A game-agnostic library of agents. Any environment that satisfies the interface contract
can use these agents without modification.

Agents shipped:
- `RandomAgent` - 100% reusable, no game knowledge required.
- `GreedyAgent` - 100% reusable framework; game developer injects a `StateEvaluator`.
- `ArchetypeAgent` - 100% reusable framework; game developer injects a `List[Rule]`.
- `MCTSAgent` - 90% reusable; tree search logic is generic, rollout policy is injected.

### Repo 3 - Balance Toolkit
A game-agnostic Optuna-driven balance optimizer plus analysis dashboard.
Game developer defines a parameter space and target metrics. The toolkit handles the rest.

---

## 3. The Interface Contract (what Repo 1 MUST implement)

For Repo 2 and Repo 3 to be truly game-agnostic, every game environment (including Fjöld)
must satisfy this interface. This is based on the OpenAI Gymnasium standard.

### 3.1 Environment Interface

```python
class GameEnvironment(ABC):

    def reset(self) -> GameState:
        """Start a new game. Return the initial state."""
        ...

    def step(self, action: Action) -> tuple[GameState, float, bool, dict]:
        """
        Apply action to current state.
        Returns: (new_state, reward, done, info)
        - reward: float, from the perspective of the active player
        - done: True if the game is over
        - info: dict with optional debug/metadata
        """
        ...

    def legal_actions(self) -> list[Action]:
        """Return all legal actions from the current state."""
        ...

    def current_player(self) -> int:
        """Return the index of the player whose turn it is (0 or 1)."""
        ...
```

### 3.2 Action Interface

Actions must carry semantic tags. This is the bridge between generic agents and game-specific
knowledge - without tags, the generic rule library in Repo 2 cannot function.

```python
@dataclass(frozen=True)
class Action:
    action_type: str          # e.g. "keep_die", "activate_god_power", "reroll"
    payload: dict             # game-specific parameters
    tags: frozenset[str]      # semantic labels (see Section 3.3)
```

### 3.3 Canonical Action Tags

These tags MUST be used consistently. Repo 2's generic rules depend on them.
Game developers adding a new game should map their actions to these tags.

| Tag | Meaning |
|-----|---------|
| `"offensive"` | Action primarily deals damage or worsens opponent state |
| `"defensive"` | Action primarily blocks damage or improves own survivability |
| `"healing"` | Action restores HP |
| `"economy"` | Action generates or manipulates resources (tokens, mana, etc.) |
| `"information"` | Action reveals hidden state |
| `"disruption"` | Action interferes with opponent's plan without direct damage |
| `"risky"` | Action has significant variance or self-damage |
| `"terminal"` | Action ends the game or a major phase |

Multiple tags per action are allowed and expected. Example: Surtr's Flame is `{"offensive", "risky"}`.

### 3.4 GameState Interface

GameState does not need to be standardized beyond being immutable. However, it MUST expose
these normalized fields so generic rules can operate without game-specific knowledge:

```python
# These properties must exist on every GameState implementation
state.hp_ratio: float          # current_hp / max_hp for active player (0.0 - 1.0)
state.opponent_hp_ratio: float # same for opponent
state.resource_ratio: float    # current_resources / some_max for active player
state.round_ratio: float       # current_round / expected_max_rounds (0.0 - 1.0)
state.is_terminal: bool        # True if game is over
state.winner: Optional[int]    # 0 or 1 if terminal, else None
```

---

## 4. Agent Framework Design (Repo 2)

### 4.1 GreedyAgent - inject the evaluator

```python
class StateEvaluator(ABC):
    @abstractmethod
    def score(self, state: GameState, action: Action) -> float:
        """Score how good an action is from the current state."""
        ...

class GreedyAgent:
    def __init__(self, evaluator: StateEvaluator):
        self.evaluator = evaluator

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        return max(legal_actions, key=lambda a: self.evaluator.score(state, a))
```

Fjöld ships a `FjoldEvaluator`. Game 2 ships a `Game2Evaluator`. The agent is shared.

### 4.2 ArchetypeAgent - inject rules

```python
class Rule(ABC):
    @abstractmethod
    def apply(self, state: GameState, legal_actions: list[Action]) -> Optional[Action]:
        """Return an action if this rule fires, else None."""
        ...

class ArchetypeAgent:
    def __init__(self, rules: list[Rule], fallback: Agent = None):
        self.rules = rules  # evaluated in priority order
        self.fallback = fallback or RandomAgent()

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        for rule in self.rules:
            action = rule.apply(state, legal_actions)
            if action is not None:
                return action
        return self.fallback.choose_action(state, legal_actions)
```

### 4.3 Generic Rule Library (ships with Repo 2)

These rules operate only on normalized GameState fields and action tags.
Any game that satisfies the interface gets these for free.

```python
class LowHealthDefenseRule(Rule):
    """When HP is below threshold, prefer defensive actions."""
    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    def apply(self, state, legal_actions):
        if state.hp_ratio < self.threshold:
            defensive = [a for a in legal_actions if "defensive" in a.tags]
            return random.choice(defensive) if defensive else None

class WinningAggressionRule(Rule):
    """When ahead by threshold, prefer offensive actions."""
    def __init__(self, lead_threshold: float = 0.25):
        self.threshold = lead_threshold

    def apply(self, state, legal_actions):
        lead = state.opponent_hp_ratio - state.hp_ratio
        if lead > self.threshold:
            offensive = [a for a in legal_actions if "offensive" in a.tags]
            return random.choice(offensive) if offensive else None

class ResourceSpendRule(Rule):
    """When resources are high, prefer actions that spend them."""
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold

    def apply(self, state, legal_actions):
        if state.resource_ratio > self.threshold:
            economy = [a for a in legal_actions if "economy" in a.tags]
            return random.choice(economy) if economy else None

class LateGameTerminalRule(Rule):
    """In late game, prefer terminal/decisive actions."""
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    def apply(self, state, legal_actions):
        if state.round_ratio > self.threshold:
            terminal = [a for a in legal_actions if "terminal" in a.tags]
            return random.choice(terminal) if terminal else None
```

Fjöld's Archetype agents are composed from these generic rules + Fjöld-specific rules.
The ratio of generic:specific rules is a measure of how well the interface was designed.

---

## 5. Balance Toolkit Design (Repo 3)

### 5.1 Core Optuna Loop

```python
class BalanceOptimizer:
    def __init__(self, env_factory, agent_factory, metric_targets: dict):
        self.env_factory = env_factory    # callable -> GameEnvironment
        self.agent_factory = agent_factory # callable(params) -> (Agent, Agent)
        self.targets = metric_targets

    def optimize(self, param_space: dict, n_trials: int = 200):
        study = optuna.create_study(direction="minimize")
        study.optimize(self._objective, n_trials=n_trials)
        return study.best_params

    def _objective(self, trial):
        params = {k: trial.suggest_*(k, **v) for k, v in self.param_space.items()}
        results = self._run_simulation(params)
        return self._violation_score(results)

    def _violation_score(self, results) -> float:
        """Sum of squared deviations from target metrics. 0.0 = perfect balance."""
        score = 0.0
        for metric, target in self.targets.items():
            actual = results[metric]
            score += max(0, actual - target["max"]) ** 2
            score += max(0, target["min"] - actual) ** 2
        return score
```

### 5.2 When to Use the Balance Optimizer

Do NOT reach for Optuna for single-parameter changes. Use it when:
- Introducing a new archetype (dice + GP + runes + conditions simultaneously)
- A cross-layer regression makes multiple metrics go red
- 5+ interdependent parameters need tuning
- Manual iteration has failed after 3+ attempts

For single God Power tuning: change numbers manually, re-run simulator, check results.

---

## 6. Simulator Design Decisions Driven by This Plan

These are decisions the Fjöld simulator must make NOW to enable future reusability.
**Flag any of these to the developer when they arise during simulator development.**

| Decision | What to do | Why |
|----------|-----------|-----|
| Environment class | Implement `GameEnvironment` ABC from Section 3.1 | Repo 2 depends on this interface |
| Action dataclass | Add `tags: frozenset[str]` field to every Action | Repo 2 generic rules depend on tags |
| GameState fields | Expose `hp_ratio`, `opponent_hp_ratio`, `resource_ratio`, `round_ratio` | Generic rules need normalized fields |
| Reward signal | `step()` returns reward from active player's perspective | Standard for Gymnasium; needed for MCTS |
| Package structure | Make simulator importable as a package (`import fjold`) | Repo 2 needs to import it as a dependency |
| Action constructors | Every action factory must assign tags at construction time | Tags must be consistent, not ad-hoc |

---

## 7. What NOT to Over-Engineer Now

The interface contract in Section 3 should be implemented as Fjöld is built - not upfront as
an abstract framework. The abstractions will be extracted into Repo 2 once Fjöld's simulator
is working. Premature abstraction here will slow down the 5-month launch timeline.

**Order of operations:**
1. Build Fjöld simulator with the interface contract in mind (this repo).
2. Extract generic agent framework into Repo 2 once Greedy + Archetype agents are working.
3. Build Repo 3 balance toolkit once L3+ simulation is producing meaningful results.

---

*Last updated: April 15, 2026.*
*Read alongside CLAUDE.md. CLAUDE.md governs game design decisions; this file governs toolkit architecture.*
