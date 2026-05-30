# ABOUTME: Content test for #606 — a shipped room must offer cover-based concealment.
# ABOUTME: Verifies the laboratory dungeon ships a ¾-cover room where Hide yields advantage.

"""Content coverage for cover-based concealment (issue #606).

The Hide gate (#496) admits a room when it is Heavily Obscured *or* offers at
least Three-Quarters Cover. Before this content existed, the only shipped
hideable room (`laboratory.boiler_room`) qualified purely via heavy fog, which
blinds both directions — a hidden attacker's advantage and the can't-see-target
disadvantage cancel, so the classic Hide payoff was never reachable in shipped
play.

These tests pin a shipped room that qualifies via cover with *clear* sight, so a
hidden attacker still sees the target and lands the advantaged shot.
"""

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.perception import (
    Cover,
    LightLevel,
    Obscurement,
    VisibilityRelation,
    compute_visibility,
)

CAMPAIGN_ID = "poisoned_laboratory"
DUNGEON_NAME = "laboratory"


def _cover_concealment_rooms() -> list[dict]:
    """Rooms that qualify for Hide via cover (not heavy fog) with clear sight."""
    dungeon = DataLoader().load_dungeon(DUNGEON_NAME, CAMPAIGN_ID)
    rooms = dungeon["rooms"].values()
    qualifying = []
    for room in rooms:
        cover = str(room.get("cover", "none")).lower()
        obscured = "heavy_fog" in [s.lower() for s in room.get("obscurement_sources", [])]
        if cover in ("three_quarters", "total") and not obscured:
            qualifying.append(room)
    return qualifying


class TestCoverConcealmentContentShipped:
    def test_laboratory_ships_a_cover_concealment_room(self):
        """At least one shipped room offers ¾+ cover with clear sight."""
        rooms = _cover_concealment_rooms()
        assert rooms, (
            "No shipped laboratory room offers cover-based concealment "
            "(cover three_quarters/total with clear sight); Hide-for-advantage "
            "is unreachable in shipped content (#606)."
        )

    def test_cover_concealment_room_has_an_enemy_to_snipe(self):
        """The payoff room hosts an enemy so the advantaged shot is reachable."""
        rooms = _cover_concealment_rooms()
        assert any(room.get("enemies") for room in rooms), (
            "A cover-concealment room must host an enemy so a player can take "
            "the advantaged shot from hiding."
        )

    def test_cover_concealment_room_is_reachable(self):
        """The payoff room is wired into the dungeon graph (an exit leads to it)."""
        dungeon = DataLoader().load_dungeon(DUNGEON_NAME, CAMPAIGN_ID)
        rooms = dungeon["rooms"]
        target_ids = {r["id"] for r in _cover_concealment_rooms()}
        destinations = set()
        for room in rooms.values():
            for dest in room.get("exits", {}).values():
                # Exits are either a room-id string or a {"destination": ...} dict.
                destinations.add(dest["destination"] if isinstance(dest, dict) else dest)
        assert target_ids & destinations, (
            "The cover-concealment room is not reachable from any other room."
        )


class TestCoverConcealmentGate:
    def test_room_passes_the_hide_gate(self):
        """`can_attempt_hide` admits the shipped cover room."""
        rooms = _cover_concealment_rooms()
        room = rooms[0]
        party = Party(
            [
                Character(
                    name="Sneak",
                    character_class=CharacterClass.ROGUE,
                    level=1,
                    abilities=Abilities(10, 16, 10, 10, 10, 10),
                    max_hp=8,
                    ac=14,
                    skill_proficiencies=["stealth"],
                )
            ]
        )
        gs = GameState(party, DUNGEON_NAME, campaign_id=CAMPAIGN_ID)
        gs.current_room_id = room["id"]
        assert gs.can_attempt_hide(party.characters[0]) is True


class TestCoverConcealmentPayoff:
    def test_hidden_attacker_in_clear_cover_room_gains_advantage(self):
        """In clear sight behind cover, the hidden attacker sees the target while
        the target cannot see the attacker — the unseen-attacker advantage stands
        (it does not cancel, because the attacker is not blinded by fog)."""
        rooms = _cover_concealment_rooms()
        room = rooms[0]
        assert str(room.get("cover")).lower() in ("three_quarters", "total")

        attacker = Creature(
            name="Hidden Rogue", max_hp=8, ac=14, abilities=Abilities(10, 16, 10, 10, 10, 10)
        )
        attacker.add_condition("hidden")
        defender = Creature(
            name="Skeleton", max_hp=13, ac=13, abilities=Abilities(10, 14, 15, 6, 8, 5)
        )

        attacker_sees_defender = compute_visibility(
            attacker,
            defender,
            light_level=LightLevel.BRIGHT,
            obscurement=Obscurement.CLEAR,
            distance=10,
        )
        defender_sees_attacker = compute_visibility(
            defender,
            attacker,
            light_level=LightLevel.BRIGHT,
            obscurement=Obscurement.CLEAR,
            distance=10,
        )

        assert attacker_sees_defender == VisibilityRelation.SEEN
        assert defender_sees_attacker == VisibilityRelation.UNSEEN

    def test_room_cover_string_round_trips_to_enum(self):
        """The shipped `cover` value parses into a Hide-qualifying Cover enum."""
        room = _cover_concealment_rooms()[0]
        cover = Cover(str(room["cover"]).lower())
        assert cover in (Cover.THREE_QUARTERS, Cover.TOTAL)

    def test_attack_from_cover_resolves_with_advantage(self):
        """End-to-end: feeding the room's visibility relations into combat yields
        an advantaged attack (the unseen-attacker advantage does not cancel)."""
        room = _cover_concealment_rooms()[0]
        # The shipped room must be clear-sighted cover for the advantage to stand.
        assert str(room["cover"]).lower() in ("three_quarters", "total")
        attacker = Creature(
            name="Hidden Rogue", max_hp=8, ac=14, abilities=Abilities(10, 16, 10, 10, 10, 10)
        )
        attacker.add_condition("hidden")
        defender = Creature(
            name="Skeleton", max_hp=13, ac=13, abilities=Abilities(10, 14, 15, 6, 8, 5)
        )

        attacker_sees_defender = compute_visibility(
            attacker, defender, light_level=LightLevel.BRIGHT, obscurement=Obscurement.CLEAR
        )
        defender_sees_attacker = compute_visibility(
            defender, attacker, light_level=LightLevel.BRIGHT, obscurement=Obscurement.CLEAR
        )

        engine = CombatEngine(dice_roller=DiceRoller(seed=42))
        result = engine.resolve_attack(
            attacker,
            defender,
            attack_bonus=5,
            damage_dice="1d6+3",
            attacker_sees_defender=attacker_sees_defender,
            defender_sees_attacker=defender_sees_attacker,
        )

        assert result.advantage is True
        assert result.disadvantage is False
