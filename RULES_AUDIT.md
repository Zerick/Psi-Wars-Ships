# RULES AUDIT — Psi-Wars Combat Simulator v0.11
## Comparing Implementation Against Rules As Written (RAW)

Audit Date: 2026-03-15
Source Documents:
- Psi-Wars: Action Vehicular Combat (primary authority)
- GURPS Action 2: Exploits Chase Rules
- GURPS Combat Maneuvers Cheat Sheet 2.04
- GURPS 4e Lite 2020

---

## 1. RANGE BAND TABLE

### RAW:
| Band | Range Penalty |
|------|--------------|
| Close | -0 to -2 (apply Bulk penalty) |
| Short | -3 to -6 |
| Medium | -7 to -10 |
| Long | -11 to -14 |
| Extreme | -15 to -18 |
| Distant | -19 to -22 |
| Beyond Visual | -23 or more |
| Remote | -27 or more (special) |

RAW says: "Use the low range penalty for all ranged attacks."

### Our Implementation (combat_state.py):
Uses the LOW end of each range band for the penalty.

### VERDICT: ✅ CORRECT (assuming we use the low end)
**ACTION NEEDED:** Verify exact values in get_range_penalty(). Should be:
Close=-0, Short=-3, Medium=-7, Long=-11, Extreme=-15, Distant=-19.
Also: we're missing Beyond Visual (-23) and Remote (-27) range bands.

---

## 2. CHASE ROLLS

### RAW:
"Chase Rolls meet in a Quick Contest."
- Victory by 0-4: No change. Opponent loses advantage if they had it. Pursuing stall-speed craft must succeed by 0+ to attack with fixed weapons.
- Victory by 5-9: Gain advantage OR shift 1 range band. If already advantaged, may Match Speed.
- Victory by 10+: Match Speed, OR shift 1 band + gain advantage (unless already advantaged → match speed), OR shift 2 bands.

### Our Implementation (chase.py):
resolve_chase_outcome() returns options based on margin.

### VERDICT: ⚠️ PARTIALLY CORRECT
**ISSUES FOUND:**
1. **Victory by 0-4**: We strip opponent's advantage. ✅ Correct.
   BUT: "Pursuing stall-speed craft must succeed by 0+ to attack with fixed weapons" — we DON'T check this. A stall-speed ship that loses the chase contest cannot fire fixed weapons that turn. **BUG.**
2. **Victory by 5-9**: We offer advantage OR 1-band shift. ✅ Correct.
   Match Speed offered if already advantaged. ✅ Correct.
3. **Victory by 10+**: RAW says you can do Match Speed, OR (1 shift + advantage), OR 2 shifts. Need to verify our options match this exactly.

---

## 3. CHASE SKILL CALCULATION

### RAW:
Chase roll is a Quick Contest of the relevant driving/piloting skill with modifiers from the maneuver chosen. No explicit mention of adding Handling to the chase roll in the Psi-Wars rules — Handling affects dodge only.

### Our Implementation:
`skill = Piloting + Handling + maneuver.chase_modifier`

