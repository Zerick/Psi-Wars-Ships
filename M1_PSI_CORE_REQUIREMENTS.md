# M1 Psi-Core: Rules Engine Requirements Specification
## GURPS Psi-Wars Ship Combat Simulator — Combat Resolution Layer

**Version:** 1.0.0-DRAFT
**Status:** Awaiting owner approval before test suite creation
**Last Updated:** 2026-03-14

---

## 1. System Overview

Psi-Core (M1) is the rules engine for the combat simulator. It implements GURPS dice mechanics, the Psi-Wars Action Vehicular Combat rules, and all game logic needed to resolve multi-ship space combat encounters turn by turn.

M1 consumes ship data from M3 (Data-Vault) and produces combat events. It never writes directly to the database — it calls M3's DAL methods to read stats and persist state changes.

### 1.1 Technology Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | Python 3.11+ | Strict type hinting throughout |
| Testing | pytest | Test suite must pass before implementation is complete |
| Dependency | m3_data_vault | Reads ship stats and writes state via M3 DAL |
| Dice | Internal module | Deterministic seeding for reproducible tests |

### 1.2 Design Principles

- **Deterministic Testing**: All randomness flows through a single `DiceRoller` class that can be seeded or mocked. No test ever depends on random outcomes.
- **Strict Separation from M3**: M1 imports M3's DAL to read/write ship state. M3 never imports M1.
- **Event-Driven Output**: Every combat action produces structured event objects (not print statements). The terminal UI and future web UI consume these events to display results.
- **Modular Subsystems**: Each rules subsystem (dice, chase, attack, defense, damage, etc.) is an independent module that can be tested in isolation.

### 1.3 Module Decomposition

M1 is organized into these subsystems:

| Module | Responsibility |
|--------|---------------|
| `dice` | 3d6 rolls, damage rolls, dice parsing, critical success/failure detection |
| `combat_state` | Turn tracking, engagement relationships, range bands, advantage/facing/matched speed |
| `chase` | Chase roll resolution, maneuver validation, range band shifting, escape conditions |
| `attack` | Hit roll calculation, modifiers (range/speed, sensor lock, SM, deceptive), accuracy rules |
| `missile` | Missile attack resolution (separate modifier pipeline from beam attacks) |
| `defense` | Dodge calculation, High-G dodge, missile defense, decoy/ESM, jamming |
| `point_defense` | Wait-and-attack missile/torpedo interception |
| `damage` | Damage roll parsing, armor penetration, force screen ablation, wound level, subsystem damage |
| `electronic_warfare` | Detection, stealth, ambush, sensor locks, active jamming, scrambling |
| `maneuvers` | Maneuver catalog with validation rules (facing, stall restrictions, attack permissions) |
| `passengers` | Passenger actions: emergency repairs, tactical coordination, e-war, navigation, boarding |
| `emergency_power` | Emergency power allocation: engines, evasion, firepower, screen recharge, system purge |
| `formations` | Multi-party chases, formation intercept, area jammer sharing |
| `special` | Lucky breaks, cinematic injury (mook rules, "Just a Scratch"), hugging, ramming |
| `turn_sequence` | Turn order, declaration/resolution phases, configuration locking |
| `events` | Structured event dataclasses for all combat outcomes |

---

## 2. Dice Subsystem (`dice`)

The foundation of GURPS. All randomness in the engine flows through this module.

### 2.1 Core Rolling

```
roll_3d6() -> int                    # Standard GURPS success roll die
roll_nd6(n: int) -> int              # Roll n six-sided dice, sum result
roll_damage(damage_str: str) -> int  # Parse "6d×5(5) burn" and roll damage
```

### 2.2 Damage String Parsing

GURPS damage strings follow the pattern: `NdM×X(AD) type [modifiers]`

Examples from the ship data:
- `"6d×5(5) burn"` → roll 6d6, multiply by 5, armor divisor 5, burning damage
- `"3d×5(10) burn"` → roll 3d6, multiply by 5, armor divisor 10
- `"5d×200 cr ex"` → roll 5d6, multiply by 200, crushing explosive
- `"6d×30(2) burn ex"` → roll 6d6, multiply by 30, armor divisor 2, burning explosive
- `"6d×4(5) burn"` → roll 6d6, multiply by 4, armor divisor 5
- `"12d burn"` → roll 12d6, no multiplier, burning
- `"4d tox"` → roll 4d6, toxic (ignores DR in some cases)
- `"0"` → zero damage (tractor beams)

