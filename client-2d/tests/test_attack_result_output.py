# ABOUTME: Tests for game_attack MCP result text (issue #365).
# ABOUTME: Verifies attack roll, hit/miss, damage, and target HP are reported.

"""Tests for the attack-result block prepended to game_attack responses."""

from unittest.mock import MagicMock, PropertyMock


def _make_session():
    """Build a session-shaped mock that GameSession.attack can drive."""
    from client_2d.session import GameSession

    session = MagicMock()
    type(session).width = PropertyMock(return_value=1280)
    type(session).height = PropertyMock(return_value=900)
    session.player_x = 5
    session.player_y = 5
    session.selected_enemy = 0
    session.processing_enemy_turn = False
    session.combat_log = []
    session.current_mode = MagicMock()
    session.party_spread = False
    session.party_positions = []
    session._state_renderer = None
    # Bind real methods so the attack-result block actually renders.
    session._format_attack_report = GameSession._format_attack_report.__get__(session)
    session.execute_attack = GameSession.execute_attack.__get__(session)
    session.get_state = lambda: "<state>"
    return session


def _wire_player_with_longsword(session):
    """Configure session.engine for an adjacent melee combatant."""
    session.engine = MagicMock()
    session.engine.in_combat = True
    session.engine.is_player_turn.return_value = True
    session.engine.get_current_turn_state.return_value = MagicMock(movement_remaining=30)

    creature = MagicMock()
    creature.inventory.get_equipped_item.return_value = "longsword"
    archy = {
        "is_player": True,
        "creature": creature,
        "name": "Archy",
    }
    next_turn = {
        "is_player": True,
        "creature": creature,
        "name": "Bran",
    }
    # First call (pre-attack) returns Archy; subsequent calls return the next
    # combatant so the session's "attack didn't execute" check is bypassed.
    session.engine.get_current_combatant.side_effect = [archy] + [next_turn] * 20
    session.engine.game_state.data_loader.load_items.return_value = {
        "weapons": {
            "longsword": {
                "name": "Longsword",
                "category": "melee",
                "damage": "1d8",
                "properties": ["versatile"],
            }
        }
    }
    session.engine.advance_turn.return_value = {"combat_ended": True}
    session.engine.get_party_data.return_value = []


def _wire_adjacent_target(session, hp=7, max_hp=7):
    monster = MagicMock()
    monster.grid_x = 5
    monster.grid_y = 6  # adjacent (5 ft)
    monster.enemy_index = 0
    monster.entity_id = "monster_0"
    monster.sub_type = "giant_rat"
    monster.hp = hp
    monster.max_hp = max_hp
    monster._creature_ref = MagicMock(current_hp=hp, max_hp=max_hp, name="Giant Rat 1")
    session.entity_manager = MagicMock()
    session.entity_manager.get_monsters.return_value = [monster]
    session.entity_manager.get_current_turn_position.return_value = (5, 5)
    return monster