### VERDICT: ⚠️ NEEDS VERIFICATION
**ISSUE:** The RAW says the chase roll is Piloting + maneuver modifier. Handling is described as affecting dodge (vehicular dodge = Piloting/2 + Handling). Adding Handling to the chase roll may be a houserule or may come from the base GURPS Action 2 rules (which we don't have the full text of). The Psi-Wars text doesn't explicitly state Handling adds to chase rolls.

**RECOMMENDATION:** Ask the game owner to confirm whether Handling applies to chase rolls or only to dodge. This significantly affects balance — ships with high Handling (Hornet +6) would be much better at chasing than ships with low Handling.

---

## 4. MANEUVER DEFINITIONS

### RAW vs Implementation:

| Maneuver | RAW Chase Mod | RAW Facing | RAW Attack | Our Chase Mod | Our Facing | Our Attack |
|----------|--------------|------------|------------|---------------|------------|------------|
| Attack | 0 | F | Full Acc | ? | ? | ? |
| Evade | -2 | B | None | ? | ? | ? |
| Move | 0 | F or B | None | ? | ? | ? |
| Move and Attack | 0 (no -2!) | F | Half Acc | ? | ? | ? |
| Stunt | +2 | Any | w/o Acc (Ace) | ? | ? | ? |
| Stunt Escape | +2 | Any | w/o Acc (Ace) | ? | ? | ? |
| Mobility Pursuit | 0 | F | w/o Acc (Ace) | ? | ? | ? |
| Mobility Escape | 0 | B | w/o Acc (Ace) | ? | ? | ? |
| Hide | 0 | Any | None | ? | ? | ? |

### CRITICAL RAW NOTE:
"Move and Attack: Do not apply the -2 to the chase roll unless the driver of the vehicle is attacking with a side-arm, rather than using the vehicle itself to attack."

This means Move and Attack has NO chase penalty when using vehicle weapons. Only personal sidearms get -2.

### VERDICT: ⚠️ NEEDS LINE-BY-LINE AUDIT of maneuvers.py
**KEY CONCERN:** Is Move and Attack correctly getting 0 chase penalty?
**KEY CONCERN:** Attack maneuver — "Vehicles with a stall speed may not Attack." We implement this. ✅
**KEY CONCERN:** Stall speed ships can't Stunt against vehicles with Advantage against them. Need to verify.

---

## 5. ATTACK MODIFIERS

### RAW:
- Base: Gunner (Blaster) skill
- Range penalty: Use highest of |range penalty|, own speed penalty, opponent's speed penalty
- SM bonus: Target's SM
- Sensor Lock: +3 (or +5 with targeting computer)
- Accuracy: Full Acc on Attack maneuver; Half Acc on Move and Attack; No Acc on Stunt/Mobility/etc.
- Matched Speed: "Use the higher of the absolute value of the range penalty or your Stall Speed as your Range/Speed penalty. You may add accuracy even on Move and Attack."
- Relative Size: Fighter vs Corvette: -5. Corvette vs Fighter: no penalty. Capital vs Corvette: -5. Capital vs Fighter: -10. Halved for "light turret."
- Deceptive Attack: Allowed! -2 to hit per -1 to target's defense.
- ROF bonus: Standard GURPS Rapid Fire table (B373). ROF 5-8: +1, 9-12: +2, etc. Linked weapons double ROF, increasing the bonus. ✅ CORRECT.

### Our Implementation:
- Base skill ✅
- Range penalty ✅ (but we only check range band, not speed)
- SM bonus ✅
- Sensor Lock: We use +5 with targeting computer. Need to check if +3 without.
- Accuracy: We apply half Acc for Move and Attack.
- Matched Speed accuracy: **NOT IMPLEMENTED** — Matched Speed should grant full Acc on Move and Attack.
- Relative Size: We implement fighter/corvette/capital tiers.
- ROF bonus: We add a to-hit bonus for high ROF.

### VERDICT: ⚠️ SEVERAL ISSUES
**BUGS:**
1. **Speed penalty not used in range calculation.** RAW says use highest of range penalty, own speed, opponent speed. We only use range. At close range with fast ships, speed should dominate.
2. **Matched Speed doesn't grant full accuracy on Move and Attack.** This is a significant omission — Matched Speed is supposed to make Move and Attack equivalent to Attack for accuracy purposes.
3. **ROF bonus is non-RAW.** GURPS doesn't add ROF to hit for vehicle weapons. ROF determines how many hits you get, not your to-hit bonus. However, the Psi-Wars rules note "double ROF (+1 to hit)" for linked weapons, so there IS a linked weapon bonus. We should use +1 for linked (not ROF-based bonus).
4. **Sensor lock should be +3 base, +5 with targeting computer.** Need to verify we're distinguishing these.

---

## 6. DEFENSE (DODGE)

### RAW:
"Vehicular Dodge = Piloting/2 + Handling" (this is standard GURPS vehicular dodge)

Modifiers:
- Evade maneuver: +2 to dodge
- Advantaged + escaping: +1 to all defense rolls
- Ace Pilot + Stunt maneuver: +1 to first vehicular dodge
- High-G dodge: +1 (requires accel 40+ or Move 400+, HT roll, FP cost on failure)
- Precision Aiming awareness: +2 to dodge (if attacker used Precision Aiming)

### Our Implementation:
- Base dodge = Piloting/2 + Handling ✅
- Evade +2 ✅
- Advantage escaping +1 ✅
- Ace Pilot stunt +1 ✅
- High-G +1 ✅
- Precision Aiming +2 — tracked but not wired (no Precision Aiming maneuver in UI yet)

### VERDICT: ✅ MOSTLY CORRECT
**MINOR:** The +3 base dodge from standard GURPS (Basic Speed contributes +3 to dodge) — in vehicular combat, this is replaced by Piloting/2 + Handling. We do this correctly. No +3 base. ✅

---

## 7. CRITICAL HITS

### RAW (GURPS B381):
A critical hit on the attack roll means the target gets no defense at all.

### Our Implementation:
We now skip defense on critical hits (v0.11). ✅

### VERDICT: ✅ CORRECT

---

## 8. DAMAGE PIPELINE

### RAW (Conditional Injury):
- Scratch: <10% HP — ignore entirely
- Minor: 10-50% HP — noticeable damage, can accumulate
- Major: 50-100% HP — disable one system, accumulates
- Crippling: 100-200% HP — destroy one system, HT roll to remain operational, accumulates
- Mortal: 200-500% HP — destroy one system, HT roll or destroyed, accumulates
- Lethal: >500% HP — instantly destroyed

### Our Implementation:
determine_wound_level() calculates based on penetrating damage vs HP.

### VERDICT: ⚠️ NEEDS VERIFICATION
**ISSUES:**
1. **Wound accumulation not implemented.** RAW says: "Roll HT once per additional wound; on a failure, increase wound severity by one." We track wound level but don't roll HT for accumulation. Repeated minor wounds should eventually escalate to major.
2. **HT roll to remain operational on Crippling.** RAW says crippling wounds require an HT roll or the ship is reduced to minimum systems. We don't do this.
3. **Mortal wound HT roll.** RAW says mortal wound = destroy system + HT roll or destroyed. We don't roll HT.
4. **"If HT roll to resist accumulation succeeds by margin of 0 and the ship has a wound level that disables/destroys a system, disable/destroy a second system."** Not implemented.

---

## 9. FORCE SCREENS

### RAW:
- DR is hardened 1 and ablative
- Against plasma/plasma lance/shaped charge: Force screens ignore ALL armor divisors AND eliminate the armor divisor for armor underneath
- Heavy Force Screens (optional): ignore all armor divisors from all attacks
- Recover full DR between chase turns

### Our Implementation:
apply_force_screen() handles ablative damage.

### VERDICT: ⚠️ SIGNIFICANT ISSUES
**BUGS:**
1. **Armor divisor interaction with force screens.** RAW says force screens are "hardened 1" which means armor divisors are reduced by one step (e.g., AD 5 becomes AD 3, AD 3 becomes AD 2, AD 2 becomes AD 1). We may be applying the full armor divisor to force screens.
2. **Plasma/shaped charge special rule.** Force screens should completely negate armor divisors for plasma weapons, and the armor underneath also loses its armor divisor benefit. This is a major rule for Psi-Wars since most weapons are plasma.
3. **Heavy Force Screen optional rule.** Capital ship screens should ignore ALL armor divisors. Important for capital ship combat balance.

---

## 10. SUBSYSTEM DAMAGE

### RAW:
"If a vehicle suffers 50% or more damage from a single attack, a system is damaged or disabled."

The trigger is 50% HP from a SINGLE attack — this is a Major wound. We use Conditional Injury thresholds which align with this.

### RAW Subsystem Table (3d):
3: Fuel → cascades to Power
4: Habitat → cascades to Cargo
5: Propulsion → cascades to Weaponry
...
(table repeats at 10-18 offset by 7)

### RAW Cascade Rule:
"If a system has already been disabled, roll against HT; on failure, it is destroyed and the vehicle suffers a Crippling Wound. If HT succeeds or subsystem is already destroyed, damage cascades to the noted subsystem."

### Our Implementation:
get_subsystem_hit() returns a system and cascade target. But we don't implement the HT roll for already-disabled systems or the cascade mechanic.

### VERDICT: ⚠️ PARTIALLY CORRECT
**MISSING:**
1. **Cascade mechanic**: When a hit system is already disabled, HT roll → failure destroys it + crippling wound. Success → cascade to next system.
2. **Already-destroyed cascade**: If system is already destroyed, cascade immediately.
3. **Targeted system attacks**: -5 to hit, bypass the random roll.

---

## 11. RELATIVE SIZE PENALTIES

### RAW:
"If a corvette fires at a fighter, apply a -5 to hit. If a capital ship fires on a corvette, apply a -5 to hit; if a capital ship fires at a fighter, apply a -10 to hit! Halve these penalties (rounded down!) if the weapon is noted as 'light turret.'"

Fighter: SM +4 to +7 (or chase +16 or better)
Corvette: SM +7 to +10 (or chase +11 to +15)
Capital: SM +10 or larger (or chase +10 or worse)

Note: The penalty only applies DOWNWARD. A fighter firing at a capital ship gets NO penalty. A corvette firing at a capital ship gets NO penalty.

### Our Implementation:
classify_ship() and get_relative_size_penalty() in special.py.

### VERDICT: ⚠️ NEEDS VERIFICATION
**CONCERN:** Verify the penalty is one-directional (larger firing at smaller = penalty, smaller firing at larger = no penalty). Also verify the "light turret" halving.

---

## 12. SENSOR LOCK AND TARGETING

### RAW:
"+3 to all attack rolls if you have a sensor lock. Increase this bonus to +5 if you have a targeting computer."

"Sensor locks are assumed to be automatic if your vehicle has an Ultrascanner and your target is within range unless your target actively resists with Electronics Operation (ECM)."

### Our Implementation:
get_sensor_lock_bonus(has_lock, targeting_bonus) — we pass the ship's targeting_bonus directly.

### VERDICT: ⚠️ NEEDS FIX
**ISSUE:** The bonus should be +3 (basic sensor lock) or +5 (with targeting computer), not the ship's raw targeting_bonus value. Some ships have targeting_bonus: 5 in their JSON (which is correct for a ship WITH targeting computer), but the function should distinguish between "has targeting computer" (+5) and "basic sensor lock" (+3), not pass through an arbitrary number.

---

## 13. MATCHED SPEED ATTACK RULES

### RAW:
"Matched Speed includes the benefits of Advantaged; Additionally, instead of using the Range (and Speed) modifier below, use the higher of the absolute value of the range penalty or your Stall Speed as your Range/Speed penalty. Finally, you may add accuracy to your attack even if making a Move and Attack."

### Our Implementation:
We track matched speed but don't implement the special attack rules.

### VERDICT: ❌ NOT IMPLEMENTED
**SIGNIFICANT GAMEPLAY IMPACT:** Matched Speed is supposed to be the payoff for gaining advantage twice. It grants full accuracy on Move and Attack, which is a massive bonus. Without this, there's little incentive to match speed.

---

## 14. FACING AND FIXED WEAPONS

### RAW:
- Pursuing = Front facing toward opponent
- Evading = Back facing toward opponent
- Fixed mount weapons must have proper facing to fire
- Advantaged attackers may choose which facing to attack
- Non-advantaged attackers hit the facing the opponent declared

### Our Implementation:
Facing is tracked on maneuvers but not enforced for weapon firing or DR selection.

### VERDICT: ❌ NOT ENFORCED
**IMPACT:** Ships with fixed front weapons should not be able to fire while evading (back facing toward opponent). We allow all weapons to fire regardless of facing. Also, advantage should let you choose which facing of the opponent you hit (e.g., attacking the weak rear armor).

---

## 15. MOVE AND ATTACK CHASE PENALTY

### RAW:
"Do not apply the -2 to the chase roll unless the driver of the vehicle is attacking with a side-arm, rather than using the vehicle itself to attack."

### Our Implementation:
Need to verify — Move and Attack should have 0 chase penalty for vehicle weapons.

### VERDICT: ⚠️ NEEDS VERIFICATION in maneuvers.py

---

## SUMMARY OF FINDINGS

### Critical Bugs (affect combat correctness):
1. **Matched Speed doesn't grant full accuracy on Move and Attack** — major incentive broken
2. **Force screen hardened DR / armor divisor interaction wrong** — affects all damage calculations for shielded ships
3. **Wound accumulation not implemented** — repeated minor/major wounds should escalate
4. **Speed penalty not factored into range calculation** — matters at close range with fast ships
5. **Facing not enforced** — fixed weapons fire in wrong direction, wrong DR applied

### Moderate Issues (affect balance/correctness):
6. Sensor lock bonus should be +3/+5, not arbitrary
8. Subsystem cascade mechanic not implemented
9. HT roll on crippling/mortal wounds not implemented
10. Stall speed chase attack restriction not checked
11. Chase skill may incorrectly include Handling

### Minor/Cosmetic:
12. Beyond Visual and Remote range bands not implemented
13. Precision Aiming maneuver not in UI
14. Targeted system attacks (-5 to hit) not in UI
15. Light turret halving of relative size penalty not tracked

### Working Correctly:
- Base vehicular dodge formula ✅
- Evade +2 dodge bonus ✅
- High-G dodge mechanics ✅
- Critical hit skips defense ✅
- Subsystem damage tracking and basic effects ✅
- Ship destruction on lethal wound or HP ≤ 0 ✅
- Force screen ablative damage (basic) ✅
- Chase outcome options (victory by 0-4, 5-9, 10+) ✅
- Mook vehicle rules ✅