The parser must extract: dice count, dice multiplier, flat adds, armor divisor, damage type, and explosive flag.

### 2.3 Success Roll Resolution

```
check_success(effective_skill: int, roll: int) -> SuccessResult
```

Returns a `SuccessResult` with: `success` (bool), `margin` (int), `critical` (bool), `critical_type` ("success" | "failure" | None).

**Critical success rules:**
- Roll of 3 or 4: always critical success
- Roll of 5: critical success if effective skill ≥ 15
- Roll of 6: critical success if effective skill ≥ 16

**Critical failure rules:**
- Roll of 18: always critical failure
- Roll of 17: critical failure if effective skill ≤ 15; otherwise ordinary failure
- Roll of 10+ greater than effective skill: critical failure

**Minimum skill rule:** You may not attempt a roll if effective skill < 3, except for defense rolls.

### 2.4 Quick Contest Resolution

```
resolve_quick_contest(skill_a: int, roll_a: int, skill_b: int, roll_b: int) -> ContestResult
```

Both sides roll. Compare margins of success (or failure). The winner is the one with the better margin. Ties go to neither side.

### 2.5 DiceRoller Class

```python
class DiceRoller:
    def __init__(self, seed: int | None = None): ...
    def roll_3d6(self) -> int: ...
    def roll_nd6(self, n: int) -> int: ...
    def roll_1d6(self) -> int: ...
    # All other roll methods delegate to these
```

For testing, construct with a seed for reproducibility, or inject a mock that returns predetermined values.

---

## 3. Combat State (`combat_state`)

Tracks the dynamic state of a combat encounter that isn't persisted to the database — positioning, relationships, turn tracking.

### 3.1 Engagement State

Each pair of ships in combat has a relationship:

```
EngagementState:
  ship_a_id: str
  ship_b_id: str
  range_band: str          # "close", "short", "medium", "long", "extreme",
                           #   "distant", "beyond_visual", "remote", "beyond_remote"
  advantage: str | None    # ship_id that has advantage, or None
  matched_speed: bool      # True if the advantaged ship has matched speed
  hugging: str | None      # ship_id that is hugging, or None (requires 3+ SM difference)
  facing_a: str            # What facing ship_a presents: "front", "rear", etc.
  facing_b: str            # What facing ship_b presents
```

### 3.2 Per-Ship Turn State

State that resets each turn:

```
TurnState:
  ship_id: str
  maneuver: str | None           # Chosen maneuver for this turn
  intent: str                    # "pursue" or "evade"
  configuration: dict            # Afterburner on/off, force screen facing, mode
  has_acted: bool
  has_defended: bool
  dodge_bonus: int               # Accumulated dodge bonuses for this turn
  attack_bonus: int              # Accumulated attack bonuses
  precision_aiming_target: str | None  # Target of precision aiming (persists to next turn)
  precision_aiming_bonus: int    # +4 if precision aimed last turn
  stunt_dodge_used: bool         # Ace pilot +1 from stunt maneuver
```

### 3.3 Range Band System

Range bands with their penalties (use low penalty for attacks):

| Band | Range | Penalty |
|------|-------|---------|
| close | 0-5 | 0 to -2 |
| short | 6-20 | -3 to -6 |
| medium | 21-100 | -7 to -10 |
| long | 101-500 | -11 to -14 |
| extreme | 500-2000 | -15 to -18 |
| distant | 2001-10000 | -19 to -22 |
| beyond_visual | 10001-50000 | -23 or more |
| remote | 50001+ | -27 or more |
| beyond_remote | 200001+ | -31 or more |

**Special rules:**
- Beyond visual: requires active sensors to engage
- Remote: requires 2 range-band shifts to enter/exit; no advantage possible; -30 penalty
- Beyond remote: no tactical relevance

### 3.4 Collision Range

A ship is at collision range when its speed bonus exceeds the absolute value of the range penalty. This is relevant for Ram, Force, Embark/Disembark maneuvers.

---

## 4. Chase Subsystem (`chase`)

Implements the Action Vehicular Combat chase roll system.

