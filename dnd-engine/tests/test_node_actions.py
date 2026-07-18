# ABOUTME: Tests for node-surface action dispatch (issue #684 slice 3).
# ABOUTME: Covers interactions, talk/shop/rest routing, rumors, job board, and skill-gated examine.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.node_surface import NodeActionError
from dnd_engine.core.npc import NPC
from dnd_engine.core.party import Party
from dnd_engine.core.quest import QuestManager
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


def _npc(npc_id: str, location: str, reputation: int = 0, **overrides) -> NPC:
    data = {
        "id": npc_id,
        "name": npc_id.title(),
        "display_name": f"{npc_id.title()} the Tester",
        "home_location": location,
        "current_location": location,
        "personality": {"traits": ["testy"], "speech_style": "terse"},
        "knowledge": {
            "general": [f"{npc_id} general rumor"],
            "quest_hooks": ["investigate_crypt"],
            "local_lore": [f"{npc_id} local lore"],
        },
        "shop": {
            "enabled": True,
            "shop_type": "tavern",
            "inventory": [
                {"item_id": "ale", "price": 10, "stock": -1},
                {"item_id": "room_night", "price": 20, "stock": 3},
            ],
            "buy_rate": 0.5,
        },
        "dialogue": {
            "greeting": f"Welcome, says {npc_id}.",
            "farewell": "Bye.",
            "hostile_greeting": f"Get out, says {npc_id}.",
        },
        "reputation_modifiers": {
            "friendly_threshold": 10,
            "hostile_threshold": -20,
            "disposition_effects": {
                "friendly": {"price_modifier": 0.9, "extra_hints": True},
                "hostile": {"refuses_service": True},
            },
        },
    }
    data.update(overrides)
    npc = NPC.from_dict(data)
    npc.player_reputation = reputation
    return npc


class StubNPCManager:
    def __init__(self, npcs):
        self.npcs = {npc.id: npc for npc in npcs}

    def get_npcs_in_room(self, room_guid):
        return [npc for npc in self.npcs.values() if npc.current_location == room_guid]

    def get_npc(self, npc_id):
        return self.npcs.get(npc_id)


@pytest.fixture
def test_party():
    abilities = Abilities(
        strength=14,
        dexterity=12,
        constitution=13,
        intelligence=10,
        wisdom=11,
        charisma=8,
    )
    character = Character(
        name="Test Hero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=abilities,
        max_hp=12,
        ac=16,
    )
    return Party([character])


@pytest.fixture
def node_game(test_party):
    game = GameState(
        party=test_party,
        dungeon_name="lab_settlement",
        event_bus=EventBus(),
        data_loader=DataLoader(),
    )
    game.npc_manager = StubNPCManager(
        [
            _npc("tavernkeep", "lab_tavern", reputation=0),
            _npc("friendly", "lab_tavern", reputation=15),
            _npc("grump", "lab_tavern", reputation=-30),
        ]
    )
    return game


@pytest.fixture
def tavern_game(node_game):
    node_game.enter_node("lab_tavern")
    return node_game


class TestInteractions:
    def test_interactions_merge_actions_and_npcs(self, tavern_game):
        view = tavern_game.node_actions.interactions()
        assert [a["id"] for a in view["actions"]] == ["talk", "shop", "rest"]
        npc_ids = [npc["id"] for npc in view["npcs"]]
        assert npc_ids == ["tavernkeep", "friendly", "grump"]

    def test_npcs_carry_disposition_word_never_number(self, tavern_game):
        view = tavern_game.node_actions.interactions()
        by_id = {npc["id"]: npc for npc in view["npcs"]}
        assert by_id["tavernkeep"]["disposition"] == "neutral"
        assert by_id["friendly"]["disposition"] == "friendly"
        assert by_id["grump"]["disposition"] == "hostile"
        for npc in view["npcs"]:
            assert "reputation" not in npc

    def test_actions_normalized_to_objects(self, node_game):
        node_game.enter_node("lab_gate")
        view = node_game.node_actions.interactions()
        examine = view["actions"][0]
        assert examine["id"] == "examine_symbol"
        assert examine["gate"] == {"skill": "religion", "dc": 12}

    def test_transition_surfaces_in_view(self, node_game):
        node_game.enter_node("lab_gate")
        view = node_game.node_actions.interactions()
        assert view["transition"]["to"] == "lab_dungeon"


