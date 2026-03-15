"""
NPC Behavior Module for M1 Psi-Core.

Provides AI decision-making for computer-controlled ships. The base
AIPersonality class defines the decision interface; StandardAI implements
the default priority tree. New personality variants (Aggressive, Defensive,
Tactical, Reckless) subclass AIPersonality and override specific methods.

Architecture:
    AIPersonality (abstract base)
    ├── StandardAI         — balanced default behavior
    ├── AggressiveAI       — future: always pursue, liberal emergency power
    ├── DefensiveAI        — future: prefer evade, disengage when damaged
    ├── TacticalAI         — future: formation tactics, coordinated attacks
    └── RecklessAI         — future: mook behavior, charge/ram, never retreat

The AI operates purely on SituationAssessment data. It never accesses
the display layer or the database directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# AI Decision Output
# ---------------------------------------------------------------------------

@dataclass
class AIDecision:
    """Complete decision for one NPC ship's turn."""
    target_id: Optional[str]        # Who to engage
    maneuver: str                    # Chosen maneuver
    intent: str                      # "pursue" or "evade"
    use_afterburner: bool = False
    force_screen_facing: Optional[str] = None
    deceptive_levels: int = 0
    targeted_system: Optional[str] = None
    use_emergency_power: Optional[str] = None
    fire_missile: bool = False
    fire_torpedo: bool = False
    use_lucky_break: bool = False
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Ship Situation Assessment
# ---------------------------------------------------------------------------

@dataclass
class SituationAssessment:
    """Assessment of a ship's current tactical situation."""
    ship_id: str
    current_hp_pct: float
    has_force_screen: bool
    force_screen_pct: float
    wound_level: str
    is_crippled: bool
    has_stall_speed: bool
    stall_speed: int
    has_advantage: bool
    has_matched_speed: bool
    opponent_has_advantage: bool
    range_band: str
    own_speed: int
    opponent_speed: int
    is_faster: bool
    has_missiles: bool
    has_torpedoes: bool
    effective_skill: int
    force_screen_depleted: bool
    systems_damaged: list[str] = field(default_factory=list)


def assess_situation(
    ship_id: str,
    ship_stats,
    engagement,
    opponent_stats=None,
) -> SituationAssessment:
    """
    Assess a ship's tactical situation for AI decision-making.

    Accepts either MockShipStats or EffectiveStatBlock — uses duck typing.
    """
    hp_pct = ship_stats.current_hp / max(ship_stats.st_hp, 1)
    has_screen = ship_stats.fdr_max > 0
    screen_pct = ship_stats.current_fdr / max(ship_stats.fdr_max, 1) if has_screen else 0.0

    wound = getattr(ship_stats, "wound_level", "none")
    is_crippled = wound in ("crippling", "mortal", "lethal")

    has_advantage = engagement.advantage == ship_id
    opponent_id = (engagement.ship_b_id
                   if engagement.ship_a_id == ship_id
                   else engagement.ship_a_id)
    opponent_has_adv = engagement.advantage == opponent_id

    own_speed = ship_stats.top_speed
    opp_speed = opponent_stats.top_speed if opponent_stats else 0

    has_missiles = False
    has_torpedoes = False
    for w in getattr(ship_stats, "weapons", []):
        wtype = (getattr(w, "weapon_type", "")
                 if hasattr(w, "weapon_type")
                 else w.get("weapon_type", ""))
        if wtype == "missile":
            has_missiles = True
        elif wtype == "torpedo":
            has_torpedoes = True

    effective_skill = 14

    systems_damaged = []
    if ship_stats.half_power:
        systems_damaged.append("power_disabled")
    if ship_stats.no_power:
        systems_damaged.append("power_destroyed")

    return SituationAssessment(
        ship_id=ship_id,
        current_hp_pct=hp_pct,
        has_force_screen=has_screen,
        force_screen_pct=screen_pct,
        wound_level=wound,
        is_crippled=is_crippled,
        has_stall_speed=ship_stats.stall_speed > 0,
        stall_speed=ship_stats.stall_speed,
        has_advantage=has_advantage,
        has_matched_speed=engagement.matched_speed and has_advantage,
        opponent_has_advantage=opponent_has_adv,
        range_band=engagement.range_band,
        own_speed=own_speed,
        opponent_speed=opp_speed,
        is_faster=own_speed > opp_speed,
        has_missiles=has_missiles,
        has_torpedoes=has_torpedoes,
        effective_skill=effective_skill,
        force_screen_depleted=has_screen and ship_stats.current_fdr == 0,
        systems_damaged=systems_damaged,
    )


