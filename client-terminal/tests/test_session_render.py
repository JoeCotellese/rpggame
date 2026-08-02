# ABOUTME: Unit tests for rendering Session events as terminal output.
# ABOUTME: Pins the player-facing text so migrating off the old turn loop reads identically.

"""Verification for the session event renderer (#697).

The terminal client used to call `process_enemy_turn`, `next_turn` and
`_check_combat_end` itself and print as it went. It now receives an
`ActionResult` and renders from the events alone, so these tests pin the lines a
player actually sees: an enemy's turn, a death save, a skipped turn, an ongoing
effect, and an opportunity attack.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from dnd_engine.session import ActionResult, GameEvent
from dnd_engine.utils.events import EventType
from terminal_client.ui.session_render import SessionEventRenderer


@pytest.fixture
def cli():
    """A CLI stand-in with narrative disabled, so only mechanics are rendered."""
    stub = Mock()
    stub.llm_enhancer = None
    stub.game_state.party.characters = []
    stub.game_state.active_enemies = []
    stub._find_party_member_by_name.return_value = None
    stub._find_enemy_by_name.return_value = None
    return stub


@pytest.fixture
def renderer(cli):
    return SessionEventRenderer(cli)


def _result(*events: GameEvent) -> ActionResult:
    """Wrap events in an ActionResult with contiguous sequence numbers."""
    return ActionResult(
        ok=True,
        events=tuple(
            GameEvent(type=e.type, data=e.data, sequence=i, message=e.message)
            for i, e in enumerate(events)
        ),
    )


def _event(event_type: EventType, data: dict, message: str | None = None) -> GameEvent:
    return GameEvent(type=event_type, data=data, sequence=0, message=message)


def _enemy_turn(**overrides) -> GameEvent:
    """An ENEMY_TURN payload with every field the facade sends."""
    data = {
        "enemy_name": "Skeleton",
        "enemy_display_name": "Skeleton 2",
        "action_taken": "attack",
        "attack_result": None,
        "attack_text": None,
        "target_name": None,
        "target_killed": False,
        "action_data": None,
        "saving_throw_triggered": False,
        "save_ability": None,
        "save_dc": None,
        "save_succeeded": None,
        "conditions_applied": [],
        "condition_removal": None,
        "concentration_broken": None,
        "turn_start_effects": [],
        "turn_end_effects": [],
        "incapacitating_conditions": [],
        "moved_squares": 0,
    }
    data.update(overrides)
    return _event(EventType.ENEMY_TURN, data)


def _attack_result(**overrides) -> dict:
    payload = {
        "attacker_name": "Skeleton",
        "defender_name": "Thorin",
        "attack_roll": 15,
        "attack_bonus": 4,
        "target_ac": 16,
        "hit": True,
        "damage": 5,
        "critical_hit": False,
        "advantage": False,
        "disadvantage": False,
        "sneak_attack_damage": 0,
        "sneak_attack_dice": None,
        "circumstantial": 0,
    }
    payload.update(overrides)
    return payload


class TestEnemyTurns:
    """An enemy's turn must read the way it always has."""

    def test_an_attack_announces_the_turn_and_the_mechanics(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    attack_result=_attack_result(),
                    attack_text="Skeleton attacks Thorin: HIT for 5 damage",
                    target_name="Thorin",
                )
            )
        )

        out = capsys.readouterr().out
        assert "Skeleton 2's turn" in out
        assert "HIT for 5 damage" in out

    def test_a_killing_blow_is_announced(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    attack_result=_attack_result(damage=30),
                    attack_text="Skeleton attacks Thorin: HIT for 30 damage",
                    target_name="Thorin",
                    target_killed=True,
                )
            )
        )

        assert "Thorin has fallen!" in capsys.readouterr().out

    def test_incapacitation_names_the_conditions(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    action_taken="incapacitated",
                    incapacitating_conditions=["paralyzed"],
                )
            )
        )

        out = capsys.readouterr().out
        assert "Skeleton 2" in out
        assert "paralyzed" in out
        assert "cannot act this turn" in out

    def test_a_fatal_turn_start_effect_is_announced(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    action_taken="died_start_of_turn",
                    turn_start_effects=[
                        {
                            "effect_type": "damage",
                            "condition_id": "on_fire",
                            "message": "Skeleton 2 burns for 3 damage!",
                            "damage": 3,
                            "creature_died": True,
                        }
                    ],
                )
            )
        )

        out = capsys.readouterr().out
        assert "burns for 3 damage" in out
        assert "killed by on fire" in out

    def test_a_condition_removal_attempt_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    action_taken="condition_removal",
                    condition_removal={
                        "condition_id": "on_fire",
                        "attempted": True,
                        "success": True,
                        "message": "Skeleton 2 puts out the flames!",
                        "action_consumed": "action",
                    },
                )
            )
        )

        assert "puts out the flames" in capsys.readouterr().out

    def test_a_failed_save_reports_the_condition_applied(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    attack_result=_attack_result(),
                    attack_text="Skeleton attacks Thorin: HIT for 5 damage",
                    target_name="Thorin",
                    saving_throw_triggered=True,
                    save_ability="CON",
                    save_dc=12,
                    save_succeeded=False,
                    conditions_applied=["poisoned"],
                )
            )
        )

        out = capsys.readouterr().out
        assert "fails CON save" in out
        assert "POISONED" in out

    def test_turn_end_expiry_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _enemy_turn(
                    action_taken="incapacitated",
                    incapacitating_conditions=["stunned"],
                    turn_end_effects=[
                        {
                            "effect_type": "condition_expired",
                            "condition_id": "stunned",
                            "message": "",
                            "damage": 0,
                            "creature_died": False,
                        }
                    ],
                )
            )
        )

        assert "STUNNED" in capsys.readouterr().out

    def test_the_attack_events_that_follow_are_not_printed_twice(self, renderer, capsys):
        """The facade emits ATTACK_ROLL/DAMAGE_DEALT/CHARACTER_DEATH after
        ENEMY_TURN for the same swing. The enemy-turn display already covered it.
        """
        renderer.render(
            _result(
                _enemy_turn(
                    attack_result=_attack_result(),
                    attack_text="Skeleton attacks Thorin: HIT for 5 damage",
                    target_name="Thorin",
                    target_killed=True,
                ),
                _event(
                    EventType.ATTACK_ROLL,
                    {"attacker": "Skeleton 2", "target": "Thorin", "hit": True},
                    message="Skeleton 2 hits Thorin with scimitar.",
                ),
                _event(
                    EventType.DAMAGE_DEALT,
                    {"attacker": "Skeleton 2", "target": "Thorin", "amount": 5},
                    message="Thorin takes 5 damage.",
                ),
                _event(
                    EventType.CHARACTER_DEATH,
                    {"name": "Thorin"},
                    message="Thorin falls.",
                ),
            )
        )

        out = capsys.readouterr().out
        assert "hits Thorin with scimitar" not in out
        assert out.count("has fallen") == 1

    def test_the_swallow_does_not_outlast_the_turn_it_belongs_to(self, renderer, capsys):
        """A later attack from another source must still be shown.

        The echo suppression is scoped to the enemy attack that preceded it. If
        it stayed armed, the next attack events to arrive — a player's, once
        their attacks route through the session — would vanish.
        """
        renderer.render(
            _result(
                _enemy_turn(
                    attack_result=_attack_result(),
                    attack_text="Skeleton attacks Thorin: HIT for 5 damage",
                    target_name="Thorin",
                ),
                # The pair the facade emits for a damaging hit.
                _event(
                    EventType.ATTACK_ROLL,
                    {"attacker": "Skeleton 2", "target": "Thorin", "hit": True},
                    message="Skeleton 2 hits Thorin with scimitar.",
                ),
                _event(
                    EventType.DAMAGE_DEALT,
                    {"attacker": "Skeleton 2", "target": "Thorin", "amount": 5},
                    message="Thorin takes 5 damage.",
                ),
                # A different attack entirely — this one must be shown.
                _event(
                    EventType.ATTACK_ROLL,
                    {"attacker": "Thorin", "target": "Skeleton 2", "hit": True},
                    message="Thorin hits Skeleton 2 with longsword.",
                ),
            )
        )

        assert "Thorin hits Skeleton 2 with longsword" in capsys.readouterr().out, (
            "echo suppression leaked past the enemy turn it belonged to"
        )


