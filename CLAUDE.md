# CLAUDE.md — Fjöld Project Brief

> **This file is the single source of truth for AI-assisted development on this project.**
> It captures every design decision, rule, and constraint agreed upon during the design phase.
> Claude Code should treat this as authoritative context for all tasks.
> The master spreadsheet (`/data/Fjold_Master_Design_v1.0.xlsx`) contains the exact numbers;
> this file provides the reasoning, architecture, and development methodology.

---

## 1. Project Overview

**Fjöld** (Old Norse for "multitude/many") is a mobile dice-dueling game inspired by Orlog
from Assassin's Creed Valhalla. It is a **spiritual successor**, not a clone — original art,
original names, original God Powers, Norse mythology theme, no AC Valhalla IP.

### Why This Game Exists

- The Orlog physical board game Kickstarter raised **CA$1.1M from 12,409 backers in 35 minutes**.
- Reviewers said the physical version works **better as a digital game** (tiny unreadable tokens, complex tracking).
- **No standalone digital Orlog app exists** on any platform.
- The core mechanic (dice combat + God Powers + token economy) is proven fun for 3-5 minute mobile sessions.

### What We're Building

A F2P mobile dice dueling game with:
- **Hybrid PvE → PvP** game mode (PvE campaign onboards players; PvP endgame retains them).
- **Roguelike PvE campaign** ("Realms of Yggdrasil") structured like Slay the Spire.
- **Async PvP** (take your turn, opponent gets a push notification).
- **Cosmetics + battle pass monetization** — no pay-to-win, ever.

### Team

- **3 developers**, nights and weekends (~15 hours/person/week, ~45 combined hours/week).
- **Target timeline:** < 5 months to iOS soft launch.

---

## 2. Legal Constraints

- **Game mechanics cannot be copyrighted** (U.S. Copyright Office, American Bar Association confirm).
- What IS copyrightable: names, art, characters, code, music.
- **Never use:** the name "Orlog", any AC Valhalla assets, character names from AC, direct visual references.
- **Safe to use:** the core dice-combat mechanic, token economy, God Power activation system — all genericized.
- "Orlog" is Old Norse for "fate" and is not trademarked by Ubisoft, but avoid it anyway to prevent confusion.
- Ubisoft filed an infringement lawsuit in March 2025 — they actively enforce IP. Stay clean.
- **Conduct a trademark search** on the final game name before committing.

---

## 3. Tech Stack (Decided)

| Layer | Technology | Why |
|-------|-----------|-----|
| **Game Engine** | Unity (2022 LTS+) | ~70% of top mobile games, mature mobile optimization, built-in IAP/Ads/Analytics, massive Asset Store, free until $200K revenue. |
| **Language (Client)** | C# | Unity's native language. GameCore logic is pure C# with no Unity dependencies. |
| **Language (Simulator)** | Python 3.11+ | NumPy/Pandas/Matplotlib for analysis, Jupyter notebooks for iteration, 10,000 games/min achievable. |
| **Backend** | Firebase | Firestore (game state), Cloud Functions (server-authoritative dice rolls), Auth (anonymous → linked), Cloud Messaging (push notifications), Remote Config (live balance tuning). Free tier handles 50K DAU. |
| **Multiplayer** | Async (Firebase) | Dramatically simpler than real-time. Store game state in Firestore, push notifications for "your turn." Real-time PvP deferred to v2. |
| **Version Control** | GitHub | Free private repos. Use Git LFS for Unity assets. |
| **Art (Prototype)** | Midjourney/Stable Diffusion | AI-generated Norse art for soft launch. Commission real art post-validation. |
| **UI Design** | Figma | Mood boards, UI mockups, shared design system. |
| **Platform** | iOS first, Android 3-6 months later | iOS users spend 45% more, fewer fragmentation issues, faster QA for small team. Unity same codebase for both. |

### Key Technical Decisions