### 4.1 Chase Roll Calculation

The chase roll is a Quick Contest of effective piloting skill. The base chase bonus for a ship is calculated from its stats (Handling + SR + speed factor), but this is computed by M3's `get_effective_stats()`. M1 adds situational modifiers.

**Chase roll modifiers:**
- Maneuver modifiers (Evade: -2, Stunt: variable, etc.)
- High-G stunt: +1 (requires HT roll)
- All Power to Engines: +2 (costs emergency power)
- Tactical coordination: +2 (from formation tactics)
- Rough terrain / obstacles: -2 to handling
- Afterburner active: uses afterburner stats instead of base

### 4.2 Chase Roll Resolution

```
resolve_chase_roll(margin_of_victory: int, winner_intent: str,
                   winner_had_advantage: bool) -> ChaseOutcome
```

| Margin | Outcome |
|--------|---------|
| 0-4 | No range change. Opponent loses advantage if they had it. Stall-speed ships need ≥0 to fire fixed weapons. |
| 5-9 | Gain advantage OR shift range by 1 band. If already advantaged: may match speed. |
| 10+ | Match speed, OR shift 1 band + gain advantage, OR shift 2 bands. |

**Constraints:**
- Pursuers may only reduce range
- Evaders may only increase range
- Stall-speed ships may not pursue a ship that is advantaged against them
- Static maneuvers grant opponent 1 free range band shift (not chase victory)

### 4.3 Escape Conditions

Escape occurs when:
- Target successfully hides and elects to escape
- Pursuer stops and resigns the chase
- Target exceeds maximum attack range for current terrain
- Target successfully shunts into hyperspace

---

## 5. Maneuver Catalog (`maneuvers`)

Each maneuver has defined properties and restrictions.

### 5.1 Maneuver Definition

```
ManeuverDef:
  name: str
  facing: str              # Required facing: "front", "rear", "any", "any_opponent_choice"
  chase_modifier: int      # Modifier to chase roll
  allows_attack: str       # "none", "no_accuracy", "half_accuracy", "full_accuracy"
  dodge_bonus: int          # Bonus to dodge this turn
  is_static: bool          # Static maneuvers lose advantage, grant opponent range shift
  requires_collision: bool  # Ram, Force, Embark require collision range
  stall_restricted: bool   # Ships with stall speed cannot use this in certain conditions
```

### 5.2 Maneuver Catalog

| Maneuver | Facing | Chase Mod | Attack Allowed | Dodge Bonus | Static | Notes |
|----------|--------|-----------|----------------|-------------|--------|-------|
| Attack | F | 0 | full_accuracy | 0 | No | Stall ships cannot use |
| Move | F or B | 0 | none | 0 | No | Must declare pursue/evade |
| Move and Attack | F | 0 | half_accuracy | 0 | No | |
| Evade | B | -2 | none | +2 | No | Must increase range |
| Mobility Pursuit | F | 0 | no_accuracy | 0 | No | |
| Mobility Escape | B | 0 | no_accuracy | 0 | No | |
| Stunt | Any | varies | no_accuracy | 0 | No | Stall restricted vs advantaged |
| Stunt Escape | Any | varies | no_accuracy | 0 | No | |
| Force | Any | 0 | half_accuracy | 0 | No | Requires collision range |
| Ram | F | 0 | half_accuracy | 0 | No | Requires collision range |
| Hide | Any | 0 | none | 0 | Yes | |
| Stop | Any | 0 | none | 0 | Yes | |
| Precision Aiming | F | 0 | none | 0 | Yes | +4 to attacks next turn |
| Embark/Disembark | Any | 0 | special | 0 | No | Requires collision range |
| Emergency Action | Any* | 0 | none | 0 | No | Opponent chooses facing |

### 5.3 Maneuver Validation

```
validate_maneuver(ship_stats: EffectiveStatBlock, maneuver: str,
                  engagement: EngagementState) -> list[str]  # Returns list of violation messages, empty = valid
```

Validates:
- Stall speed restrictions (cannot Attack, cannot Stunt against advantaged opponent, cannot pursue advantaged opponent)
- Collision range requirements
- Static maneuver restrictions (cannot use with stall speed unless stopped)

---

## 6. Attack Subsystem (`attack`)

### 6.1 Hit Roll Calculation