# ---------------------------------------------------------------------------
# Range helpers
# ---------------------------------------------------------------------------

_RANGE_ORDER = [
    "close", "short", "medium", "long", "extreme",
    "distant", "beyond_visual", "remote", "beyond_remote",
]
_GOOD_WEAPON_RANGES = {"close", "short", "medium", "long"}
_MISSILE_RANGES = {"extreme", "distant"}


def _is_good_weapon_range(band: str) -> bool:
    return band in _GOOD_WEAPON_RANGES

def _is_missile_range(band: str) -> bool:
    return band in _MISSILE_RANGES

def _range_index(band: str) -> int:
    return _RANGE_ORDER.index(band)

def _is_far_range(band: str) -> bool:
    return _range_index(band) >= _RANGE_ORDER.index("extreme")


# ---------------------------------------------------------------------------
# AI Personality Base Class
# ---------------------------------------------------------------------------

class AIPersonality(ABC):
    """
    Base class for NPC AI personalities.

    Subclass this and override individual check_* methods to create
    new behavior variants. The decide() method walks the priority chain
    and returns the first non-None result.

    To create a new personality:
        class AggressiveAI(AIPersonality):
            def check_retreat(self, sit): return None  # Never retreat
            def check_no_advantage_slower(self, sit):
                return self._make("move_and_attack", "pursue",
                    reasoning="Aggressive — charging in regardless.")
    """

    def decide(self, situation: SituationAssessment, is_mook: bool = False) -> AIDecision:
        """
        Walk the priority chain and return the first applicable decision.

        Override individual check_* methods in subclasses, not this method.
        """
        checks = [
            self.check_retreat,
            self.check_stall_escape,
            self.check_matched_speed_attack,
            self.check_advantaged_attack,
            self.check_advantaged_close_distance,
            self.check_no_advantage_faster,
            self.check_no_advantage_slower,
            self.check_missile_range,
            self.check_depleted_screen,
            self.check_far_range,
            self.check_default,
        ]

        for check in checks:
            result = check(situation)
            if result is not None:
                return result

        # Should never reach here — check_default always returns something
        return self._make("move_and_attack", "pursue", reasoning="Fallback.")

    # --- Priority methods (override these in subclasses) ---

    def check_retreat(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 1: Critically damaged — attempt escape."""
        if sit.is_crippled:
            return self._make("evade", "evade",
                              reasoning="Critically damaged — attempting to escape.")
        return None

    def check_stall_escape(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 2: Stall speed + opponent has advantage."""
        if sit.has_stall_speed and sit.opponent_has_advantage:
            return self._make("stunt_escape", "evade",
                              reasoning="Stall speed and opponent has advantage — stunt escape.")
        return None

    def check_matched_speed_attack(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 3: Have matched speed — press the attack."""
        if sit.has_matched_speed:
            maneuver = "attack" if not sit.has_stall_speed else "move_and_attack"
            return self._make(maneuver, "pursue",
                              deceptive_levels=self._calc_deceptive(sit),
                              reasoning="Matched speed — pressing the attack for maximum accuracy.")
        return None

    def check_advantaged_attack(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 4: Have advantage at good weapon range."""
        if sit.has_advantage and _is_good_weapon_range(sit.range_band):
            maneuver = "attack" if not sit.has_stall_speed else "move_and_attack"
            return self._make(maneuver, "pursue",
                              deceptive_levels=self._calc_deceptive(sit),
                              reasoning="Advantaged at weapon range — attacking.")
        return None

    def check_advantaged_close_distance(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 5: Have advantage but too far."""
        if sit.has_advantage and _is_far_range(sit.range_band):
            return self._make("move", "pursue",
                              reasoning="Advantaged but too far — closing distance.")
        return None

    def check_no_advantage_faster(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 6: No advantage, faster ship."""
        if not sit.has_advantage and sit.is_faster:
            # At weapon range: attack while using speed advantage
            if _is_good_weapon_range(sit.range_band):
                return self._make("move_and_attack", "pursue",
                                  reasoning="Faster at weapon range — attacking while maneuvering.")
            return self._make("mobility_pursuit", "pursue",
                              reasoning="Faster than opponent — using speed to close distance.")
        return None

    def check_no_advantage_slower(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 7: No advantage, slower or equal ship."""
        if not sit.has_advantage and not sit.is_faster:
            # At weapon range: attack rather than stunt forever
            if _is_good_weapon_range(sit.range_band):
                return self._make("move_and_attack", "pursue",
                                  reasoning="At weapon range — engaging with Move and Attack.")
            # Far range: stunt to try for advantage before closing
            return self._make("stunt", "pursue",
                              reasoning="Slower than opponent — attempting a stunt to gain advantage.")
        return None

    def check_missile_range(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 8: At missile range with missiles available."""
        if _is_missile_range(sit.range_band) and sit.has_missiles:
            return self._make("move_and_attack", "pursue", fire_missile=True,
                              reasoning="At missile range — firing missiles while closing.")
        return None

    def check_depleted_screen(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 9: Force screen depleted — evade to let it regen."""
        if sit.force_screen_depleted:
            return self._make("evade", "evade",
                              reasoning="Force screen depleted — evading to allow regeneration.")
        return None

    def check_far_range(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Priority 10: Far range — close distance."""
        if _is_far_range(sit.range_band):
            return self._make("move", "pursue",
                              reasoning="Out of weapon range — closing distance.")
        return None

    def check_default(self, sit: SituationAssessment) -> Optional[AIDecision]:
        """Default fallback: Move and Attack."""
        return self._make("move_and_attack", "pursue",
                          reasoning="Standard engagement — move and attack.")

    # --- Helpers ---

    def _calc_deceptive(self, sit: SituationAssessment) -> int:
        """Calculate deceptive attack levels. Override for different aggression."""
        if sit.effective_skill >= 14:
            return 1
        return 0

    @staticmethod
    def _make(
        maneuver: str,
        intent: str,
        reasoning: str = "",
        deceptive_levels: int = 0,
        fire_missile: bool = False,
        fire_torpedo: bool = False,
        use_afterburner: bool = False,
        force_screen_facing: Optional[str] = None,
        use_emergency_power: Optional[str] = None,
        use_lucky_break: bool = False,
    ) -> AIDecision:
        """Convenience factory for building AIDecision objects."""
        return AIDecision(
            target_id=None,
            maneuver=maneuver,
            intent=intent,
            reasoning=reasoning,
            deceptive_levels=deceptive_levels,
            fire_missile=fire_missile,
            fire_torpedo=fire_torpedo,
            use_afterburner=use_afterburner,
            force_screen_facing=force_screen_facing,
            use_emergency_power=use_emergency_power,
            use_lucky_break=use_lucky_break,
        )


# ---------------------------------------------------------------------------
# Standard AI (default personality)
# ---------------------------------------------------------------------------

class StandardAI(AIPersonality):
    """
    Balanced NPC AI personality. Uses all default priority methods.

    This is the default AI for all NPC ships. It plays competently
    but conservatively — it won't do anything brilliant or reckless.
    """
    pass  # All behavior inherited from AIPersonality defaults


# ---------------------------------------------------------------------------
# Backward-compatible function interface
# ---------------------------------------------------------------------------

_standard_ai = StandardAI()


def decide_standard(
    situation: SituationAssessment,
    is_mook: bool = False,
) -> AIDecision:
    """
    Standard NPC AI decision (function interface).

    Delegates to StandardAI.decide(). This function exists for backward
    compatibility and for use cases where a class instance isn't needed.
    """
    return _standard_ai.decide(situation, is_mook=is_mook)


# ---------------------------------------------------------------------------
# Target Selection
# ---------------------------------------------------------------------------

@dataclass
class TargetCandidate:
    """A potential target for an NPC ship."""
    ship_id: str
    range_band: str
    hp_pct: float
    is_targeting_ally: bool
    ship_class: str


def select_target(
    own_ship_id: str,
    own_class: str,
    current_target_id: Optional[str],
    candidates: list[TargetCandidate],
) -> Optional[str]:
    """
    Select the best target from available enemies.

    Priority:
    1. Continue engaging current target (if still valid)
    2. Threats targeting our allies
    3. Weakened ships
    4. Closest range
    5. Class-appropriate targets
    """
    if not candidates:
        return None

    if current_target_id:
        for c in candidates:
            if c.ship_id == current_target_id:
                return current_target_id

    scored = []
    for c in candidates:
        score = 0.0
        if c.is_targeting_ally:
            score += 50
        score += (1.0 - c.hp_pct) * 30
        range_idx = _range_index(c.range_band)
        score += max(0, 20 - range_idx * 3)
        if c.ship_class == own_class:
            score += 10
        scored.append((score, c.ship_id))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


# ---------------------------------------------------------------------------
# Chase Outcome Decision
# ---------------------------------------------------------------------------

def choose_chase_outcome(
    can_gain_advantage: bool,
    can_match_speed: bool,
    can_shift_range: int,
    currently_advantaged: bool,
    current_range: str,
    intent: str,
) -> str:
    """
    Choose what to do with a chase victory.

    Returns: "advantage", "match_speed", "shift_close", "shift_far", "no_action"
    """
    if can_match_speed and currently_advantaged:
        return "match_speed"
    if can_gain_advantage and not currently_advantaged:
        return "advantage"
    if can_shift_range > 0 and intent == "pursue":
        return "shift_close"
    if can_shift_range > 0 and intent == "evade":
        return "shift_far"
    if can_gain_advantage:
        return "advantage"
    return "no_action"


# ---------------------------------------------------------------------------
# Emergency Power Decision
# ---------------------------------------------------------------------------

def decide_emergency_power(
    situation: SituationAssessment,
    reserves_remaining: int,
) -> Optional[str]:
    """
    Decide whether to use emergency power and which option.

    Returns the option name or None.
    """
    if reserves_remaining <= 0:
        return None

    if situation.force_screen_depleted and situation.has_force_screen:
        return "emergency_screen_recharge"

    if situation.opponent_has_advantage and not situation.is_crippled:
        return "all_power_to_engines"

    return None


# ---------------------------------------------------------------------------
# High-G dodge decision making
# ---------------------------------------------------------------------------

def should_attempt_high_g(
    current_fp: int,
    max_fp: int,
    wound_level: str,
    attacker_margin: int,
) -> bool:
    """
    Decide whether an NPC should attempt a High-G dodge.

    Weighs FP cost risk against threat level:
    - Healthy with FP: always attempt (the +1 dodge is worth it)
    - Low FP: skip unless desperate
    - Badly wounded: always attempt (survival matters more than FP)

    Args:
        current_fp: Current fatigue points.
        max_fp: Maximum fatigue points.
        wound_level: Current wound level.
        attacker_margin: Attacker's margin of success (higher = scarier).
    """
    from m1_psi_core.damage import WOUND_SEVERITY

    wound_sev = WOUND_SEVERITY.get(wound_level, 0)
    fp_ratio = current_fp / max(max_fp, 1)

    # Desperate: badly wounded, always try
    if wound_sev >= WOUND_SEVERITY.get("crippling", 4):
        return True

    # High threat: big attack margin, worth the risk
    if attacker_margin >= 5 and current_fp >= 2:
        return True

    # Healthy with FP to spare: attempt
    if fp_ratio > 0.3:
        return True

    # Low FP, minor threat: conserve energy
    return False


# ---------------------------------------------------------------------------
# NPC Weapon Selection
# ---------------------------------------------------------------------------

def select_best_weapon(
    weapons: list,
    range_band: str,
    attacker_facing: str,
    has_stall_speed: bool,
    won_chase: bool,
) -> int:
    """
    Select the best weapon index for an NPC to fire.

    Priority:
    1. Weapon must be in range
    2. Weapon must be able to fire given current facing
    3. Weapon must pass stall speed restriction
    4. Among valid weapons, pick highest expected damage

    Args:
        weapons: List of WeaponInfo objects.
        range_band: Current engagement range band.
        attacker_facing: Attacker's current facing ("front", "rear", "any").
        has_stall_speed: Whether the ship has a stall speed.
        won_chase: Whether the ship won the chase this turn.

    Returns:
        Index of the best weapon, or 0 as fallback.
    """
    from m1_psi_core.engine import is_weapon_in_range, can_weapon_fire_facing, check_stall_attack_restriction

    best_idx = 0
    best_score = -1

    for i, w in enumerate(weapons):
        # Filter: range check
        if w.range_str and not is_weapon_in_range(w.range_str, range_band):
            continue

        # Filter: facing check
        if not can_weapon_fire_facing(w.mount, attacker_facing):
            continue

        # Filter: stall speed restriction
        if not check_stall_attack_restriction(has_stall_speed, won_chase, w.mount):
            continue

        # Score: estimate damage output
        # Parse the multiplier from damage string for a rough score
        score = w.rof * 10  # Higher ROF = more hits
        # Bonus for high accuracy
        score += w.acc
        # Bonus for armor divisor (better penetration)
        if w.armor_divisor and w.armor_divisor > 1:
            score += w.armor_divisor * 2
        # Bonus for explosive (area damage)
        if w.is_explosive:
            score += 5

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx
