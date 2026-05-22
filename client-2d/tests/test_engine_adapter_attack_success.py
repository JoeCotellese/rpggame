# ABOUTME: Adapter-level tests for EngineAdapter.execute_attack success/error
# ABOUTME: propagation from the underlying PlayerAttackResult (issue #394).

"""Regression tests for issue #394.

The adapter must mirror ``PlayerAttackResult.success`` and forward
``PlayerAttackResult.error`` to the caller. Prior to this fix the adapter
hard-coded ``success=True`` whenever the engine call did not raise, which
silently swallowed legitimate failures such as the no-ammunition short-circuit
in ``GameState.execute_player_attack`` (``game_state.py`` ammo check).
"""

from pathlib import Path

import pytest

SCENARIO_DIR = (
    Path(__file__).parent.parent.parent
    / "dnd-engine"
    / "tests"
    / "scenarios"
    / "yaml"
)


@pytest.fixture
def adapter_no_ammo():
    """Adapter loaded into a scenario whose fighter has a shortbow but no arrows.

    ``ranged_attack_basic.yaml`` arms its high-elf fighter with a shortbow
    and never grants ammunition, so the engine short-circuits the attack on
    the ammo check and returns ``PlayerAttackResult(success=False, ...)``.
    """
    from client_2d.integration.engine_adapter import EngineAdapter

    adapter = EngineAdapter()
    adapter.load_scenario(SCENARIO_DIR / "ranged_attack_basic.yaml")
    assert adapter.in_combat
    return adapter


def _live_enemy_index(adapter):
    for idx, enemy in enumerate(adapter.game_state.active_enemies):
        if enemy.is_alive:
            return idx
    pytest.skip("No live enemy to attack")


class TestEngineAdapterSuccessPassthrough:
    """The adapter must mirror PlayerAttackResult.success/error."""

    def test_no_ammo_attack_returns_success_false(self, adapter_no_ammo):
        """No-ammo failure must surface as success=False, not True."""
        target_index = _live_enemy_index(adapter_no_ammo)

        result = adapter_no_ammo.execute_attack(target_index=target_index)

        assert result["success"] is False

    def test_no_ammo_attack_returns_engine_error_message(self, adapter_no_ammo):
        """The engine's error string must be forwarded verbatim."""
        target_index = _live_enemy_index(adapter_no_ammo)

        result = adapter_no_ammo.execute_attack(target_index=target_index)

        assert result["error"] == "No ammunition available for this weapon"

    def test_no_ammo_attack_preserves_metadata_keys(self, adapter_no_ammo):
        """Failure dict must still expose the keys callers index into.

        Existing callers (session, MCP attack report) read hit/damage/etc.
        unconditionally. A regression that omits keys would surface as
        KeyError rather than a graceful failure path.
        """
        target_index = _live_enemy_index(adapter_no_ammo)

        result = adapter_no_ammo.execute_attack(target_index=target_index)

        for key in (
            "hit",
            "damage",
            "critical",
            "target_name",
            "target_killed",
            "attacker_name",
            "attack_roll",
            "attack_bonus",
            "target_ac",
            "disadvantage",
        ):
            assert key in result, f"missing key: {key}"

    def test_successful_attack_returns_success_true_and_no_error(
        self, adapter_no_ammo, monkeypatch
    ):
        """Sanity: when the engine reports success=True, the adapter mirrors it.

        We monkeypatch ``execute_player_attack`` so the test does not depend
        on either dice outcomes or scenario-specific ammo state.
        """
        from dnd_engine.core.combat import AttackResult
        from dnd_engine.core.game_state import PlayerAttackResult

        attacker = adapter_no_ammo.party.characters[0]
        target_index = _live_enemy_index(adapter_no_ammo)
        target = adapter_no_ammo.game_state.active_enemies[target_index]

        fake_attack = AttackResult(
            attacker_name=attacker.name,
            defender_name=target.name,
            attack_roll=15,
            attack_bonus=4,
            target_ac=13,
            hit=True,
            critical_hit=False,
            damage=6,
            advantage=False,
            disadvantage=False,
        )
        fake_result = PlayerAttackResult(
            success=True,
            attack_result=fake_attack,
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name="shortbow",
        )

        def _stub(*_args, **_kwargs):
            return fake_result

        monkeypatch.setattr(
            adapter_no_ammo.game_state, "execute_player_attack", _stub
        )

        result = adapter_no_ammo.execute_attack(target_index=target_index)

        assert result["success"] is True
        assert result["error"] is None
        assert result["hit"] is True
        assert result["damage"] == 6