```
calculate_hit_modifiers(attacker_stats, target_stats, weapon, engagement,
                        maneuver, turn_state) -> HitModifiers
```

**Modifier pipeline (beam/direct fire weapons):**

1. **Base skill**: Gunner skill (from controller)
2. **Range/Speed penalty**: Highest of |range penalty|, own speed penalty, target speed penalty. Exception: matched speed uses the higher of |range penalty| or stall speed.
3. **Size modifier**: Target's SM as bonus
4. **Relative size penalty**: Corvette→fighter: -5, Capital→corvette: -5, Capital→fighter: -10. Halved for light turrets.
5. **Sensor lock**: +3 (+5 with targeting computer) if scanner has lock
6. **Accuracy**: Added if maneuver allows (Attack maneuver, or Move and Attack with matched speed)
7. **Precision aiming**: +4 if precision aimed on previous turn (Attack maneuver only)
8. **Deceptive attack**: -2 per -1 to target's defense (optional)
9. **Weapon linking**: ROF bonus from linked weapons
10. **ROF bonus**: Standard GURPS rapid fire bonus table

**Cannot attack if:**
- Maneuver doesn't allow it
- Weapon's mount facing doesn't match current facing (unless advantaged)
- Weapon is disabled/destroyed
- Ship has no power

### 6.2 Ace Pilot and Gunslinger Rules

Ace Pilots may attack with vehicle weapons during maneuvers that normally don't allow it:
- Mobility Escape/Pursuit, Move, Stunt, Stunt Escape: attack without accuracy
- Force, Move and Attack, Ram: attack with halved accuracy
- Attack, or Move and Attack with matched speed: attack with full accuracy

Gunslingers get the same progression but with hand-held weapons only.

### 6.3 Plasma Flak Rules

Flak turrets use special hit rules:
- Extreme range: hit on 1 + target SM or less
- Long or closer: hit on 5 + target SM or less
- Recoil 1
- Targets in range count as rough terrain (-2 handling)
- Failed handling roll = automatic flak hit

---

## 7. Missile Attack Subsystem (`missile`)

Missiles use a completely different modifier pipeline from direct fire.

### 7.1 Missile Hit Roll

```
calculate_missile_hit(gunner_skill, weapon_acc, target_sm, target_ecm,
                      target_speed_mod) -> int  # Effective skill
```

**Missile modifiers:**
- Weapon accuracy (always applied)
- Target SM
- Target ECM penalty
- Half of target speed modifier (rounded up) as penalty
- Ignore: deceptive attacks, range penalties, sensor locks, targeting computers
- Ace pilots never add accuracy to missile attacks

**Air burst option:** Explosive missiles without armor divisors may attempt +4 to hit. Miss by 1 on explosive weapon = "near miss" (1/3 damage, no armor divisor).

**Free missile:** Under circumstances where you would gain accuracy, you may instead fire a free missile in addition to your normal attack.

### 7.2 Torpedo Rules

- Use Gunner (Torpedo), not Gunner (Missile)
- Defaults to Gunner (Blaster) at -4 and Artillery (Guided Missile) at -2
- Grant target +1 dodge at extreme range, +2 at distant
- Cannot attack beyond distant range
- NOT guided — they use normal attack rules, not missile rules

---

## 8. Defense Subsystem (`defense`)

### 8.1 Vehicular Dodge Calculation

```
calculate_dodge(pilot_skill, ship_stats, engagement, maneuver,
                turn_state) -> int  # Effective dodge
```

**Base vehicular dodge** is determined by the pilot's Piloting skill and the ship's handling. The exact formula depends on the campaign rules, but typically: Piloting/2 + 3 + Handling modifier, or a simpler formulation.

**Dodge modifiers:**
- Evade maneuver: +2
- Advantage (escaping): +1
- Ace Pilot + Stunt maneuver: +1 to first dodge
- High-G dodge: +1 (requires HT roll; +2 if G-chair or G-suit; failure = FP loss)
- Emergency evasive maneuvers: +2 (costs emergency power, always High-G)
- Tactical coordination (defensive): +1 to formation dodge
- Precision aiming target aware: +2 to dodge against the aimer

### 8.2 Missile Defense

