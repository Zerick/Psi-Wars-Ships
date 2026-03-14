"""
Tests for the dice subsystem.

Covers:
- 3d6 rolling and seeding
- Nd6 rolling
- Damage string parsing (all formats found in weapon catalog)
- Success roll resolution with margins
- Critical success detection
- Critical failure detection
- Quick contest resolution
- Minimum skill rule
"""
import pytest


class TestDiceRolling:
    """Basic dice rolling mechanics."""

    def test_roll_3d6_range(self):
        """3d6 always produces values between 3 and 18."""
        from m1_psi_core.dice import DiceRoller
        roller = DiceRoller(seed=42)
        results = [roller.roll_3d6() for _ in range(1000)]
        assert min(results) >= 3
        assert max(results) <= 18

    def test_roll_3d6_deterministic(self):
        """Same seed produces same sequence."""
        from m1_psi_core.dice import DiceRoller
        roller1 = DiceRoller(seed=123)
        roller2 = DiceRoller(seed=123)
        seq1 = [roller1.roll_3d6() for _ in range(20)]
        seq2 = [roller2.roll_3d6() for _ in range(20)]
        assert seq1 == seq2

    def test_roll_nd6(self):
        """roll_nd6 produces values in the correct range."""
        from m1_psi_core.dice import DiceRoller
        roller = DiceRoller(seed=42)
        for n in [1, 2, 4, 6, 10]:
            results = [roller.roll_nd6(n) for _ in range(100)]
            assert min(results) >= n
            assert max(results) <= n * 6

    def test_roll_1d6_range(self):
        """1d6 produces values between 1 and 6."""
        from m1_psi_core.dice import DiceRoller
        roller = DiceRoller(seed=42)
        results = [roller.roll_1d6() for _ in range(200)]
        assert min(results) >= 1
        assert max(results) <= 6


class TestDamageStringParsing:
    """Parsing GURPS damage strings into structured components."""

    def test_parse_simple_multiplier(self):
        """'6d×5(5) burn' -> 6 dice, x5 multiplier, AD 5, burn."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("6d×5(5) burn")
        assert result.dice == 6
        assert result.multiplier == 5
        assert result.adds == 0
        assert result.armor_divisor == 5
        assert result.damage_type == "burn"
        assert result.explosive is False

    def test_parse_explosive(self):
        """'5d×200 cr ex' -> 5 dice, x200, no AD, crushing explosive."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("5d×200 cr ex")
        assert result.dice == 5
        assert result.multiplier == 200
        assert result.armor_divisor is None
        assert result.damage_type == "cr"
        assert result.explosive is True

    def test_parse_burn_ex_with_divisor(self):
        """'6d×30(2) burn ex' -> 6 dice, x30, AD 2, burn explosive."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("6d×30(2) burn ex")
        assert result.dice == 6
        assert result.multiplier == 30
        assert result.armor_divisor == 2
        assert result.explosive is True

    def test_parse_no_multiplier(self):
        """'12d burn' -> 12 dice, x1 multiplier, no AD."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("12d burn")
        assert result.dice == 12
        assert result.multiplier == 1
        assert result.armor_divisor is None

    def test_parse_toxic(self):
        """'4d tox' -> 4 dice, toxic damage."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("4d tox")
        assert result.dice == 4
        assert result.damage_type == "tox"

    def test_parse_cutting_incendiary(self):
        """'5d×15(10) cut inc' -> cutting incendiary."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("5d×15(10) cut inc")
        assert result.dice == 5
        assert result.multiplier == 15
        assert result.armor_divisor == 10
        assert result.damage_type == "cut"

    def test_parse_zero_damage(self):
        """'0' -> zero damage (tractor beams)."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("0")
        assert result.dice == 0
        assert result.multiplier == 0

    def test_parse_with_unicode_multiply(self):
        """Handles both × and x as multiplier symbols."""
        from m1_psi_core.dice import parse_damage_string
        r1 = parse_damage_string("6d×5(5) burn")
        r2 = parse_damage_string("6dx5(5) burn")
        assert r1.dice == r2.dice
        assert r1.multiplier == r2.multiplier

    def test_parse_surge_damage(self):
        """'6d×75(5) sur' -> surge damage type."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("6d×75(5) sur")
        assert result.damage_type == "sur"

    def test_parse_fractional_armor_divisor(self):
        """'10d(0.5) burn' -> AD 0.5 means double DR."""
        from m1_psi_core.dice import parse_damage_string
        result = parse_damage_string("10d(0.5) burn")
        assert result.armor_divisor == 0.5

    def test_roll_damage(self):
        """roll_damage produces correct range for known damage string."""
        from m1_psi_core.dice import DiceRoller
        roller = DiceRoller(seed=42)
        # "6d×5(5) burn" -> roll 6d6 (range 6-36), multiply by 5 -> range 30-180
        result = roller.roll_damage("6d×5(5) burn")
        assert 30 <= result <= 180


