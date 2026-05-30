# ABOUTME: Unit tests for slice-5a core actions (Dash, Disengage, Drop Prone, Stand Up)
# ABOUTME: Plan-01 step 4 — handlers for the SRD's missing core actions

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.systems.action_economy import ActionType, TurnState
from dnd_engine.systems.actions import dash, disengage, drop_prone, hide, stand_up


def _make_creature(name: str = "Hero", speed: int = 30) -> Creature:
    return Creature(
        name=name,
        max_hp=20,
        ac=15,
        abilities=Abilities(10, 10, 10, 10, 10, 10),
        speed=speed,
    )


class TestDash:
    """SRD § Actions › Dash:
    'For the rest of the turn, give yourself extra movement equal to
    your Speed.'
    """

    def test_dash_consumes_action_and_adds_speed_to_movement_pool(self):
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = dash(turn)
        assert ok is True
        assert reason is None
        assert turn.action_available is False
        assert turn.movement_remaining == 60  # 30 base + 30 from Dash

    def test_dash_fails_when_no_action_available(self):
        turn = TurnState()
        turn.reset(speed=30)
        turn.consume_action(ActionType.ACTION)
        ok, reason = dash(turn)
        assert ok is False
        assert reason == "no action available"
        assert turn.movement_remaining == 30  # unchanged

    def test_dash_applies_to_remaining_movement_not_a_set_value(self):
        """A creature that already moved 10 ft (pool=20) then Dashes
        ends up with 50 ft remaining, not 60. SRD says 'extra
        movement equal to your Speed', i.e. additive."""
        turn = TurnState()
        turn.reset(speed=30)
        turn.consume_movement(10)
        assert turn.movement_remaining == 20
        ok, _ = dash(turn)
        assert ok is True
        assert turn.movement_remaining == 50

    def test_dash_uses_cached_speed_for_dwarf(self):
        turn = TurnState()
        turn.reset(speed=25)  # Dwarf
        ok, _ = dash(turn)
        assert ok is True
        assert turn.movement_remaining == 50


class TestDisengage:
    """SRD § Actions › Disengage:
    'Your movement doesn't provoke Opportunity Attacks for the rest
    of the turn.'
    """

    def test_disengage_consumes_action_and_sets_flag(self):
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = disengage(turn)
        assert ok is True
        assert reason is None
        assert turn.action_available is False
        assert turn.disengaged_this_turn is True

    def test_disengage_fails_when_no_action_available(self):
        turn = TurnState()
        turn.reset(speed=30)
        turn.consume_action(ActionType.ACTION)
        ok, reason = disengage(turn)
        assert ok is False
        assert reason == "no action available"
        assert turn.disengaged_this_turn is False

    def test_disengage_flag_resets_on_next_turn(self):
        turn = TurnState()
        turn.reset(speed=30)
        disengage(turn)
        assert turn.disengaged_this_turn is True
        turn.reset(speed=30)
        assert turn.disengaged_this_turn is False


class TestDropProne:
    """SRD § Movement › Dropping Prone:
    'On your turn, you can give yourself the Prone condition without
    using an action or any of your Speed, but you can't do so if your
    Speed is 0.'
    """

    def test_drop_prone_adds_condition_without_consuming(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = drop_prone(actor, turn)
        assert ok is True
        assert reason is None
        assert actor.has_condition("prone") is True
        # No action, no bonus action, no movement consumed.
        assert turn.action_available is True
        assert turn.bonus_action_available is True
        assert turn.movement_remaining == 30

    def test_drop_prone_forbidden_when_speed_is_zero(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=0)
        ok, reason = drop_prone(actor, turn)
        assert ok is False
        assert reason == "speed is 0"
        assert actor.has_condition("prone") is False


class TestStandUp:
    """Rules Glossary › Prone:
    'Standing up from prone costs half the creature's Speed.'
    """

    def test_stand_up_costs_half_speed_and_clears_prone(self):
        actor = _make_creature()
        actor.add_condition("prone")
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = stand_up(actor, turn)
        assert ok is True
        assert reason is None
        assert actor.has_condition("prone") is False
        assert turn.movement_remaining == 15  # 30 - 15 (half of 30)

    def test_stand_up_fails_when_not_prone(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = stand_up(actor, turn)
        assert ok is False
        assert reason == "not prone"
        assert turn.movement_remaining == 30

    def test_stand_up_fails_when_insufficient_movement(self):
        actor = _make_creature()
        actor.add_condition("prone")
        turn = TurnState()
        turn.reset(speed=30)
        turn.consume_movement(20)  # 10 ft left, need 15
        ok, reason = stand_up(actor, turn)
        assert ok is False
        assert reason == "insufficient movement"
        assert actor.has_condition("prone") is True  # still prone
        assert turn.movement_remaining == 10  # unchanged

    def test_stand_up_dwarf_costs_half_of_25_speed(self):
        actor = _make_creature(speed=25)
        actor.add_condition("prone")
        turn = TurnState()
        turn.reset(speed=25)
        ok, _ = stand_up(actor, turn)
        assert ok is True
        # 25 // 2 = 12, leaving 13
        assert turn.movement_remaining == 13


class TestHide:
    """SRD § Actions › Hide: 'Make a Dexterity (Stealth) check.'

    The caller rolls the Stealth check (it needs skills data and the DC
    from observers' passive Perception); the handler consumes the turn's
    slot and, on a successful check, gives the hider the Hidden (unseen)
    condition.
    """

    def test_hide_consumes_action_and_sets_hidden_on_success(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = hide(actor, turn, succeeded=True)
        assert ok is True
        assert reason is None
        assert turn.action_available is False
        assert actor.has_condition("hidden") is True

    def test_hide_consumes_action_but_stays_visible_on_failure(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        ok, reason = hide(actor, turn, succeeded=False)
        assert ok is True
        assert reason is None
        assert turn.action_available is False  # the action is still spent
        assert actor.has_condition("hidden") is False

    def test_hide_fails_when_no_action_available(self):
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        turn.consume_action(ActionType.ACTION)
        ok, reason = hide(actor, turn, succeeded=True)
        assert ok is False
        assert reason == "no action available"
        assert actor.has_condition("hidden") is False

    def test_hide_can_use_a_bonus_action(self):
        """Cunning Action / Nimble Escape let some creatures Hide as a
        Bonus Action; the handler honors an explicit BONUS_ACTION cost."""
        actor = _make_creature()
        turn = TurnState()
        turn.reset(speed=30)
        ok, _ = hide(actor, turn, succeeded=True, action_type=ActionType.BONUS_ACTION)
        assert ok is True
        assert turn.bonus_action_available is False
        assert turn.action_available is True  # Action slot untouched
        assert actor.has_condition("hidden") is True