class TestAttackResultText:
    """game_attack must surface attack roll, hit/miss, damage, target HP."""

    def test_hit_reports_roll_and_damage(self):
        from client_2d.session import GameSession

        session = _make_session()
        _wire_player_with_longsword(session)
        target = _wire_adjacent_target(session, hp=7, max_hp=7)

        # After the attack the target's cached HP drops to 3.
        def _post_attack_sync(*_args, **_kwargs):
            target.hp = 3
            target._creature_ref.current_hp = 3

        session.entity_manager.sync_from_engine.side_effect = _post_attack_sync

        session.engine.execute_attack.return_value = {
            "success": True,
            "hit": True,
            "critical": False,
            "damage": 4,
            "attack_roll": 14,
            "attack_bonus": 5,
            "target_ac": 12,
            "target_name": "Giant Rat 1",
            "attacker_name": "Archy",
            "target_killed": False,
        }

        result = GameSession.attack(session, 0)

        assert "Archy" in result
        assert "Giant Rat 1" in result
        assert "14" in result  # natural roll
        assert "+5" in result or "+ 5" in result  # bonus
        assert "19" in result  # total
        assert "AC 12" in result
        assert "HIT" in result
        assert "4 damage" in result
        assert "3/7 HP" in result

    def test_miss_reports_roll_no_damage(self):
        from client_2d.session import GameSession

        session = _make_session()
        _wire_player_with_longsword(session)
        _wire_adjacent_target(session, hp=7, max_hp=7)

        session.engine.execute_attack.return_value = {
            "success": True,
            "hit": False,
            "critical": False,
            "damage": 0,
            "attack_roll": 5,
            "attack_bonus": 5,
            "target_ac": 12,
            "target_name": "Giant Rat 1",
            "attacker_name": "Archy",
            "target_killed": False,
        }

        result = GameSession.attack(session, 0)

        assert "MISS" in result
        assert "5" in result
        assert "AC 12" in result
        # On a miss the target HP is unchanged.
        assert "7/7 HP" in result
        assert "damage" not in result.split("Map:")[0].lower() or "0 damage" not in result

    def test_critical_hit_is_called_out(self):
        from client_2d.session import GameSession

        session = _make_session()
        _wire_player_with_longsword(session)
        target = _wire_adjacent_target(session, hp=7, max_hp=7)

        def _post_attack_sync(*_args, **_kwargs):
            target.hp = 0
            target._creature_ref.current_hp = 0

        session.entity_manager.sync_from_engine.side_effect = _post_attack_sync

        session.engine.execute_attack.return_value = {
            "success": True,
            "hit": True,
            "critical": True,
            "damage": 12,
            "attack_roll": 20,
            "attack_bonus": 5,
            "target_ac": 12,
            "target_name": "Giant Rat 1",
            "attacker_name": "Archy",
            "target_killed": True,
        }

        result = GameSession.attack(session, 0)

        assert "CRITICAL" in result
        assert "12 damage" in result
        assert "defeated" in result.lower() or "down" in result.lower()

    def test_long_range_disadvantage_called_out(self):
        from client_2d.session import GameSession

        session = _make_session()
        # Shortbow: normal 80, max 320. Position target 25 squares (125 ft) away.
        session.engine = MagicMock()
        session.engine.in_combat = True
        session.engine.is_player_turn.return_value = True
        session.engine.get_current_turn_state.return_value = MagicMock(movement_remaining=30)

        creature = MagicMock()
        creature.inventory.get_equipped_item.return_value = "shortbow"
        archy = {
            "is_player": True,
            "creature": creature,
            "name": "Archy",
        }
        next_turn = {
            "is_player": True,
            "creature": creature,
            "name": "Bran",
        }
        session.engine.get_current_combatant.side_effect = [archy] + [next_turn] * 20
        session.engine.game_state.data_loader.load_items.return_value = {
            "weapons": {
                "shortbow": {
                    "name": "Shortbow",
                    "category": "ranged",
                    "damage": "1d6",
                    "range": "80/320",
                }
            }
        }
        session.engine.advance_turn.return_value = {"combat_ended": True}
        session.engine.get_party_data.return_value = []

        monster = MagicMock()
        monster.grid_x = 30
        monster.grid_y = 5  # 25 squares = 125 ft (long range for shortbow)
        monster.enemy_index = 0
        monster.entity_id = "monster_0"
        monster.sub_type = "giant_rat"
        monster.hp = 5
        monster.max_hp = 7
        monster._creature_ref = MagicMock(current_hp=5, max_hp=7, name="Giant Rat 1")
        session.entity_manager = MagicMock()
        session.entity_manager.get_monsters.return_value = [monster]
        session.entity_manager.get_current_turn_position.return_value = (5, 5)

        session.engine.execute_attack.return_value = {
            "success": True,
            "hit": True,
            "critical": False,
            "damage": 2,
            "attack_roll": 11,
            "attack_bonus": 5,
            "target_ac": 12,
            "target_name": "Giant Rat 1",
            "attacker_name": "Archy",
            "target_killed": False,
        }

        result = GameSession.attack(session, 0)

        assert "long range" in result.lower()
        assert "disadvantage" in result.lower()