Against missiles, additional modifiers apply:
- Static dodge penalty: -3
- Tactical ESM: +1
- Decoy launcher: +1 (limited charges)

**Alternative: Jam the missile** (instead of dodging):
- Roll: Electronics Operation (ECM) / 2
- Bonus: half vehicle's ECM rating
- Bonus: +2 if using decoy launcher
- This functions as a parry

**Near miss rule:** If defending against explosive missile (no armor divisor) with margin of 0, treat as near miss: hit with 1/3 damage. If already a near miss, it misses entirely.

### 8.3 High-G Dodge

Available if vehicle acceleration ≥ 40 or move ≥ 400:
- +1 to dodge
- Pilot must roll vs HT
- +2 to HT roll if G-chair or G-suit
- Failure: lose FP equal to margin of failure

---

## 9. Point Defense Subsystem (`point_defense`)

### 9.1 Point Defense Resolution

Passengers with Wait and Attack (Point Defense) may intercept incoming missiles/torpedoes.

```
resolve_point_defense(gunner_skill, target_type, sensor_lock_bonus,
                      special_bonus) -> SuccessResult
```

**Modifiers:**
- Ignore range penalties
- Apply only size/speed modifiers (combined values):
  - 100mm "Light" missile: -16
  - 160mm "Standard" missile: -16
  - 400mm "Light" torpedo: -11
  - 640mm "Heavy" torpedo: -10
  - 1600mm "Bombardment" torpedo: -8
- Add sensor lock bonus
- Add special point defense bonuses (e.g., Needle Laser +3)

---

## 10. Damage Subsystem (`damage`)

### 10.1 Damage Resolution Pipeline

```
resolve_damage(raw_damage: int, weapon, target_stats, facing_hit,
               engagement) -> DamageResult
```

**Pipeline:**

1. **Force screen ablation**: If target has fDR > 0, force screen absorbs damage first (hardened 1, ablative). Against plasma/shaped-charge/plasma-lance: standard screens ignore armor divisors. Heavy screens ignore ALL armor divisors.
2. **Hull armor**: Apply remaining damage against directional DR for the facing hit. Apply armor divisor to DR. Penetrating damage = raw damage minus effective DR.
3. **Wound level determination**: Compare penetrating damage to ship's max HP to determine wound level (scratch/minor/major/crippling/mortal/lethal).
4. **Wound effects**: Based on wound level, trigger appropriate effects via M3.

### 10.2 Armor Divisor Application

```
apply_armor_divisor(dr: int, divisor: float) -> int
```

Divide DR by the divisor. Fractional divisors multiply DR (0.5 = double DR, 0.2 = 5x DR, 0.1 = 10x DR).

### 10.3 Wound Effects (M1 responsibility, calls M3 to persist)

| Wound Level | Effects |
|-------------|---------|
| Scratch | No effect |
| Minor | Cosmetic damage. Can accumulate (HT roll; failure escalates). |
| Major | Disable one system (roll 3d6 on subsystem table). Accumulates. |
| Crippling | Destroy one system. HT roll to remain operational. Accumulates. |
| Mortal | Destroy one system. HT roll or ship destroyed. Accumulates. |
| Lethal | Ship instantly destroyed. |

### 10.4 Wound Accumulation

If a ship takes a wound equal to or less than its current wound level, the wound may accumulate. Roll HT once per additional wound; failure escalates wound level by one. If HT roll succeeds with margin of 0 and wound level disables/destroys a system, disable/destroy a second system.

### 10.5 Subsystem Damage Table (3d6)

| Roll | System | Cascade Target |
|------|--------|----------------|
| 3 | Fuel | Power |
| 4 | Habitat | Cargo |
| 5 | Propulsion | Weaponry |
| 6 | Cargo/Hangar | None |
| 7 | Equipment | Controls |
| 8 | Power | Propulsion |
| 9 | Weaponry | Equipment |
| 10 | Armor | Fuel |
| 11 | Fuel | Power |
| 12 | Habitat | Cargo |
| 13 | Propulsion | Weaponry |
| 14 | Cargo/Hangar | None |
| 15 | Equipment | Controls |
| 16 | Power | Propulsion |
| 17 | Weaponry | Equipment |
| 18 | Armor | Fuel |

**Cascade logic:** If a system is already disabled, roll HT. Failure → system destroyed (counts as crippling wound). HT success or system already destroyed → damage cascades to the noted system.