- **Server-authoritative dice rolls** in all PvP modes. Client never generates random numbers for multiplayer. Firebase Cloud Functions handle all RNG. This is the primary anti-cheat measure.
- **Anonymous authentication first.** Players start playing instantly. Link to Apple ID/Google later. Removes sign-up drop-off.
- **GameCore is engine-agnostic.** Pure C# logic with no MonoBehaviour dependencies. Same code runs headless (simulation/server) or with UI (Unity client). Pattern: `GameState + Action → GameRules.apply() → (NewGameState, [Events])`.
- **Pseudo-Random Distribution (PRD)** for all probability-based effects. Never pure random. Dota 2's proven approach: stated probability is the long-run average, but actual per-trial probability starts low and increases until proc, then resets. Eliminates frustrating droughts.
- **Remote Config for live balance tuning.** God Power costs, Rune effects, Condition parameters can be changed server-side without an app update. Critical for post-launch balancing.

---

## 4. The Constitution (20 Inviolable Rules)

These rules exist because violating them historically breaks dueling games.
**All 3 devs must sign off to amend any of these.**

### Balance Rules

- **C01:** No single strategy may have >55% win rate against the field.
- **C02:** Every archetype must win >60% vs. at least one other AND win <40% vs. at least one other. (Enforces rock-paper-scissors.)
- **C03:** Direct damage must cost at least 2.5 tokens per point of damage at efficient tiers. (Prevents "Thor's Strike" dominance.)
- **C04:** Every die type must sum to the same Power Budget (6.0 ± 0.2). Dice are sidegrades, not upgrades.
- **C05:** Every Rune must have a genuine downside or conditional cost. No pure-upside runes.
- **C06:** No God Power may appear in >60% or <10% of simulated victories.
- **C07:** No Battlefield Condition may shift any archetype's win rate by more than 10 percentage points.
- **C08:** Average match length must be 5–8 rounds.

### Monetization Rules

- **C09:** Nothing that affects gameplay may be sold for cash. Only cosmetics and convenience.
- **C10:** Every cosmetic must also be earnable through free play, even if slowly.

### Fairness Rules

- **C11:** Ranked PvP uses standardized loadout pool. Skill tree effects do not apply.
- **C12:** All randomness visible to the client must be server-authoritative in multiplayer.
- **C13:** Probability-based effects use PRD, not pure random.

### UX Rules

- **C14:** Concede is always free and available. No time-gating or XP penalty.
- **C15:** Every God Power, Rune, and Condition must be explainable in ≤20 words on the card itself.
- **C16:** A player who has never opened a patch note should never be surprised by an interaction. Tooltip everything.

### Process Rules

- **C17:** No balance number ships without having run through the Python simulator first.
- **C18:** If a simulated metric goes red, either the number changes or the feature is cut — never shipped "we'll see."
- **C19:** Core content added quarterly, seasonal conditions monthly, cosmetics weekly.
- **C20:** No mechanic is shipped without at least one hard counter in the same content bundle.

---

## 5. Core Game Mechanics

### Match Parameters

| Parameter | Value |
|-----------|-------|
| Starting Health Stones | 15 per player |
| Starting Tokens | 0 (modified by Runes/Skill Tree) |
| Dice per player | 6 (selected from owned pool, duplicates allowed) |
| Rolls per round | 3 (initial + 2 rerolls) |
| God Powers per loadout | 3 (chosen before match) |
| Runes per loadout | 3 (passive effects, slots unlock at account level 1, 5, 15) |
| Battlefield Conditions | 1 known at start + 1 revealed at round 3 |
| Comeback: Fury Tokens | +1 per round when behind ≥4 HP; 1 Fury = 2 regular tokens for God Power activation only |

### Round Structure (11 Phases)

```
1. REVEAL      → Battlefield Conditions check. Round 1: reveal primary. Round 3: reveal secondary. Fury check.
2. ROLL        → Both players roll 6 loadout dice simultaneously. PRD-adjusted by runes/skill tree.
3. KEEP_1      → Players simultaneously select dice to keep. Unkept dice will be rerolled.
4. REROLL_1    → Unkept dice rerolled.
5. KEEP_2      → Players select additional dice to keep.
6. REROLL_2    → Final reroll. All dice are now final.
7. GOD_POWER   → Both secretly choose 0 or 1 God Power and tier (if affordable).
8. COMBAT      → Attack dice resolve vs. defense dice (axes vs helmets, arrows vs shields).
9. GOD_RESOLVE → God Powers activate in priority order. Tokens deducted.
10. TOKENS     → Bordered Hands generate tokens. Plain Hands steal from opponent. Rune triggers fire.
11. END_CHECK  → Win condition check. If nobody at 0 HP, increment round → Phase 1.
```