class TestDeathSaves:
    """Death saves used to print from `process_death_save_turn`."""

    def _death_save(self, **overrides) -> GameEvent:
        data = {
            "character": "Thorin",
            "roll": 11,
            "success": True,
            "natural_20": False,
            "natural_1": False,
            "successes": 1,
            "failures": 0,
            "stabilized": False,
            "dead": False,
            "conscious": False,
        }
        data.update(overrides)
        return _event(EventType.DEATH_SAVE, data)

    def test_the_turn_is_introduced_before_the_roll(self, renderer, capsys):
        renderer.render(_result(self._death_save()))
        out = capsys.readouterr().out
        assert "Thorin's Turn - Death Save" in out
        assert "must make a death saving throw" in out

    def test_a_success_reports_the_roll_and_the_tally(self, renderer, capsys):
        renderer.render(_result(self._death_save()))
        out = capsys.readouterr().out
        assert "rolled 11" in out
        assert "Successes: 1/3" in out

    def test_a_failure_reports_the_tally(self, renderer, capsys):
        renderer.render(_result(self._death_save(success=False, failures=2)))
        assert "Failures: 2/3" in capsys.readouterr().out

    def test_a_natural_twenty_restores_consciousness(self, renderer, capsys):
        renderer.render(
            _result(self._death_save(natural_20=True, roll=20, conscious=True))
        )
        out = capsys.readouterr().out
        assert "Natural 20" in out
        assert "regains 1 HP" in out

    def test_a_natural_one_counts_two_failures(self, renderer, capsys):
        renderer.render(
            _result(self._death_save(natural_1=True, roll=1, success=False, failures=2))
        )
        out = capsys.readouterr().out
        assert "Natural 1" in out
        assert "Two failures" in out

    def test_death_is_announced(self, renderer, capsys):
        renderer.render(
            _result(self._death_save(success=False, failures=3, dead=True))
        )
        assert "has died" in capsys.readouterr().out

    def test_stabilizing_is_announced(self, renderer, capsys):
        renderer.render(_result(self._death_save(stabilized=True)))
        assert "is stabilized" in capsys.readouterr().out