**Targeted systems:** Attacker may accept -5 to hit to target a specific system (no random roll).

### 10.6 Cinematic Injury Rules

**Mook vehicles:** If a mook takes a major wound, remove it from combat. Otherwise it sparks and continues.

**Just a Scratch:** PCs may spend a character point to reduce any wound to minor. Accumulation from this can only trigger disabled systems, never worse.

---

## 11. Electronic Warfare Subsystem (`electronic_warfare`)

### 11.1 Detection

Ships automatically detect each other at maximum sensor range unless actively stealthing.

**Stealth detection (sensor):**
- Quick Contest: Electronics Operation (Sensors) vs Electronics Operation (ECM)
- Sensor side penalized by target's ECM value
- -10 in nebula
- Success: engage at preferred range
- Failure: stealthy ship may pass or ambush from beyond visual

**Stealth detection (visual, closer than beyond visual):**
- Contest: Vision vs worst of (Piloting, Stealth)
- Modifiers: +SM, darkness, -4 for chameleon, -5 for nebula/asteroid, -10 for both
- Success by 4+ allows approaching one band closer per 4 margin

### 11.2 Ambush

If a ship evades detection, it may initiate combat at whatever range its stealth allowed.

**Ambush defense:**
- Defenders roll IQ. Combat Reflexes: +6. Failure: cannot act or defend turn 1. Success: act/defend at -4.
- Danger Sense: IQ roll to detect. Success: act normally. Critical success: warn allies.

### 11.3 Active Jamming

Passenger action: roll Electronics Operation (ECM) vs Electronics Operation (Sensors), penalized by target ECM. Success: target loses sensor lock for one turn (no +3/+5 bonus, no missile attacks).

### 11.4 Missile Jamming

Separate from active jamming. Uses installed Distortion Jammer:
- Roll: Electronics Operation (ECM) / 2
- Bonus: half vehicle ECM rating
- Bonus: +2 with decoy launcher
- Functions as a parry against missile attacks

---

## 12. Passenger Actions Subsystem (`passengers`)

Capital ships (and some corvettes) have crews performing actions simultaneously.

### 12.1 Passenger Action Catalog

| Action | Skill | Notes |
|--------|-------|-------|
| Man Turret (Attack) | Gunner | No -1 passenger penalty for vehicle weapons |
| Board | Special | Auto if embarked via launch pad; otherwise EO(Security)/Forced Entry/Lockpicking |
| Chart Hyperspace Route | Navigation (Hyperspace) | 5 turns base; -2 per turn reduced; -8 for 1 turn |
| Command and Coordinate | Leadership | Complementary roll, or replace crew skill |
| Emergency Repairs | Mechanic | -10 penalty (halved by Quick Gadgeteer); jury-rigged result |
| Operate Electronics | EO (Sensors/ECM/Comms) | Jam, detect, communicate |
| Tactical Coordination | Tactics | +2 chase, -2 enemy hit/+1 dodge, +2 hit/-1 enemy dodge |
| Point Defense | Gunner | Wait and Attack on incoming missiles |

### 12.2 Crew Skill

Capital ships use Crew Skill (default 12, range 10-15) for all passenger actions unless a named character is performing the action.

### 12.3 Internal Movement

Moving between stations takes turns:
- Starfighters/shuttles: 0 turns (free)
- Corvettes: 1 turn
- Capital ships: 2 turns

Obstacles may add turns (skill roll to bypass).

---

## 13. Emergency Power Subsystem (`emergency_power`)

### 13.1 Emergency Power Reserve

Some ships have Emergency Power Reserves. Ships without them may "redline" (reduce HT by 1) instead. Each use costs 1 point of reserve (or 1 HT). Requires a Passenger Action and skill roll.

### 13.2 Emergency Power Options

| Option | Skill | Effect |
|--------|-------|--------|
| All Power to Engines | Electrician / Mechanic | +2 chase rolls. Cumulative -4 per repeat. Crit fail: engines disabled. |
| Emergency Evasive | Electrician / Mechanic | +2 to one dodge (always High-G) |
| Emergency Firepower | Electrician / Armoury | +1 or +2 damage per die; Malf reduced to 14 at +2. Crit fail: weapons disabled. |
| Emergency Screen Recharge | Electrician / Armoury (Force Screen) | Immediately restore fDR to full |
| Emergency System Purge | Electrician / Mechanic | Reroll failed HT (surge/operational/disabled). No effect on destroyed. |
| Emergency Weapon Recharge | Electrician / Armoury | Restore half shots to one weapon |