### Resolution Order (strict precedence within Phase 8-10)

```
1. Battlefield Conditions apply passive modifiers.
2. Pre-combat Rune triggers fire.
3. Combat resolves: axes vs helmets, arrows vs shields. Blocked attacks deal 0.
4. Defensive God Powers activate (Aegis, Vidar, Frigg).
5. Offensive God Powers activate (Mjölnir, Fenrir, Skaði, Surtr, Loki).
6. Healing God Powers activate (Eir's Mercy).
7. Token generation: bordered Hand dice produce tokens.
8. Token theft: unmatched Hand dice steal tokens from opponent.
9. Post-combat Rune triggers fire.
10. Fury Token generation: if behind ≥4 HP, gain 1 Fury Token.
```

### Die Face Types

| Face | Symbol | Effect | Power Value |
|------|--------|--------|-------------|
| Axe | 🪓 | Deal 1 melee damage. Blocked by Helmet. | 1.0 |
| Arrow | 🏹 | Deal 1 ranged damage. Blocked by Shield. | 1.0 |
| Helmet | ⛑️ | Block 1 Axe. | 1.0 |
| Shield | 🛡️ | Block 1 Arrow. | 1.0 |
| Tithing Hand | ✋ | Steal 1 token from opponent (if they have any). | 0.8 |
| Gilded Hand (bordered) | 🤲 | Generate 1 token + steal 1 if able. | 1.2 |
| Wild (skill tree) | ✴️ | Resolves as Axe OR Arrow (player chooses). | 1.4 |
| Runic (skill tree) | 🔆 | Generate 2 tokens. No combat value. | 1.3 |

### Power Budget Formula

Every die has 6 faces. The sum of face power values must equal **6.0 ± 0.2**.
This is Constitution C04 — enforced by formula in the spreadsheet, validated by the simulator.

```
Power Budget = (Axes × 1.0) + (Arrows × 1.0) + (Helmets × 1.0) + (Shields × 1.0) + (Hands × 0.8) + (Bordered × 1.2)
```

### The 8 Launch Dice

| Die ID | Name | Axe | Arrow | Helmet | Shield | Hand | Bordered | Budget | Role |
|--------|------|-----|-------|--------|--------|------|----------|--------|------|
| DIE_WARRIOR | Huskarl's Die | 1 | 1 | 1 | 1 | 1 | 1 | 6.0 | Balanced baseline (starter) |
| DIE_BERSERKER | Berserkr's Die | 2 | 1 | 0 | 1 | 1 | 1 | 6.0 | Melee aggression |
| DIE_HUNTER | Skjaldmær's Die | 0 | 2 | 1 | 0 | 2 | 1 | 5.8 | Ranged + token theft |
| DIE_WARDEN | Stoðvar's Die | 0 | 0 | 2 | 2 | 1 | 1 | 6.0 | Pure defense |
| DIE_MISER | Gullgjafi's Die | 0 | 1 | 1 | 1 | 1 | 2 | 6.2 | Token economy engine |
| DIE_GAMBLER | Lokason's Die | 2 | 2 | 0 | 0 | 1 | 1 | 6.0 | All offense, no defense |
| DIE_SKALD | Skald's Die | 1 | 1 | 1 | 1 | 0 | 2 | 6.4 | Attrition / balanced hybrid |
| DIE_JOTUN | Jötunn's Die | 2 | 0 | 1 | 0 | 1 | 2 | 6.2 | Heavy hitter with openings |

---

## 6. God Powers (16 Launch)

**Categories:** 5 Offense, 5 Defense, 3 Utility, 3 Hybrid.
Each has 3 tiers with escalating cost and effect.
See `/data/god_powers.json` for exact numbers.

### Offensive

| ID | Name | T1 Cost/Effect | T2 Cost/Effect | T3 Cost/Effect |
|----|------|----------------|----------------|----------------|
| GP_MJOLNIRS_WRATH | Mjölnir's Wrath | 6 tokens / 2 direct dmg | 11 / 4 dmg | 16 / 6 dmg |
| GP_FENRIRS_BITE | Fenrir's Bite | 5 / 3 dmg + 1 Bleed | 9 / 4 + 2 Bleed | 13 / 6 + 3 Bleed |
| GP_SKADIS_VOLLEY | Skaði's Volley | 4 / arrows +1 dmg each | 7 / +2 each | 10 / +3 each |
| GP_SURTRS_FLAME | Surtr's Flame | 3 / 2 dmg, self 1 | 5 / 3 dmg, self 1 | 8 / 5 dmg, self 2 |
| GP_LOKIS_GAMBIT | Loki's Gambit | 5 / 1-4 random dmg | 8 / 2-6 | 11 / 3-8 |

### Defensive

| ID | Name | T1 | T2 | T3 |
|----|------|-----|-----|-----|
| GP_AEGIS_OF_BALDR | Aegis of Baldr | 4 / block 3 dmg | 7 / block 5 | 11 / block 8 |
| GP_EIRS_MERCY | Eir's Mercy | 5 / heal 2 | 9 / heal 4 | 13 / heal 6 |
| GP_VIDARS_REFLECTION | Vidar's Reflection | 5 / reflect 50% GP dmg | 8 / 75% | 12 / 100% + 1 |
| GP_HELS_PURGE | Hel's Purge | 3 / remove bleed/poison | 6 / remove + heal 2 | 9 / remove + heal 3 + 2 tokens |
| GP_FRIGGS_VEIL | Frigg's Veil | 6 / cancel opponent GP, refund 50% | 9 / cancel, 0% refund | 12 / cancel + steal tokens |

### Utility

| ID | Name | T1 | T2 | T3 |
|----|------|-----|-----|-----|
| GP_ODINS_INSIGHT | Óðinn's Insight | 3 / peek dice | 6 / peek dice + GP | 10 / full info + 2 tokens |
| GP_NJORDS_TIDE | Njörðr's Tide | 4 / reroll 3 kept | 7 / reroll 5 | 10 / reroll all, pick best |
| GP_BRAGIS_SONG | Bragi's Song | 4 / next round free rerolls | 7 / +1 reroll + free | 10 / +2 rerolls + cost to opponent |

### Hybrid

| ID | Name | T1 | T2 | T3 |
|----|------|-----|-----|-----|
| GP_TYRS_JUDGMENT | Tyr's Judgment | 5 / 2 dmg + block 2 | 9 / 3 + 3 | 13 / 4 + 4 |
| GP_FREYAS_BLESSING | Freyja's Blessing | 4 / gain 3 tokens + heal 1 | 7 / 5 tokens + heal 2 | 10 / 8 tokens + heal 3 |
| GP_HEIMDALLRS_WATCH | Heimdallr's Watch | 4 / next attack unblockable + take -1 dmg | 7 / 2 unblockable + -2 | 10 / all unblockable + -3 |

### Design Notes on God Power Balance