class TestTalk:
    def test_talk_returns_disposition_greeting(self, tavern_game):
        result = tavern_game.node_actions.talk("tavernkeep")
        assert result["greeting"] == "Welcome, says tavernkeep."
        assert result["npc"]["disposition"] == "neutral"

    def test_talk_hostile_npc_uses_hostile_greeting(self, tavern_game):
        result = tavern_game.node_actions.talk("grump")
        assert result["greeting"] == "Get out, says grump."
        assert result["npc"]["disposition"] == "hostile"

    def test_talk_to_absent_npc_raises(self, tavern_game):
        with pytest.raises(NodeActionError, match="nobody"):
            tavern_game.node_actions.talk("nobody")

    def test_talk_requires_authored_action(self, node_game):
        # lab_square authors gather_rumors/read_job_board but not talk
        with pytest.raises(NodeActionError, match="talk"):
            node_game.node_actions.talk("tavernkeep")


class TestShop:
    def test_shop_returns_inventory_at_listed_prices(self, tavern_game):
        result = tavern_game.node_actions.shop("tavernkeep")
        assert result["refused"] is False
        prices = {item["item_id"]: item["price"] for item in result["inventory"]}
        assert prices == {"ale": 10, "room_night": 20}

    def test_friendly_disposition_discounts_prices(self, tavern_game):
        result = tavern_game.node_actions.shop("friendly")
        prices = {item["item_id"]: item["price"] for item in result["inventory"]}
        assert prices == {"ale": 9, "room_night": 18}

    def test_hostile_npc_refuses_service(self, tavern_game):
        result = tavern_game.node_actions.shop("grump")
        assert result["refused"] is True
        assert result["dialogue"] == "Get out, says grump."
        assert "inventory" not in result

    def test_shop_with_shopless_npc_raises(self, tavern_game):
        npc = tavern_game.npc_manager.get_npc("tavernkeep")
        npc.shop = None
        with pytest.raises(NodeActionError, match="shop"):
            tavern_game.node_actions.shop("tavernkeep")


class TestRest:
    def test_rest_routes_to_party_rest(self, tavern_game):
        hero = tavern_game.party.characters[0]
        hero.current_hp = 1

        result = tavern_game.node_actions.rest("long")

        assert hero.current_hp == hero.max_hp
        assert result.rest_type == "long"

    def test_rest_requires_authored_action(self, node_game):
        with pytest.raises(NodeActionError, match="rest"):
            node_game.node_actions.rest("long")


class TestGatherRumors:
    def test_rumors_from_npcs_present(self, tavern_game):
        # gather_rumors is authored on lab_square, not lab_tavern; author it
        # here to exercise NPC-sourced rumors.
        tavern_game.dungeon["nodes"]["lab_tavern"]["actions"].append("gather_rumors")

        result = tavern_game.node_actions.gather_rumors()

        texts = [r["text"] for r in result["rumors"]]
        assert "tavernkeep general rumor" in texts
        assert "tavernkeep local lore" in texts

    def test_hostile_npc_refuses_rumors(self, tavern_game):
        tavern_game.dungeon["nodes"]["lab_tavern"]["actions"].append("gather_rumors")

        result = tavern_game.node_actions.gather_rumors()

        refusing = [r["npc_id"] for r in result["refusals"]]
        assert "grump" in refusing
        sharing = {r["npc_id"] for r in result["rumors"]}
        assert "grump" not in sharing

    def test_friendly_npc_with_extra_hints_shares_quest_hooks(self, tavern_game):
        tavern_game.dungeon["nodes"]["lab_tavern"]["actions"].append("gather_rumors")
        quest_manager = QuestManager()
        quest_manager.load_quests_from_dict(
            {
                "quests": [
                    {
                        "id": "investigate_crypt",
                        "name": "The Crypt Problem",
                        "description": "Strange lights at the crypt.",
                        "unlocked_by_default": True,
                    }
                ]
            }
        )
        tavern_game.quest_manager = quest_manager

        result = tavern_game.node_actions.gather_rumors()

        hook_texts = [r["text"] for r in result["rumors"] if r["npc_id"] == "friendly"]
        assert "Strange lights at the crypt." in hook_texts
        neutral_texts = [r["text"] for r in result["rumors"] if r["npc_id"] == "tavernkeep"]
        assert "Strange lights at the crypt." not in neutral_texts

    def test_no_npcs_yields_empty_rumors(self, node_game):
        # lab_square authors gather_rumors and has no NPCs
        result = node_game.node_actions.gather_rumors()
        assert result["rumors"] == []
        assert result["refusals"] == []


class TestReadJobBoard:
    def test_postings_from_available_quests(self, node_game):
        quest_manager = QuestManager()
        quest_manager.load_quests_from_dict(
            {
                "quests": [
                    {
                        "id": "investigate_crypt",
                        "name": "The Crypt Problem",
                        "description": "Strange lights at the crypt.",
                        "unlocked_by_default": True,
                    },
                    {
                        "id": "locked_quest",
                        "name": "Locked",
                        "description": "Not yet.",
                        "unlocked_by_default": False,
                    },
                ]
            }
        )
        node_game.quest_manager = quest_manager

        result = node_game.node_actions.read_job_board()

        assert result["postings"] == [
            {
                "quest_id": "investigate_crypt",
                "name": "The Crypt Problem",
                "description": "Strange lights at the crypt.",
            }
        ]

    def test_no_quest_manager_yields_empty_postings(self, node_game):
        node_game.quest_manager = None
        result = node_game.node_actions.read_job_board()
        assert result["postings"] == []

    def test_requires_authored_action(self, tavern_game):
        with pytest.raises(NodeActionError, match="read_job_board"):
            tavern_game.node_actions.read_job_board()


class TestExamine:
    def test_examine_success_returns_success_prose(self, node_game):
        node_game.enter_node("lab_gate")
        # DC 1 with a non-negative modifier cannot fail (d20 minimum is 1)
        node_game.dungeon["nodes"]["lab_gate"]["actions"][0]["gate"]["dc"] = 1
        hero = node_game.party.characters[0]

        result = node_game.node_actions.examine("examine_symbol", hero)

        assert result["success"] is True
        assert result["prose"].startswith("The symbol is a ward")
        assert result["check"]["skill"] == "religion"
        assert result["check"]["dc"] == 1

    def test_examine_failure_returns_failure_prose(self, node_game):
        node_game.enter_node("lab_gate")
        # DC 40 cannot be reached by d20 + a level-1 modifier
        node_game.dungeon["nodes"]["lab_gate"]["actions"][0]["gate"]["dc"] = 40
        hero = node_game.party.characters[0]

        result = node_game.node_actions.examine("examine_symbol", hero)

        assert result["success"] is False
        assert result["prose"].startswith("The scratches look old")

    def test_examine_unknown_action_raises(self, node_game):
        node_game.enter_node("lab_gate")
        hero = node_game.party.characters[0]
        with pytest.raises(NodeActionError, match="examine_wall"):
            node_game.node_actions.examine("examine_wall", hero)

    def test_examine_emits_skill_check_via_engine(self, node_game):
        """The check must go through Character.make_skill_check (the d20-test
        primitive), not a private dice path."""
        node_game.enter_node("lab_gate")
        hero = node_game.party.characters[0]
        calls = {}
        original = hero.make_skill_check

        def spy(skill, dc, skills_data, **kwargs):
            calls["skill"] = skill
            calls["dc"] = dc
            return original(skill, dc, skills_data, **kwargs)

        hero.make_skill_check = spy

        node_game.node_actions.examine("examine_symbol", hero)

        assert calls == {"skill": "religion", "dc": 12}


class TestExamineErrorContract:
    def test_examine_non_examine_action_names_the_problem(self, tavern_game):
        """'talk' exists at the tavern; the error must say it isn't examinable,
        not falsely claim the action doesn't exist."""
        hero = tavern_game.party.characters[0]
        with pytest.raises(NodeActionError, match="examin"):
            tavern_game.node_actions.examine("talk", hero)

    def test_examine_unknown_gate_skill_raises_node_action_error(self, node_game):
        """A typoed authored skill fails inside the NodeActionError contract,
        not as a bare KeyError."""
        node_game.enter_node("lab_gate")
        node_game.dungeon["nodes"]["lab_gate"]["actions"][0]["gate"]["skill"] = "Religion"
        hero = node_game.party.characters[0]
        with pytest.raises(NodeActionError, match="Religion"):
            node_game.node_actions.examine("examine_symbol", hero)


class TestNpcViewUnification:
    def test_enter_node_npcs_carry_disposition(self, node_game):
        """enter_node and interactions() must present the same NPC shape."""
        context = node_game.enter_node("lab_tavern")
        by_id = {npc["id"]: npc for npc in context["npcs"]}
        assert by_id["friendly"]["disposition"] == "friendly"
        assert by_id["grump"]["disposition"] == "hostile"


class TestAuthoredQuestHints:
    def test_gather_rumors_prefers_authored_npc_hint(self, tavern_game):
        from dnd_engine.core.quest import QuestManager

        tavern_game.dungeon["nodes"]["lab_tavern"]["actions"].append("gather_rumors")
        quest_manager = QuestManager()
        quest_manager.load_quests_from_dict(
            {
                "quests": [
                    {
                        "id": "investigate_crypt",
                        "name": "The Crypt Problem",
                        "description": "Strange lights at the crypt.",
                        "unlocked_by_default": True,
                        "npc_hints": {
                            "available": {"friendly": "Psst - lights up at the crypt, love."}
                        },
                    }
                ]
            }
        )
        tavern_game.quest_manager = quest_manager

        result = tavern_game.node_actions.gather_rumors()

        friendly_texts = [r["text"] for r in result["rumors"] if r["npc_id"] == "friendly"]
        assert "Psst - lights up at the crypt, love." in friendly_texts
        assert "Strange lights at the crypt." not in friendly_texts