class TestSuccessRolls:
    """GURPS 3d6 success roll mechanics."""

    def test_success_by_margin(self):
        """Roll under effective skill succeeds with correct margin."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=14, roll=10)
        assert result.success is True
        assert result.margin == 4
        assert result.critical is False

    def test_failure_by_margin(self):
        """Roll over effective skill fails with correct margin."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=10, roll=13)
        assert result.success is False
        assert result.margin == -3

    def test_exact_match_succeeds(self):
        """Rolling exactly the effective skill is a success with margin 0."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=12, roll=12)
        assert result.success is True
        assert result.margin == 0

    def test_critical_success_3(self):
        """Roll of 3 is always critical success."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=6, roll=3)
        assert result.success is True
        assert result.critical is True
        assert result.critical_type == "success"

    def test_critical_success_4(self):
        """Roll of 4 is always critical success."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=6, roll=4)
        assert result.success is True
        assert result.critical is True

    def test_critical_success_5_at_skill_15(self):
        """Roll of 5 is critical success when effective skill >= 15."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=15, roll=5)
        assert result.critical is True
        assert result.critical_type == "success"

    def test_not_critical_success_5_at_skill_14(self):
        """Roll of 5 is NOT critical at effective skill 14."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=14, roll=5)
        assert result.success is True
        assert result.critical is False

    def test_critical_success_6_at_skill_16(self):
        """Roll of 6 is critical success when effective skill >= 16."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=16, roll=6)
        assert result.critical is True

    def test_critical_failure_18(self):
        """Roll of 18 is always critical failure."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=20, roll=18)
        assert result.success is False
        assert result.critical is True
        assert result.critical_type == "failure"

    def test_critical_failure_17_low_skill(self):
        """Roll of 17 is critical failure when effective skill <= 15."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=15, roll=17)
        assert result.critical is True
        assert result.critical_type == "failure"

    def test_not_critical_failure_17_high_skill(self):
        """Roll of 17 is ordinary failure when effective skill >= 16."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=16, roll=17)
        assert result.success is False
        assert result.critical is False

    def test_critical_failure_10_over(self):
        """Roll 10+ over effective skill is critical failure."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=6, roll=16)
        assert result.critical is True
        assert result.critical_type == "failure"

    def test_minimum_skill_rule(self):
        """Cannot attempt roll with effective skill < 3 (except defense)."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=2, roll=3, is_defense=False)
        assert result.success is False
        assert result.auto_fail is True

    def test_minimum_skill_defense_exception(self):
        """Defense rolls CAN be attempted at effective skill < 3."""
        from m1_psi_core.dice import check_success
        result = check_success(effective_skill=2, roll=3, is_defense=True)
        assert result.success is True  # 3 is always a success


class TestQuickContest:
    """Quick contest resolution for chase rolls and opposed tests."""

    def test_both_succeed_higher_margin_wins(self):
        """Both succeed: highest margin of success wins."""
        from m1_psi_core.dice import resolve_quick_contest
        # A: skill 14, roll 10 = margin +4
        # B: skill 12, roll 10 = margin +2
        result = resolve_quick_contest(14, 10, 12, 10)
        assert result.winner == "a"
        assert result.margin_of_victory == 2

    def test_both_fail_smaller_failure_wins(self):
        """Both fail: smallest margin of failure wins."""
        from m1_psi_core.dice import resolve_quick_contest
        # A: skill 10, roll 12 = margin -2
        # B: skill 10, roll 15 = margin -5
        result = resolve_quick_contest(10, 12, 10, 15)
        assert result.winner == "a"
        assert result.margin_of_victory == 3

    def test_one_succeeds_one_fails(self):
        """If one succeeds and one fails, success wins."""
        from m1_psi_core.dice import resolve_quick_contest
        # A: skill 14, roll 10 = success by 4
        # B: skill 10, roll 13 = failure by 3
        result = resolve_quick_contest(14, 10, 10, 13)
        assert result.winner == "a"
        assert result.margin_of_victory == 7  # 4 + 3

    def test_tie(self):
        """Tied margins means no winner."""
        from m1_psi_core.dice import resolve_quick_contest
        # A: skill 12, roll 10 = margin +2
        # B: skill 14, roll 12 = margin +2
        result = resolve_quick_contest(12, 10, 14, 12)
        assert result.winner is None
        assert result.margin_of_victory == 0
