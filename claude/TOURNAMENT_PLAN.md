# TOURNAMENT_PLAN.md - Intra-Archetype Tournament Plan

> **Purpose:** Empirically validate and lock canonical loadouts for all 4 archetypes
> before proceeding to L3 (dice pool testing). This replaces hand-picked loadouts
> with tournament-proven ones.
>
> Seed this document into a new conversation to continue implementation.

---

## Why This Exists

Current canonical loadouts in `simulator/simulator.py` (`_ARCHETYPES` dict) were
hand-picked by design reasoning, not empirically validated. The intra-tournament:

1. Finds the strongest variant of each archetype strategy
2. Cross-validates that the winner still satisfies the target win-rate matrix
3. Iterates until all four canonical loadouts reach Nash equilibrium

---

## Key Data Insights (from actual JSON)

**Most token-efficient damage GP:** Tyr T1 - 4 tokens, 2 dmg + block 1 (2.0 tok/dmg).
Beats Surtr T2 on net basis once self-damage is counted. Currently unused in Aggro.

**Cheapest HP recovery:** Eir T1 - 3 tokens, heal 2. Most efficient GP in the pool.

**Freyja is NOT an economy GP.** It is a token sink: T1 = spend 4, get 3 back + heal 1.
Net: -1 token + 1 heal per activation. It converts tokens into healing, not tokens into tokens.

**Jotun is the only die combining heavy axes + heavy tokens.**
Faces: 2 axe, 0 arrow, 1 helmet, 0 shield, 1 hand, 2 bordered. Self-funds offensive GPs
without sacrificing attack dice. Unique in the pool.

**Skald has 2 bordered hands + balanced combat + no plain hand.** Different from Miser
(pure economy, no offense) and Jotun (axe-heavy). The best "active economy" die.

**Frigg T3 vs Mjolnir T3:** If Economy fires Mjolnir T3 (16 tokens), Frigg T3 (12 tokens)
steals all 16. Net swing: Economy loses 16, Control gains 16. Single-round game-winner.

**Vidar is dead against non-GP opponents.** Only valuable if opponent fires an offensive GP.
High ceiling, zero floor.

---

## Die Face Reference

| Die | Axe | Arrow | Helmet | Shield | Hand | Bordered |
|-----|-----|-------|--------|--------|------|----------|
| DIE_WARRIOR | 1 | 1 | 1 | 1 | 1 | 1 |
| DIE_BERSERKER | 2 | 1 | 0 | 1 | 1 | 1 |
| DIE_HUNTER | 0 | 2 | 1 | 0 | 2 | 1 |
| DIE_WARDEN | 0 | 0 | 2 | 2 | 1 | 1 |
| DIE_MISER | 0 | 1 | 1 | 1 | 1 | 2 |
| DIE_GAMBLER | 2 | 2 | 0 | 0 | 1 | 1 |
| DIE_SKALD | 1 | 1 | 1 | 1 | 0 | 2 |
| DIE_JOTUN | 2 | 0 | 1 | 0 | 1 | 2 |

---

## The 24 Variants

### AGGRO (goal: end game by round 5-6 via front-loaded damage)

**A1 - "Berserker Blitz"** (current canonical, baseline)
- Dice: 4x DIE_BERSERKER + 2x DIE_GAMBLER
- GPs: GP_SURTRS_FLAME, GP_FENRIRS_BITE, GP_HEIMDALLRS_WATCH
- Keep: FACE_AXE, FACE_ARROW, FACE_HAND_BORDERED
- Fire: Surtr first (cheapest burst), Fenrir for bleed, Heimdallr when opponent has helmets

**A2 - "Tyr Rush"** (cheapest damage spam)
- Dice: 4x DIE_BERSERKER + 2x DIE_WARRIOR
- GPs: GP_TYRS_JUDGMENT, GP_SURTRS_FLAME, GP_FENRIRS_BITE
- Keep: FACE_AXE, FACE_ARROW, FACE_HAND_BORDERED
- Fire: Tyr T1 every round (4 tokens, 2 dmg + 1 block). Cheapest damage in game.
- Question: does Tyr's 2.0 tok/dmg efficiency beat the current GP set?

**A3 - "Jotun Bleed"** (self-funding DoT aggro)
- Dice: 4x DIE_JOTUN + 2x DIE_BERSERKER
- GPs: GP_FENRIRS_BITE, GP_SURTRS_FLAME, GP_HEIMDALLRS_WATCH
- Keep: FACE_AXE, FACE_HAND_BORDERED
- Fire: Fenrir T1 round 1, Fenrir T2 round 3 (stack bleed). Jotun's 2 bordered fund Fenrir without sacrificing axes.
- Question: does Jotun self-funding make repeated Fenrir viable in Aggro?

**A4 - "Glass Cannon"** (maximum offense, zero defense)
- Dice: 6x DIE_GAMBLER
- GPs: GP_SURTRS_FLAME, GP_TYRS_JUDGMENT, GP_LOKIS_GAMBIT
- Keep: FACE_AXE, FACE_ARROW, FACE_HAND_BORDERED
- Fire: cheapest affordable GP every round
- Question: does total offense saturation (Gambler has zero defense) beat blended approach?

**A5 - "Unblockable Archer"** (Skadi + Heimdallr on same round)
- Dice: 4x DIE_GAMBLER + 2x DIE_HUNTER
- GPs: GP_SKADIS_VOLLEY, GP_HEIMDALLRS_WATCH, GP_SURTRS_FLAME
- Keep: FACE_ARROW, FACE_HAND_BORDERED
- Fire: Heimdallr + Skadi same round when 3+ arrows showing (Heimdallr makes arrows unblockable, Skadi multiplies them)
- Question: is combined Skadi + Heimdallr activation a better Aggro win condition than raw axes?

**A6 - "Loki Finisher"** (variance burst at kill threshold)
- Dice: 4x DIE_BERSERKER + 2x DIE_GAMBLER
- GPs: GP_LOKIS_GAMBIT, GP_SURTRS_FLAME, GP_FENRIRS_BITE
- Keep: FACE_AXE, FACE_ARROW, FACE_HAND_BORDERED
- Fire: Surtr early, Fenrir for bleed, save tokens for Loki T2/T3 when opponent at 4-6 HP
- Question: does holding for variance burst outperform consistent damage?

---

### CONTROL (goal: survive to round 8+, outlast)

**C1 - "Reflect Trap"** (current canonical, baseline)
- Dice: 3x DIE_WARDEN + 2x DIE_WARRIOR + 1x DIE_SKALD
- GPs: GP_AEGIS_OF_BALDR, GP_EIRS_MERCY, GP_VIDARS_REFLECTION
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED, FACE_AXE, FACE_ARROW
- Fire: Aegis vs dice damage, Eir when hurt, Vidar when opponent has 8+ tokens

**C2 - "Pure Wall"** (Tyr as sole kill condition)
- Dice: 4x DIE_WARDEN + 2x DIE_SKALD
- GPs: GP_AEGIS_OF_BALDR, GP_EIRS_MERCY, GP_TYRS_JUDGMENT
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED
- Fire: Eir T1 (3 tokens) consistently for low-cost healing, Aegis vs big damage, Tyr for kill pressure
- Question: does stripping all offense from dice and using Tyr as the only kill condition outlast blended?