- **Mjölnir's Wrath** replaces Orlog's "Thor's Strike" (which was 1.5 tokens/dmg). Now 2.67 tokens/dmg at T3. Blockable by Aegis of Baldr.
- **Bleed** (from Fenrir's Bite) deals 1 damage per round for N rounds. Countered by Hel's Purge.
- Direct damage is "unblockable by dice" (axes/shields don't stop it) but IS blockable by Aegis and reflectable by Vidar's Reflection.
- Rock-paper-scissors: Offense beats Economy (kills before hoard pays off), Defense beats Offense (shields + reflects), Economy beats Defense (outscales over time).

---

## 7. Runes (20 Launch)

Runes are pre-match passive effects. Players equip 3 per match (slots unlock at account level 1, 5, 15).
**Every rune must have an explicit downside** (Constitution C05).
See `/data/runes.json` for full list.

### Categories

- **Economy** (6): Token manipulation — Hoarding, Blood Rune, Thief's Rune, Gullveig's Touch, Skald's Memory, Yggdrasil's Root
- **Probability** (2): Dice roll modifiers — Axe-Father's Mark (+15% axe, -10% shield), Shield-Wall (guaranteed defense, capped offense)
- **Conditional** (7): Trigger under specific conditions — Desperation, Bloodlust, Giant's Vitality, Berserkr's Frenzy, Patience, Echo of Ragnarök, Troll-Hide
- **Synergy** (3): Build around combos — Storm (3rd GP activation bonus), Twins (doubles bonus), Hel's Embrace (survive lethal once)
- **Information** (2): Knowledge advantage — Foresight (see opponent GP), Völva's Whisper (see opponent rune)

### PRD Implementation for Probability Runes

Probability runes like "Axe-Father's Mark (+15% axe chance)" use Pseudo-Random Distribution:
- First roll: ~5% bonus
- Each subsequent non-proc: +~5% cumulative
- On proc: reset to base
- Long-run average equals stated probability
- Display a subtle "charge" indicator so players see probability building

---

## 8. Battlefield Conditions (10 Launch)

One revealed at match start, one revealed at round 3. Conditions modify match rules.
No condition may shift any archetype's win rate by >10pp (Constitution C07).

| ID | Name | Effect | Rarity |
|----|------|--------|--------|
| COND_ODIN_GAZE | Óðinn's Gaze | Rerolls cost 1 token per die after first roll | Common |
| COND_MIDGARD_HEARTH | Midgard's Hearth | All healing doubled | Common |
| COND_FENRIR_HUNT | Fenrir's Hunt | First unblocked attack each round deals double | Common |
| COND_YGGDRASIL_ROOTS | Yggdrasil's Roots | +3 starting HP (18 total) | Common |
| COND_RAGNAROK | Ragnarök's Shadow | Both lose 1 HP/round from round 4+ | Uncommon |
| COND_FREYA_BLESSING | Freyja's Blessing | Hand dice generate/steal +1 token | Common |
| COND_TYR_ARENA | Tyr's Arena | God Powers disabled (pure dice) | Rare (5%) |
| COND_LOKI_MISCHIEF | Loki's Mischief | 1 random die per player locked per round | Uncommon |
| COND_NIFLHEIM_CHILL | Niflheim's Chill | Blocking defense dice generate +1 token | Uncommon |
| COND_JOTUN_MIGHT | Jötunheim's Might | All GP costs -2 (min 1) | Uncommon |

---

## 9. Archetypes and Balance Targets

### The 4 Canonical Strategies

| Archetype | Win Condition | Dice | God Powers | Runes |
|-----------|---------------|------|------------|-------|
| **AGGRO** | End by round 5-6 via front-loaded dice damage | 4× Berserkr + 2× Gambler | Surtr, Fenrir, Heimdallr | Axe-Father, Berserkr's Frenzy, Bloodlust |
| **CONTROL** | Survive to round 8+, outlast | 4× Warden + 2× Huskarl | Aegis, Eir, Vidar | Shield-Wall, Giant's Vitality, Troll-Hide |
| **ECONOMY** | Hoard tokens, drop massive T3 combos | 3× Miser + 2× Huskarl + 1× Hunter | Mjölnir, Freyja, Frigg | Hoarding, Thief's, Gullveig's |
| **COMBO** | Build specific synergy (arrows + Skaði + Storm) | 4× Hunter + 2× Gambler | Skaði, Njörðr, Óðinn | Storm, Skald's Memory, Twins |

### Target Win-Rate Matrix

```
         AGGRO   CONTROL   ECONOMY   COMBO
AGGRO      50%     35%       62%      58%
CONTROL    65%     50%       38%      45%
ECONOMY    38%     62%       50%      55%
COMBO      42%     55%       45%      50%
```

- Green: >60% (intended strong matchup)
- Red: <40% (intended weak matchup)
- Yellow: 40-60% (even)

### Balance Acceptance Criteria

| Metric | Green (Ship) | Yellow (Iterate) | Red (Block) |
|--------|-------------|------------------|-------------|
| Overall archetype win rate | 45-55% | 40-45% or 55-60% | <40% or >60% |
| Worst matchup | 35-65% | 30-35% or 65-70% | <30% or >70% |
| GP usage in wins | 10-60% | 5-10% or 60-70% | <5% or >70% |
| Avg match length | 5-8 rounds | 4-5 or 8-10 | <4 or >10 |
| Close matches (winner ≤4 HP) | ≥40% | 30-40% | <30% |
| First-mover advantage | 48-52% | 46-48% or 52-54% | <46% or >54% |
| Rune pick rate | Max 30% | 30-40% | >40% |
| Condition win-rate delta | ≤5pp | 5-10pp | >10pp |
| Direct damage efficiency T3 | ≥2.5 tok/dmg | 2.2-2.5 | <2.2 |
| Comeback rate | 25-35% | 20-25% or 35-40% | <20% or >40% |

---

## 10. Comeback Mechanics

### Fury Tokens

- When a player is behind by ≥4 HP at end of round, they gain **1 Fury Token**.
- 1 Fury Token = 2 regular tokens for **God Power activation only**.
- Fury Tokens do not carry over between rounds in PvP (use or lose each round). They do accumulate in PvE.
- Target comeback rate: 25-35% (player behind at round 3 eventually wins).

### Concede / Wager System

- **Concede:** Available any time, no penalty (Constitution C14).
- **Ranked Wager mode (post-launch):** Each match starts at 1 Ranked Point. Either player can "Raise" to double stakes. Opponent can accept or fold. Reframes conceding as strategic poker-like folding.

---

## 11. PvE Campaign — Realms of Yggdrasil

### Structure

- **9 Realms** (Midgard → Álfheim → Svartálfheim → Vanaheim → Jötunheim → Niflheim → Muspelheim → Helheim → Asgard).
- Each Realm = **7 nodes** on a branching path (4 combat, 1 elite, 1 event, 1 boss).
- A single match takes 3-5 minutes. A full run takes 25-40 minutes.
- Between matches: choose 1 of 3 rewards (new rune for this run, temporary GP upgrade, health restore, bonus tokens).

### Gear System (Run-Only)

- **4 slots:** Weapon, Shield, Helm, Amulet.
- Gear found during runs (elite rewards, events, boss drops).
- **Gear does NOT persist between runs.** Run-specific vertical progression.
- Permanent progression: unlocking gear INTO THE POOL (so future runs have more variety).
- 15 launch gear pieces. See `/data/gear.json`.

### Ascension System

- Beating a Realm unlocks Ascension 1 for that Realm.
- 10 Ascension levels per Realm (cumulative modifiers).
- 9 Realms × 10 Ascensions = **90 distinct challenge levels**.
- A1: AI +1 HP. A5: Bosses +1 GP slot. A8: AI max strategic competence. A10: Double boss, no heal.

### AI Difficulty Scaling (4 axes)

1. **Strategic competence:** Archetype-specific behavior, increasing sophistication.
2. **Statistical buffs:** +HP, +tokens, better dice in later Realms.
3. **Mission constraints:** "Win without GP," "Win in 5 rounds," "Hand dice disabled."
4. **Multi-stage gauntlets:** Elite nodes with 2+ matches, no heal between.

### MVP: Launch with 3 Realms

- Midgard (tutorial), Jötunheim, Muspelheim.
- Add 2 Realms per quarter.

---

## 12. Progression — Skill Tree

- **4 branches × 5 nodes = 20 total nodes.**
- Skill Points earned per account level (~1 per 3 PvE wins).
- **Respec-able** for 200 gold.
- **Does NOT apply in ranked PvP** (Constitution C11).

### Branches

1. **Dice Mastery:** Unlock Wild face, +1 reroll, freeze die, Runic face, swap die with opponent.
2. **God Power Mastery:** -1 T1 cost, Patron God (+1 effect), tier escalation, counter refund, 4th GP slot.
3. **Economy:** +1 starting token, doubles bonus, zero-token safety net, enhanced steal, token-to-HP conversion.
4. **Resilience:** +1 HP, damage response tokens, unused defense tokens, emergency barrier, survive lethal once.

Full details: `/data/progression.json` and Progression tab in spreadsheet.

---

## 13. Monetization

### Philosophy

- F2P with **cosmetics + battle pass**.
- **Nothing that affects gameplay sold for cash** (Constitution C09).
- Every cosmetic earnable through free play (Constitution C10).

### Revenue Model

- **Cosmetic shop:** Dice skins ($1.99-$24.99 worth of Runestones), board themes, avatar frames.
- **Battle Pass:** 6-week seasons, $4.99 premium track, ~20 tiers, cosmetics only.
- **Rewarded video ads:** Optional, for bonus currency.
- **Starter Pack:** $4.99 one-time, first 7 days.
- **Remove Ads:** $2.99 one-time.
- **Subscription (post-launch):** $1.99/mo for ad removal + daily Runestones + free battle pass.

### Currencies (max 3)

1. **Gold** 🪙 — soft currency, earned through gameplay, spent on cosmetics and respec.
2. **Runestones** 💎 — premium hard currency, earned slowly free or purchased.
3. **Skill Points** ⭐ — progression currency, earned per account level.

### Phased Rollout

- **M1-M3:** Starter Pack, Remove Ads, basic Runestone bundles, basic dice skins.
- **M3-M6:** Battle Pass, premium skins, board themes.
- **M6-M12:** Legendary skins, subscription, seasonal events.

---

## 14. Simulation Methodology — Incremental Layered Validation

### Core Principle

**Balance one layer at a time. Never skip a layer. Never ship a red metric.**

### Layer Sequence

```
L0: Raw Dice Math       → 6× Huskarl, no GP, Random vs Random. P1 48-52%.
L1: Offensive GP Only   → Add 5 offense powers. Greedy beats Random 60-70%.
L2: Full GP Pool        → All 16 powers. 4 Archetypes. R-P-S matrix validates.
L3: Dice Pool           → 8 dice types. Canonical loadouts. No die >50% of wins.
L4: Battlefield Conditions → 10 conditions, tested individually then in pairs. No >10pp shift.
L5: Runes               → 20 runes. Meta evolution sim. No rune >40% pick rate.
L6: Fury Tokens          → Comeback mechanics. Comeback rate 25-35%.
L7: PvE Campaign        → Gear + Skill Tree + AI. Separate simulation track.
```

### Regression Rules

- When adding Layer N, re-run ALL tests from Layers 0 through N-1.
- If previous layer turns yellow → investigate interaction before proceeding.
- If previous layer turns RED → revert new layer and fix before re-adding.
- Never tune a lower layer to fix a higher layer's problem.
- Store outputs as versioned JSON (e.g., `balance_L3_v1.2.json`).
- After ANY number change in spreadsheet, re-run from lowest affected layer upward.

### Agents (in order of implementation)

1. **Random Agent** (2 hrs): Uniform random legal actions. L0 baseline.
2. **Greedy Agent** (4 hrs): Heuristic score function, pick highest. Three variants (Aggro/Control/Economy scoring).
3. **Archetype Agent** (8 hrs): Rule-based strategy with 10-15 rules per archetype.
4. **MCTS Agent** (20+ hrs): Monte Carlo Tree Search. **Not recommended for initial balance.** Only build if simulation results seem suspiciously clean.

### Simulation Scale

- 5,000-10,000 games per matchup for reliable confidence intervals.
- At 10,000 games: 95% CI on 50% win rate = ±1%. Precise enough to detect 55% imbalance.
- Full L5 suite: ~1.6M total simulations. Runs in <30 minutes on modern laptop with NumPy optimization.

---

## 15. Architecture — Code Structure

### Simulator (Python)

```
/simulator
├── game_state.py       # Immutable GameState dataclass
├── game_engine.py      # GameEngine: apply_action(state, action) → (new_state, events)
├── die_types.py        # DieType definitions, face distributions
├── god_powers.py       # GodPower definitions, tier costs/effects
├── runes.py            # Rune definitions, triggers
├── conditions.py       # Battlefield Condition definitions
├── agents/
│   ├── random_agent.py
│   ├── greedy_agent.py
│   └── archetype_agent.py  # Aggro, Control, Economy, Combo
├── simulator.py        # Run N games, collect metrics
├── balance_suite.py    # Full layer-by-layer test suite
├── analysis.py         # Win-rate heatmaps, GP usage charts, metric dashboards
└── data/               # JSON exports from spreadsheet
    ├── dice_types.json
    ├── god_powers.json
    ├── runes.json
    ├── conditions.json
    └── gear.json
```

### Unity Client

```
/unity-project
├── Assets/
│   ├── GameCore/           # Pure C# game logic (NO Unity dependencies)
│   │   ├── GameState.cs
│   │   ├── GameEngine.cs
│   │   ├── DieTypes.cs
│   │   ├── GodPowers.cs
│   │   ├── Runes.cs
│   │   └── Conditions.cs
│   ├── Presentation/       # MonoBehaviours, UI, animations
│   ├── AI/                 # AI opponent logic
│   ├── Networking/         # Firebase integration
│   ├── Data/               # JSON content files (same as simulator)
│   └── Resources/          # Art, audio, prefabs
```

### Key Architecture Rule

`GameCore` is **engine-agnostic**. No MonoBehaviour, no UnityEngine imports.
The pattern: `GameState + Action → GameEngine.Apply() → (NewGameState, List<GameEvent>)`.
Same logic runs headless (Python sim, C# Cloud Functions) or with UI (Unity).

### Parity Tests

After porting Python → C#, maintain a suite of 50 canonical game states with expected outcomes.
Run in both Python and C# after every change. If they diverge, one has a bug.

---

## 16. What's NOT in v1

- Ranked PvP matchmaking (casual async only)
- Battle pass (Month 6)
- Skill tree (Month 7)
- Realms 4-9 (2 per quarter)
- Ascension levels
- Best-of-3 mode
- Clans/guilds/spectator
- Android (after iOS validates)
- Real-time PvP

---

## 17. Known Problems from Orlog (and Our Fixes)

| Orlog Problem | Our Fix |
|--------------|---------|
| Thor's Strike dominance (1.5 tok/dmg, unblockable) | Mjölnir's Wrath at 2.67 tok/dmg, blockable by Aegis |
| One dominant strategy | 4 archetypes with enforced R-P-S (Constitution C01, C02) |
| No multiplayer | Async PvP from Month 3 |
| RNG feels unfair | PRD for all probability effects; Fury Token comeback mechanic |
| Certain God Favors useless | Simulator ensures no GP <10% usage (C06) |
| Limited replayability | Battlefield Conditions (match variance), Runes (build variety), Roguelike PvE |
| Inverted difficulty curve | Ascending AI difficulty across 9 Realms × 10 Ascensions |
| Physical board game: unreadable tokens | Digital solves this by default — tooltips, previews, animations |
| Game feels decided after round 1 | Fury Tokens + comeback mechanics; target comeback rate 25-35% |

---

## 18. Conventions for Claude Code

### When writing simulator code:

- Use Python 3.11+ with type hints everywhere.
- GameState must be immutable — every action returns a new state.
- Use `@dataclass(frozen=True)` for GameState.
- Use NumPy for dice rolling in bulk simulation (vectorize when possible).
- All balance numbers come from JSON files in `/data/` — never hardcode.
- Every mechanic needs a unit test. Use pytest.
- Print simulation results as formatted tables, not raw dicts.

### When writing Unity code:

- GameCore classes have zero Unity dependencies. They live in `/Assets/GameCore/`.
- Presentation layer (MonoBehaviours) lives in `/Assets/Presentation/`.
- Content data loaded from JSON at runtime (not baked into code).
- Use `[SerializeField]` for inspector-visible fields, never public fields.

### When adjusting balance:

- Change the spreadsheet first, re-export JSON, re-run simulator.
- Never change a number in code without updating the spreadsheet.
- Log every balance change in the Change Log tab.

### Naming conventions:

- God Power IDs: `GP_MJOLNIRS_WRATH` (screaming snake case, stable forever)
- Die IDs: `DIE_WARRIOR` (screaming snake case)
- Rune IDs: `RUNE_HOARD` (screaming snake case)
- Condition IDs: `COND_ODIN_GAZE` (screaming snake case)
- Display names can change; IDs never change.
- Python: snake_case for functions/variables, PascalCase for classes.
- C#: PascalCase for public members, camelCase for private, PascalCase for classes.

---

## 19. Data Files

The master spreadsheet is `/data/Fjold_Master_Design_v1.0.xlsx`.
Export the following tabs as JSON for the simulator and Unity client:

- `/data/dice_types.json` — from "Dice Types" tab
- `/data/die_faces.json` — from "Die Faces" tab
- `/data/god_powers.json` — from "God Powers" tab
- `/data/runes.json` — from "Runes" tab
- `/data/conditions.json` — from "Battlefield Conditions" tab
- `/data/gear.json` — from "Gear" tab
- `/data/progression.json` — from "Progression" tab
- `/data/archetypes.json` — from "Archetypes" tab
- `/data/balance_targets.json` — from "Balance Targets" tab
- `/data/pve_campaign.json` — from "PvE Campaign" tab

### First Task for Claude Code

> "Read the CLAUDE.md and all JSON files in /data/. Build the L0 simulator:
> GameState dataclass, GameEngine with roll/keep/resolve, RandomAgent,
> and a runner that plays 10,000 games and reports P1 win rate,
> avg rounds, and avg winner HP. Use only Huskarl's dice, no God Powers."

---

*Last updated: April 14, 2026. Version 1.0.*
*This document is the condensed output of the full design conversation. For deeper rationale on any decision, refer to the original chat history.*