class TestSkippedAndAfflictedTurns:
    """Turns the facade passes over on the player's behalf."""

    def test_a_stabilized_character_is_reported_as_skipped(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.TURN_END,
                    {"actor": "Garrick", "reason": "stabilized"},
                    message="Garrick is unconscious but stable.",
                )
            )
        )

        out = capsys.readouterr().out
        assert "Garrick" in out
        assert "stabilized" in out

    def test_an_incapacitated_character_names_its_conditions(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.TURN_END,
                    {
                        "actor": "Garrick",
                        "reason": "incapacitated",
                        "conditions": ["paralyzed"],
                    },
                )
            )
        )

        out = capsys.readouterr().out
        assert "PARALYZED" in out
        assert "cannot act" in out

    def test_ongoing_damage_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.DAMAGE_TAKEN,
                    {
                        "actor": "Garrick",
                        "condition": "on_fire",
                        "damage": 3,
                        "creature_died": False,
                    },
                    message="Garrick takes 3 fire damage!",
                )
            )
        )

        assert "takes 3 fire damage" in capsys.readouterr().out

    def test_ongoing_damage_that_kills_says_so(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.DAMAGE_TAKEN,
                    {
                        "actor": "Garrick",
                        "condition": "on_fire",
                        "damage": 9,
                        "creature_died": True,
                    },
                    message="Garrick takes 9 fire damage!",
                )
            )
        )

        assert "killed by on fire" in capsys.readouterr().out

    def test_a_repeat_save_success_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.CONDITION_REMOVED,
                    {
                        "actor": "Garrick",
                        "type": "repeat_save_success",
                        "condition": "paralyzed",
                        "save_result": {"ability": "con", "total": 15},
                    },
                )
            )
        )

        out = capsys.readouterr().out
        assert "CON save" in out
        assert "PARALYZED removed" in out

    def test_an_expiry_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.CONDITION_REMOVED,
                    {
                        "actor": "Garrick",
                        "type": "condition_expired",
                        "condition": "stunned",
                    },
                )
            )
        )

        assert "STUNNED" in capsys.readouterr().out

    def test_surprise_wearing_off_stays_silent(self, renderer, capsys):
        """Announcing it every single fight was noise, so it never was announced."""
        renderer.render(
            _result(
                _event(
                    EventType.CONDITION_REMOVED,
                    {
                        "actor": "Garrick",
                        "type": "condition_expired",
                        "condition": "surprised",
                    },
                )
            )
        )

        assert capsys.readouterr().out.strip() == ""