Reserves replenish at 1/hour during normal operation, or fully after 1 hour of maintenance in a proper shop.

---

## 14. Formation Subsystem (`formations`)

### 14.1 Formation Rules

Ships in a group may form a formation. Benefits:
- Any member may intercept an attack on any other member (if attacker is not advantaged)
- Area Jammer protection shared with all formation members
- May benefit from tactical coordination

### 14.2 Tactical Coordination

Requires a Tactics roll (Quick Contest if target is also a formation). Choose one benefit:
- **Pursuit Tactics**: +2 to formation chase rolls
- **Defensive Tactics**: Target at -2 to hit formation, OR formation at +1 dodge
- **Offensive Tactics**: Formation at +2 to hit target, OR target at -1 dodge

---

## 15. Special Rules (`special`)

### 15.1 Lucky Breaks

Ace Pilots get one free Lucky Break per chase scenario. Others can purchase them with character points or use Serendipity.

**Uses:**
- Invoke a new obstacle/opportunity
- Increase wound severity by 2 levels
- Ignore all attacks for one round

### 15.2 Hugging

If you match speed with a target ≥3 SM larger at collision range, you may hug it.
- If target is ≥6 SM larger: inside its force screen, ignore DR
- Hugged target: only half turrets can fire (proper facing), no fixed mounts, -2 to all attacks
- Attacking a hugging ship: -2 to hit; miss/dodge hits hugged vehicle on (hugged SM - 3)

### 15.3 Force Screen Configuration

Adjustable force screens may double DR on one facing, halving all others. Configuration must be declared with maneuver.

### 15.4 Ship Classification

| Class | SM Range | Chase Roll | Notes |
|-------|----------|------------|-------|
| Fighter | SM +4 to +7 | +16 or better | |
| Corvette | SM +7 to +10 | +11 to +15 | |
| Capital Ship | SM +10+ | +10 or worse | |

"Soar like a Leaf" perk: treat corvette as fighter for all chase purposes.

---

## 16. Turn Sequence (`turn_sequence`)

### 16.1 Turn Phases

1. **Declaration Phase**: All players declare maneuvers simultaneously. Higher Basic Speed (or advantaged) declares second. Configuration (afterburner, force screen facing, ship mode) is locked with declaration.
2. **Chase Resolution Phase**: Resolve chase rolls. Apply range band shifts, advantage changes, matched speed.
3. **Attack Phase**: Resolve attacks in initiative order (higher Basic Speed first). Each attack triggers defense resolution immediately.
4. **Damage Phase**: Apply all damage, resolve wound effects, subsystem damage.
5. **Cleanup Phase**: Reset turn-specific state. Force screens regenerate. Advance turn counter.

### 16.2 Force Screen Regeneration

Force screens recover to full DR at the start of each turn (between chase turns — once per 10 seconds in normal GURPS time).

---

## 17. Event System (`events`)

All combat outcomes are expressed as structured event objects.

### 17.1 Event Types

```
ChaseRollEvent       # Results of a chase roll contest
ManeuverEvent        # What maneuver was chosen and its effects
AttackRollEvent      # Attack roll with all modifiers broken down
DefenseRollEvent     # Defense roll with all modifiers
DamageEvent          # Damage dealt, armor penetration, wound level
SystemDamageEvent    # Which system was hit, disabled/destroyed
ForceScreenEvent     # Force screen ablation details
MissileAttackEvent   # Missile-specific attack resolution
PointDefenseEvent    # Point defense interception attempt
ElectronicWarfareEvent  # Jamming, detection, lock results
EmergencyPowerEvent  # Emergency power usage and results
FormationEvent       # Formation tactical coordination
EscapeEvent          # Ship escaped combat
DestructionEvent     # Ship destroyed
RepairEvent          # Emergency repair attempt
TurnStartEvent       # Turn begins, force screens regen
TurnEndEvent         # Turn ends, cleanup
```

Each event carries enough data for a UI to display a meaningful description of what happened and why.

---

## 18. File Structure

```
m1_psi_core/
├── __init__.py
├── dice.py                  # DiceRoller, damage parsing, success rolls, contests
├── combat_state.py          # EngagementState, TurnState, RangeBand management
├── chase.py                 # Chase roll resolution, range shifting, escape
├── maneuvers.py             # Maneuver catalog, validation
├── attack.py                # Hit roll calculation, modifier pipeline
├── missile.py               # Missile attack resolution
├── defense.py               # Dodge, missile defense, High-G dodge
├── point_defense.py         # Point defense interception
├── damage.py                # Damage resolution, armor penetration, wound effects, subsystem table
├── electronic_warfare.py    # Detection, stealth, ambush, jamming
├── passengers.py            # Passenger actions, crew skill, internal movement
├── emergency_power.py       # Emergency power allocation options
├── formations.py            # Multi-ship formations, tactical coordination
├── special.py               # Lucky breaks, cinematic injury, hugging, ramming
├── turn_sequence.py         # Turn phases, declaration/resolution orchestration
├── events.py                # All event dataclasses
└── engine.py                # Top-level combat engine that orchestrates everything

tests/
├── conftest.py              # Shared fixtures, seeded DiceRoller, sample combat scenarios
├── test_dice.py             # Dice rolling, damage parsing, success/critical detection
├── test_combat_state.py     # Engagement tracking, range bands, advantage
├── test_chase.py            # Chase roll resolution, range shifting, escape conditions
├── test_maneuvers.py        # Maneuver validation, stall restrictions
├── test_attack.py           # Hit modifier pipeline, all modifier sources
├── test_missile.py          # Missile attack pipeline, air burst, near miss, free missile
├── test_defense.py          # Dodge calculation, High-G, missile defense, jamming
├── test_point_defense.py    # Point defense interception
├── test_damage.py           # Damage pipeline, force screens, armor, wounds, subsystems
├── test_electronic_warfare.py  # Detection, stealth, ambush
├── test_passengers.py       # Passenger actions, crew skill, repairs
├── test_emergency_power.py  # Emergency power options
├── test_formations.py       # Formation rules, tactical coordination
├── test_special.py          # Lucky breaks, cinematic, hugging
├── test_turn_sequence.py    # Full turn resolution, phase ordering
└── test_integration.py      # Multi-turn combat scenarios (Javelin vs Hornet, etc.)
```

---

## 19. Resolved Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | All randomness through DiceRoller class | Enables deterministic testing via seeding/mocking |
| 2 | Event-driven output, not print statements | Decouples rules engine from any specific UI |
| 3 | M1 calls M3 DAL to persist state changes | Clean dependency direction: M1 → M3, never M3 → M1 |
| 4 | Conditional Injury (wound thresholds) as the damage model | Matches the Psi-Wars source material and is already implemented in M3 |
| 5 | Chase rolls as Quick Contests | Per the Psi-Wars vehicular combat rules |
| 6 | Separate missile pipeline from beam pipeline | Missiles use fundamentally different modifiers |
| 7 | Subsystem damage table is in M1, not M3 | It's a rules concern (3d6 roll + cascade logic), not data |

---

## 20. Open Questions for Owner Decision

1. **Vehicular dodge formula**: The Psi-Wars rules reference "the vehicle's dodge" but don't give an explicit formula for vehicular dodge in the Action Vehicular Combat document. Standard GURPS uses Piloting/2 + 3 + Handling, but Psi-Wars may have a different calculation. What formula should we use?

2. **Mook rules scope**: Should we implement mook vehicle rules (simplified damage) from the start, or defer? They'd be useful for large battles with NPC squadrons.

3. **Character point spending**: "Just a Scratch" costs a character point. Should M1 track character point expenditure, or is that outside scope?

4. **Hyperspace escape**: The rules mention hyperspace shunts as an escape condition. Should M1 implement full hyperspace navigation (5-turn route calculation, Navigation rolls), or just treat "hyperspace escape" as a binary event?

5. **Formation size limits**: The rules don't specify a maximum formation size. Should we cap it, or leave it open?

6. **Turn timer**: For a multiplayer web game, declarations need a time limit. Should M1 enforce a declaration timeout, or is that the web layer's concern?