**C3 - "Frigg Fortress"** (disruption Control)
- Dice: 4x DIE_WARDEN + 2x DIE_MISER
- GPs: GP_AEGIS_OF_BALDR, GP_EIRS_MERCY, GP_FRIGGS_VEIL
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED
- Fire: Frigg T3 when opponent has 12+ tokens (steal Mjolnir T3's 16 tokens). Miser funds Frigg T3 (12 tokens).
- Question: does reactive disruption (Frigg steal) outperform proactive defense (Vidar/Tyr)?

**C4 - "Hel's Wall"** (anti-bleed specialist)
- Dice: 4x DIE_WARDEN + 2x DIE_WARRIOR
- GPs: GP_AEGIS_OF_BALDR, GP_EIRS_MERCY, GP_HELS_PURGE
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED
- Fire: Hel's Purge T2 immediately vs any Fenrir stacks. Eir for general sustain. Aegis vs burst.
- Question: hard counter to bleed-heavy Aggro. What's the cost in non-bleed matchups?

**C5 - "Offensive Control"** (Jotun-based kill pressure)
- Dice: 3x DIE_WARDEN + 3x DIE_JOTUN
- GPs: GP_TYRS_JUDGMENT, GP_AEGIS_OF_BALDR, GP_EIRS_MERCY
- Keep: FACE_HELMET, FACE_AXE, FACE_HAND_BORDERED
- Fire: Tyr every round (Jotun's 2 bordered fund it). Jotun provides axes so Tyr's damage is supplemented by dice.
- Question: does maintaining dice threat + Tyr create enough kill pressure to shorten games without losing survivability?

**C6 - "Sustain Engine"** (Freyja + Eir alternating)
- Dice: 3x DIE_WARDEN + 2x DIE_SKALD + 1x DIE_MISER
- GPs: GP_EIRS_MERCY, GP_AEGIS_OF_BALDR, GP_FREYAS_BLESSING
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED
- Fire: alternate Freyja T1 and Eir T1 each round (Skald + Miser fund both). Freyja = -1 token + 1 heal per round. Eir T1 = -3 tokens + 2 heal. Consistent low-cost healing every round.
- Question: does distributed small healing across all rounds beat reactive large heals?

---

### ECONOMY (goal: hoard tokens, fire Mjolnir T3 for 6 dmg as single overwhelming burst)

**E1 - "Standard Hoard"** (current canonical, baseline)
- Dice: 3x DIE_MISER + 2x DIE_WARRIOR + 1x DIE_WARDEN
- GPs: GP_MJOLNIRS_WRATH, GP_FREYAS_BLESSING, GP_FRIGGS_VEIL
- Keep: FACE_HAND_BORDERED, FACE_HAND, FACE_ARROW, FACE_HELMET, FACE_SHIELD (no axes)
- Fire threshold: Mjolnir T1 at 6 tokens. Freyja when tokens >= 6. Frigg when flush at 9+.

**E2 - "Token Thief"** (aggressive theft-based Economy)
- Dice: 3x DIE_MISER + 3x DIE_HUNTER
- GPs: GP_MJOLNIRS_WRATH, GP_FREYAS_BLESSING, GP_FRIGGS_VEIL
- Keep: FACE_HAND_BORDERED, FACE_HAND, FACE_ARROW
- Hunter: 2 plain hands + 2 arrows/die. Combined with Miser's 2 bordered: generates AND steals tokens.
- Question: does aggressive theft snowball faster than passive Miser generation, especially in mirror?

**E3 - "Skald Hoard"** (combat-active Economy)
- Dice: 4x DIE_SKALD + 2x DIE_MISER
- GPs: GP_MJOLNIRS_WRATH, GP_FREYAS_BLESSING, GP_FRIGGS_VEIL
- Keep: FACE_HAND_BORDERED, FACE_AXE, FACE_ARROW, FACE_HELMET, FACE_SHIELD
- Skald: 2 bordered + balanced combat. Forces opponent to defend while you hoard.
- 4x Skald + 2x Miser = up to 12 bordered hand faces in pool.
- Question: does active dice threat while building tokens beat passive Miser hoarding?

**E4 - "Defensive Economy"** (survive to T3, no acceleration)
- Dice: 3x DIE_MISER + 2x DIE_WARDEN + 1x DIE_WARRIOR
- GPs: GP_MJOLNIRS_WRATH, GP_AEGIS_OF_BALDR, GP_EIRS_MERCY
- Keep: FACE_HAND_BORDERED, FACE_HELMET, FACE_SHIELD
- Swaps Freyja + Frigg for Aegis + Eir. Raw survival to reach Mjolnir T3, no disruption.
- Question: does survivability beat token acceleration when the only goal is reaching T3?

**E5 - "Jotun Bankroll"** (two-threat Economy)
- Dice: 3x DIE_JOTUN + 2x DIE_MISER + 1x DIE_WARRIOR
- GPs: GP_MJOLNIRS_WRATH, GP_FENRIRS_BITE, GP_FREYAS_BLESSING
- Keep: FACE_AXE, FACE_HAND_BORDERED
- Jotun: 2 axes + 2 bordered. Applies melee pressure while building tokens. Fenrir as backup win condition if Mjolnir gets Aegis-blocked.
- Question: does forcing opponent to defend two threats (dice + Mjolnir) beat single-threat Economy?

**E6 - "Frigg Trap"** (token denial primary strategy)
- Dice: 3x DIE_MISER + 2x DIE_HUNTER + 1x DIE_WARDEN
- GPs: GP_MJOLNIRS_WRATH, GP_FRIGGS_VEIL, GP_NJORDS_TIDE
- Keep: FACE_HAND_BORDERED, FACE_HAND
- Build faster than opponent. Frigg T3 when they activate: steal their tokens. Njordr rerolls to fish for hand dice.
- Question: is token denial as primary win condition (not just counter) viable?

---

### COMBO (goal: build specific board state for conditional high-value payoff)

**Co1 - "Arrow Volley"** (current canonical, baseline)
- Dice: 4x DIE_HUNTER + 2x DIE_GAMBLER
- GPs: GP_SKADIS_VOLLEY, GP_NJORDS_TIDE, GP_ODINS_INSIGHT
- Keep: FACE_ARROW, FACE_HAND_BORDERED, FACE_AXE
- Fire: Skadi when 2+ unblocked arrows. Njordr post-combat to reroll for more hands. Odin T3 only.

**Co2 - "Unblockable Axes"** (Heimdallr melee combo)
- Dice: 4x DIE_JOTUN + 2x DIE_BERSERKER
- GPs: GP_HEIMDALLRS_WATCH, GP_FENRIRS_BITE, GP_SURTRS_FLAME
- Keep: FACE_AXE, FACE_HAND_BORDERED
- Fire: Heimdallr when 3+ axes showing (T3 = all attacks unblockable). Jotun's 2 bordered fund Heimdallr each round.
- Distinct from Aggro: holds tokens until axis count is right, fires conditionally.
- Question: does conditional unblockable timing beat Aggro's fire-immediately approach?

**Co3 - "Reflect Bait"** (Vidar reactive trap)
- Dice: 3x DIE_WARDEN + 2x DIE_SKALD + 1x DIE_MISER
- GPs: GP_VIDARS_REFLECTION, GP_AEGIS_OF_BALDR, GP_EIRS_MERCY
- Keep: FACE_HELMET, FACE_SHIELD, FACE_HAND_BORDERED
- Fire: Aegis early. Hold Vidar T3 (12 tokens) until opponent commits a high-tier GP. Vidar T3 vs Mjolnir T3 = 7 reflected dmg.
- Question: does a one-shot reflect trap outperform proactive Control?

**Co4 - "Bleed Stack"** (Fenrir accumulator)
- Dice: 3x DIE_JOTUN + 2x DIE_MISER + 1x DIE_WARRIOR
- GPs: GP_FENRIRS_BITE, GP_FREYAS_BLESSING, GP_SURTRS_FLAME
- Keep: FACE_HAND_BORDERED, FACE_AXE
- Fire: Fenrir T2 round 2 (9 tokens, 4 dmg + 2 bleed), Fenrir T2 again round 4. Two activations = 4 bleed stacks = 4 passive dmg/round. Freyja accelerates token building.
- Question: is compounding bleed a distinct win condition from burst damage?

**Co5 - "Arrow + Bleed"** (dual-threat ranged)
- Dice: 4x DIE_HUNTER + 2x DIE_WARRIOR
- GPs: GP_SKADIS_VOLLEY, GP_FENRIRS_BITE, GP_NJORDS_TIDE
- Keep: FACE_ARROW, FACE_HAND_BORDERED, FACE_HAND
- Fire: Skadi when 2+ unblocked arrows, Fenrir when 9+ tokens. Hunter's 2 plain hands fund both conditions.
- Two independent payoffs - opponent can't defend both simultaneously.
- Question: does dual condition (burst + bleed) create harder-to-counter Combo than single condition?

**Co6 - "Odin Burst"** (information-adaptive)
- Dice: 3x DIE_HUNTER + 2x DIE_GAMBLER + 1x DIE_WARRIOR
- GPs: GP_ODINS_INSIGHT, GP_SKADIS_VOLLEY, GP_HEIMDALLRS_WATCH
- Keep: FACE_ARROW, FACE_HAND_BORDERED, FACE_AXE
- Fire: Odin T2 to see opponent's kept dice. Then choose: Skadi if opponent has few shields, Heimdallr if opponent has many helmets. Adaptive every round.
- Question: does information-based GP selection outperform fixed priority order?

---

## Implementation Plan

### Step 1: Parameterize agents (~2 hours)

Each agent needs to accept parameters instead of hardcoded constants:

```python
class AggroAgent(Agent):
    def __init__(self, keep_faces=None, gp_priority=None, tier_order=None, rng=None):
        self.keep_faces = keep_faces or frozenset({...defaults...})
        self.gp_priority = gp_priority or (...defaults...)
        self.tier_order = tier_order or (2, 1, 0)

class ControlAgent(Agent):
    def __init__(self, keep_faces=None, gp_priority=None, hp_heal_threshold=8,
                 tier_order=None, rng=None): ...

class EconomyAgent(Agent):
    def __init__(self, keep_faces=None, gp_priority=None, mjolnir_threshold=6,
                 freyja_threshold=6, rng=None): ...

class ComboAgent(Agent):
    def __init__(self, keep_faces=None, gp_priority=None, skadi_arrow_threshold=2,
                 tier_order=None, rng=None): ...
```

### Step 2: Define variant configs (~1 hour)

Add `ArchetypeVariant` dataclass to `simulator.py` (extends or replaces `ArchetypeConfig`):

```python
@dataclass
class ArchetypeVariant:
    name: str           # e.g. "A1_berserker_blitz"
    archetype: str      # "AGGRO", "CONTROL", "ECONOMY", "COMBO"
    agent_cls: type
    agent_kwargs: dict  # passed to agent __init__
    dice_loadout: list[str]
    gp_loadout: tuple[str, ...]
```

### Step 3: Intra-tournament runner (~2 hours)

New function `run_intra_tournament(variants, n_games=1000, seed=42)`:
- Runs all NxN pairs within an archetype
- Returns ranked results by average win rate
- Same infrastructure as `run_l2_simulation` - just variant configs instead of archetype configs

### Step 4: Cross-archetype validation

After each intra-tournament, take the top variant and run it in the 4x4 matrix against
the current canonical loadouts of the other 3 archetypes. Check against target matrix.

---

## Process: Finding Nash Equilibrium

```
Round 1: Run all 4 intra-tournaments independently
         -> 4 winning variants
Round 2: Run 4x4 cross-archetype matrix with the 4 winners
         -> Check target win rates
Round 3: If any matchup is RED, run the losing archetype's intra-tournament
         again with the stronger opponent as the fixed benchmark
         -> Repeat until cross-archetype matrix is stable
```

A set of 4 canonical loadouts is locked when no single archetype can improve its
cross-archetype win rate by switching to a different variant.

---

## When Balance Breaks

If a variant wins the internal tournament but breaks cross-archetype targets:

| Outcome | Action |
|---------|--------|
| Winner too strong vs one archetype | Run that archetype's intra-tournament with the winner as fixed opponent |
| Winner too strong vs all archetypes | Retune GP numbers (cost or effect), re-run intra-tournament |
| No variant satisfies cross-archetype targets | Mechanic has structural problem - design change required (not a number fix) |

Never accept a red cross-archetype metric. Constitution C18: if a metric goes red,
change the number or cut the feature. Never ship "we'll see."

---

## Files to Create/Modify

```
simulator/
  agents/
    aggro_agent.py      - parameterize (keep_faces, gp_priority, tier_order)
    control_agent.py    - parameterize (keep_faces, gp_priority, hp_heal_threshold, tier_order)
    economy_agent.py    - parameterize (keep_faces, gp_priority, mjolnir_threshold, freyja_threshold)
    combo_agent.py      - parameterize (keep_faces, gp_priority, skadi_arrow_threshold, tier_order)
  simulator.py          - add ArchetypeVariant, run_intra_tournament, print_intra_results
```

No new files required. No changes to game_engine.py, game_state.py, or data files.

---

*Created: 2026-04-17. Continuation of L2 balance work. Next step: implement Step 1 (parameterize agents).*