class TestReactions:
    """Opportunity attacks resolved by the facade."""

    def test_a_taken_opportunity_attack_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.OPPORTUNITY_ATTACK,
                    {"attacker": "Thorin", "target": "Skeleton 2", "hit": True},
                    message="Thorin takes an opportunity attack on Skeleton 2 — hit.",
                ),
                _event(
                    EventType.ATTACK_ROLL,
                    {"attacker": "Thorin", "target": "Skeleton 2", "hit": True},
                    message="Thorin hits Skeleton 2 with opportunity attack.",
                ),
            )
        )

        out = capsys.readouterr().out
        assert "opportunity attack on Skeleton 2" in out

    def test_a_declined_reaction_is_reported(self, renderer, capsys):
        renderer.render(
            _result(
                _event(
                    EventType.REACTION_DECLINED,
                    {"reactor": "Thorin", "mover": "Skeleton 2"},
                    message="Thorin lets Skeleton 2 go.",
                )
            )
        )

        assert "lets Skeleton 2 go" in capsys.readouterr().out


class TestEventsTheBusAlreadyOwns:
    """The CLI subscribes to these directly; rendering them again double-prints."""

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.COMBAT_START,
            EventType.COMBAT_END,
            EventType.COMBAT_FLED,
            EventType.LEVEL_UP,
            EventType.ITEM_ACQUIRED,
            EventType.GOLD_ACQUIRED,
            EventType.ROOM_ENTER,
            EventType.SKILL_CHECK,
        ],
    )
    def test_bus_owned_events_render_nothing(self, renderer, capsys, event_type):
        # No message: that is how the session records an event it captured from
        # the bus, and it is what marks the event as one the CLI's own
        # subscriber has already printed.
        renderer.render(_result(_event(event_type, {"anything": True})))

        assert capsys.readouterr().out.strip() == ""

    def test_a_synthesized_event_of_a_bus_owned_type_still_renders(self, renderer, capsys):
        """The overlap is real: the facade synthesizes `SKILL_CHECK` too.

        Freeform adjudication records a `SKILL_CHECK` carrying the roll the
        player needs to see, and the CLI separately subscribes to `SKILL_CHECK`
        on the bus. Suppressing the type outright would swallow the facade's
        line. Bus-sourced events never carry a message, so that is what tells
        the two apart.
        """
        renderer.render(
            _result(
                _event(
                    EventType.SKILL_CHECK,
                    {"actor": "Thorin", "skill": "athletics", "total": 17, "dc": 15},
                    message="Thorin rolls Strength (Athletics): 14 + 3 = 17 vs DC 15",
                )
            )
        )

        assert "vs DC 15" in capsys.readouterr().out, (
            "the facade's own skill-check line was suppressed as if it came "
            "from the bus"
        )

    def test_every_bus_subscription_in_the_cli_is_covered(self):
        """Guard: a new CLI bus subscription must be added to the ignore set.

        Missing one means the player sees the same line twice, which is exactly
        the class of defect this renderer exists to avoid.
        """
        import ast
        from pathlib import Path

        source = Path("terminal_client/ui/cli.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        subscribed = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "subscribe":
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Attribute) and isinstance(first.value, ast.Name):
                if first.value.id == "EventType":
                    subscribed.add(first.attr)

        uncovered = subscribed - {t.name for t in SessionEventRenderer.BUS_OWNED}
        assert not uncovered, (
            f"CLI subscribes to these on the bus but the renderer would print them "
            f"again: {sorted(uncovered)}"
        )
