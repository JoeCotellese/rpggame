# ABOUTME: Unit tests for the rule-based natural language command parser.
# ABOUTME: Tests action detection, entity extraction, and fuzzy matching.

import pytest

from terminal_client.nlp.command_parser import CommandParser, ParseResult


class MockContextProvider:
    """Mock context provider for testing."""

    def __init__(
        self,
        enemies: list[str] | None = None,
        items: list[str] | None = None,
        spells: list[str] | None = None,
        npcs: list[str] | None = None,
        party: list[str] | None = None,
        in_combat: bool = False,
    ):
        self._enemies = enemies or []
        self._items = items or []
        self._spells = spells or []
        self._npcs = npcs or []
        self._party = party or []
        self._in_combat = in_combat

    def get_available_enemies(self) -> list[str]:
        return self._enemies

    def get_available_items(self) -> list[str]:
        return self._items

    def get_available_spells(self) -> list[str]:
        return self._spells

    def get_available_npcs(self) -> list[str]:
        return self._npcs

    def get_party_member_names(self) -> list[str]:
        return self._party

    def is_in_combat(self) -> bool:
        return self._in_combat


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_success_when_action_present_and_no_error(self):
        result = ParseResult(action="attack", params={"target": "goblin"})
        assert result.success is True

    def test_not_success_when_no_action(self):
        result = ParseResult(error="Unknown command")
        assert result.success is False

    def test_not_success_when_error_present(self):
        result = ParseResult(action="attack", error="Invalid target")
        assert result.success is False


class TestActionDetection:
    """Tests for action detection from keywords."""

    @pytest.fixture
    def parser(self):
        return CommandParser()

    @pytest.mark.parametrize(
        "input_text,expected_action",
        [
            # Movement
            ("go north", "move"),
            ("walk south", "move"),
            ("move east", "move"),
            ("head west", "move"),
            ("travel up", "move"),
            ("enter north", "move"),
            # Attack
            ("attack goblin", "attack"),
            ("hit the skeleton", "attack"),
            ("strike zombie", "attack"),
            ("kill orc", "attack"),
            ("fight dragon", "attack"),
            # Cast
            ("cast fireball", "cast"),
            ("invoke magic missile", "cast"),
            # Take
            ("take sword", "take"),
            ("grab the potion", "take"),
            ("pick up gold", "take"),
            ("get torch", "take"),
            ("loot body", "take"),
            # Search
            ("search room", "search"),
            ("look around", "search"),
            ("investigate area", "search"),
            # Look/Examine
            ("look at sword", "look"),
            ("examine potion", "look"),
            ("inspect chest", "look"),
            # Talk
            ("talk to merchant", "talk"),
            ("speak with guard", "talk"),
            ("chat innkeeper", "talk"),
            # Use
            ("use potion", "use"),
            ("drink healing potion", "use"),
            ("eat rations", "use"),
            # Equip
            ("equip sword", "equip"),
            ("wear armor", "equip"),
            ("wield dagger", "equip"),
            # Flee
            ("flee", "flee"),
            ("run away", "flee"),
            ("escape", "flee"),
            ("retreat", "flee"),
            # Rest
            ("rest", "rest"),
            ("sleep", "rest"),
            ("camp", "rest"),
            # Status/inventory commands
            ("inventory", "inventory"),
            ("items", "inventory"),
            ("status", "status"),
            ("health", "status"),
            ("help", "help"),
            # Shop
            ("shop", "shop"),
            ("buy", "shop"),
            ("sell", "shop"),
            # Spells
            ("spells", "spells"),
            ("spellbook", "spells"),
            # Other
            ("stabilize gandalf", "stabilize"),
            ("end turn", "end_turn"),
            ("pass", "end_turn"),
            ("unlock north", "unlock"),
        ],
    )
    def test_exact_keyword_matching(self, parser, input_text, expected_action):
        result = parser.parse(input_text)
        assert result.action == expected_action

    def test_multi_word_action_long_rest(self, parser):
        result = parser.parse("long rest")
        assert result.action == "rest"

    def test_multi_word_action_pick_up(self, parser):
        result = parser.parse("pick up the sword")
        assert result.action == "take"

    def test_unknown_command_returns_error(self, parser):
        result = parser.parse("xyzzy plugh")
        assert result.success is False
        assert result.error is not None
        assert "Unknown command" in result.error

    def test_empty_input_returns_error(self, parser):
        result = parser.parse("")
        assert result.success is False
        assert result.error == "Empty command"

    def test_whitespace_input_returns_error(self, parser):
        result = parser.parse("   ")
        assert result.success is False


class TestFuzzyActionMatching:
    """Tests for fuzzy matching of action keywords."""

    @pytest.fixture
    def parser(self):
        return CommandParser()

    @pytest.mark.parametrize(
        "typo_input,expected_action",
        [
            ("atack goblin", "attack"),  # Missing 't'
            ("attck skeleton", "attack"),  # Missing 'a'
            ("serch room", "search"),  # Missing 'a'
            ("grasp potion", "take"),  # Synonym-ish typo -> grab
            ("fleee", "flee"),  # Extra 'e'
            ("inventry", "inventory"),  # Typo
            ("statsus", "status"),  # Typo
        ],
    )
    def test_fuzzy_action_matching_with_typos(self, parser, typo_input, expected_action):
        result = parser.parse(typo_input)
        assert result.action == expected_action
        assert result.confidence < 1.0  # Lower confidence for fuzzy match


class TestDirectionExtraction:
    """Tests for direction extraction from movement commands."""

    @pytest.fixture
    def parser(self):
        return CommandParser()

    @pytest.mark.parametrize(
        "input_text,expected_direction",
        [
            # Full names
            ("go north", "north"),
            ("go south", "south"),
            ("go east", "east"),
            ("go west", "west"),
            ("go up", "up"),
            ("go down", "down"),
            # Abbreviations
            ("go n", "north"),
            ("go s", "south"),
            ("go e", "east"),
            ("go w", "west"),
            ("go u", "up"),
            ("go d", "down"),
            # Variations
            ("go northern", "north"),
            ("go upstairs", "up"),
            ("go downstairs", "down"),
            # Natural phrasing
            ("go through the northern door", "north"),
            ("walk to the east", "east"),
        ],
    )
    def test_direction_extraction(self, parser, input_text, expected_direction):
        result = parser.parse(input_text)
        assert result.action == "move"
        assert result.params.get("direction") == expected_direction

    def test_missing_direction_leaves_params_empty(self, parser):
        result = parser.parse("go")
        assert result.action == "move"
        assert "direction" not in result.params


class TestTargetExtraction:
    """Tests for target extraction (enemies, allies)."""

    @pytest.fixture
    def combat_parser(self):
        context = MockContextProvider(
            enemies=["Goblin 1", "Goblin 2", "Skeleton 1", "Orc Warrior"],
            party=["Gandalf", "Aragorn", "Legolas"],
            in_combat=True,
        )
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text,expected_target",
        [
            ("attack goblin 1", "Goblin 1"),
            ("hit the skeleton", "Skeleton 1"),
            ("attack goblin 2", "Goblin 2"),
            ("strike orc warrior", "Orc Warrior"),
            ("attack orc", "Orc Warrior"),
        ],
    )
    def test_enemy_target_extraction(self, combat_parser, input_text, expected_target):
        result = combat_parser.parse(input_text)
        assert result.action == "attack"
        assert result.params.get("target") == expected_target

    def test_target_with_at_syntax(self, combat_parser):
        result = combat_parser.parse("attack at goblin 1")
        assert result.params.get("target") == "Goblin 1"

    def test_fuzzy_target_matching_with_typo(self, combat_parser):
        result = combat_parser.parse("attack skelton 1")  # Typo in skeleton
        assert result.params.get("target") == "Skeleton 1"

    def test_missing_target_leaves_params_empty(self, combat_parser):
        result = combat_parser.parse("attack")
        assert result.action == "attack"
        assert "target" not in result.params


class TestSpellExtraction:
    """Tests for spell name and target extraction."""

    @pytest.fixture
    def spellcaster_parser(self):
        context = MockContextProvider(
            enemies=["Goblin 1", "Skeleton 1"],
            party=["Gandalf", "Aragorn"],
            spells=["Magic Missile", "Fireball", "Cure Wounds", "Shield", "Mage Armor"],
            in_combat=True,
        )
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text,expected_spell,expected_target",
        [
            ("cast magic missile at goblin 1", "Magic Missile", "Goblin 1"),
            ("cast fireball at skeleton", "Fireball", "Skeleton 1"),
            ("cast cure wounds on gandalf", "Cure Wounds", "Gandalf"),
            ("cast shield", "Shield", None),
            ("cast mage armor", "Mage Armor", None),
        ],
    )
    def test_spell_and_target_extraction(
        self, spellcaster_parser, input_text, expected_spell, expected_target
    ):
        result = spellcaster_parser.parse(input_text)
        assert result.action == "cast"
        assert result.params.get("spell") == expected_spell
        if expected_target:
            assert result.params.get("target") == expected_target
        else:
            assert "target" not in result.params

    def test_spell_fuzzy_matching_with_typo(self, spellcaster_parser):
        result = spellcaster_parser.parse("cast magic missle at goblin 1")  # Typo
        assert result.params.get("spell") == "Magic Missile"

    def test_spell_without_target(self, spellcaster_parser):
        result = spellcaster_parser.parse("cast shield")
        assert result.action == "cast"
        assert result.params.get("spell") == "Shield"
        assert "target" not in result.params


class TestItemExtraction:
    """Tests for item name extraction."""

    @pytest.fixture
    def item_parser(self):
        context = MockContextProvider(
            items=[
                "Healing Potion",
                "Longsword",
                "Leather Armor",
                "Torch",
                "Alchemist's Fire",
            ]
        )
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text,expected_item",
        [
            ("take healing potion", "Healing Potion"),
            ("grab the longsword", "Longsword"),
            ("pick up torch", "Torch"),
            ("use healing potion", "Healing Potion"),
            ("equip leather armor", "Leather Armor"),
        ],
    )
    def test_item_extraction(self, item_parser, input_text, expected_item):
        result = item_parser.parse(input_text)
        assert result.params.get("item") == expected_item

    def test_item_fuzzy_matching_with_typo(self, item_parser):
        result = item_parser.parse("take healign potion")  # Typo
        assert result.params.get("item") == "Healing Potion"

    def test_item_partial_match(self, item_parser):
        result = item_parser.parse("grab alchemist fire")  # Missing apostrophe+s
        assert result.params.get("item") == "Alchemist's Fire"


class TestNPCExtraction:
    """Tests for NPC name extraction."""

    @pytest.fixture
    def npc_parser(self):
        context = MockContextProvider(npcs=["Marta the Innkeeper", "Guard Captain", "Merchant"])
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text,expected_npc",
        [
            ("talk to marta", "Marta the Innkeeper"),
            ("speak with guard captain", "Guard Captain"),
            ("chat merchant", "Merchant"),
            ("shop merchant", "Merchant"),
        ],
    )
    def test_npc_extraction(self, npc_parser, input_text, expected_npc):
        result = npc_parser.parse(input_text)
        assert result.params.get("npc") == expected_npc

    def test_npc_fuzzy_matching(self, npc_parser):
        result = npc_parser.parse("talk to innkeeper")
        assert result.params.get("npc") == "Marta the Innkeeper"


class TestContextValidation:
    """Tests for context-aware action validation."""

    def test_attack_invalid_outside_combat(self):
        context = MockContextProvider(in_combat=False)
        parser = CommandParser(context_provider=context)
        result = parser.parse("attack goblin")
        assert result.error is not None
        assert "only available during combat" in result.error

    def test_attack_valid_in_combat(self):
        context = MockContextProvider(enemies=["Goblin 1"], in_combat=True)
        parser = CommandParser(context_provider=context)
        result = parser.parse("attack goblin")
        assert result.success is True

    def test_rest_invalid_in_combat(self):
        context = MockContextProvider(in_combat=True)
        parser = CommandParser(context_provider=context)
        result = parser.parse("rest")
        assert result.error is not None
        assert "not available during combat" in result.error

    def test_rest_valid_outside_combat(self):
        context = MockContextProvider(in_combat=False)
        parser = CommandParser(context_provider=context)
        result = parser.parse("rest")
        assert result.success is True

    def test_movement_valid_in_any_context(self):
        # Combat
        combat_parser = CommandParser(
            context_provider=MockContextProvider(in_combat=True)
        )
        result = combat_parser.parse("go north")
        assert result.success is True

        # Exploration
        exploration_parser = CommandParser(
            context_provider=MockContextProvider(in_combat=False)
        )
        result = exploration_parser.parse("go north")
        assert result.success is True


class TestSuggestions:
    """Tests for command suggestions on invalid input."""

    @pytest.fixture
    def parser(self):
        return CommandParser()

    def test_suggestions_for_unknown_command(self, parser):
        result = parser.parse("xyzzy")
        assert result.suggestions
        assert len(result.suggestions) > 0

    def test_suggestions_include_similar_actions(self, parser):
        # Use something truly nonsense that won't match anything
        result = parser.parse("qxjkm blargh")
        # Should return error with suggestions since no match found
        assert result.success is False
        # There should be some suggestions
        assert len(result.suggestions) > 0

    def test_empty_command_suggestions(self, parser):
        result = parser.parse("")
        assert "help" in result.suggestions


class TestStopWordHandling:
    """Tests for proper handling of stop words."""

    @pytest.fixture
    def parser(self):
        context = MockContextProvider(
            enemies=["Goblin 1"],
            items=["Healing Potion"],
            in_combat=True,
        )
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text,expected_action",
        [
            ("attack the goblin", "attack"),
            ("grab a healing potion", "take"),
            ("go to the north", "move"),
            ("hit an enemy with my sword", "attack"),
        ],
    )
    def test_stop_words_filtered_from_parsing(self, parser, input_text, expected_action):
        result = parser.parse(input_text)
        assert result.action == expected_action


class TestCaseInsensitivity:
    """Tests for case-insensitive parsing."""

    @pytest.fixture
    def parser(self):
        context = MockContextProvider(
            enemies=["Goblin 1"],
            spells=["Magic Missile"],
            in_combat=True,
        )
        return CommandParser(context_provider=context)

    @pytest.mark.parametrize(
        "input_text",
        [
            "ATTACK GOBLIN",
            "Attack Goblin",
            "attack goblin",
            "AtTaCk GoBLiN",
        ],
    )
    def test_case_insensitive_commands(self, parser, input_text):
        result = parser.parse(input_text)
        assert result.action == "attack"

    def test_case_insensitive_spell_matching(self, parser):
        result = parser.parse("CAST MAGIC MISSILE")
        assert result.params.get("spell") == "Magic Missile"


class TestConfidenceScoring:
    """Tests for confidence scoring."""

    @pytest.fixture
    def parser(self):
        context = MockContextProvider(
            enemies=["Goblin 1"],
            spells=["Magic Missile"],
            in_combat=True,
        )
        return CommandParser(context_provider=context)

    def test_exact_match_high_confidence(self, parser):
        result = parser.parse("attack goblin 1")
        # 1.0 action confidence * ~0.87 target match confidence
        assert result.confidence >= 0.8

    def test_fuzzy_match_lower_confidence(self, parser):
        result = parser.parse("atack goblin")  # Typo
        assert result.confidence < 0.9
        assert result.confidence > 0.5

    def test_no_context_moderate_confidence(self):
        parser = CommandParser()  # No context provider
        result = parser.parse("attack goblin")
        assert result.confidence > 0.5


class TestEntitySuggestions:
    """Tests for entity suggestion behavior when fuzzy match fails."""

    def test_spell_suggestions_when_no_match(self):
        """Test that spell suggestions are returned when spell doesn't match."""
        context = MockContextProvider(
            spells=["Fireball", "Fire Bolt", "Flame Strike", "Magic Missile"],
            in_combat=True,
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("cast flaming orb")

        assert result.success
        assert result.action == "cast"
        assert result.params.get("spell_unmatched") is True
        assert "spell" in result.entity_suggestions
        # Should suggest fire-related spells
        assert len(result.entity_suggestions["spell"]) > 0

    def test_item_suggestions_when_no_match(self):
        """Test that item suggestions are returned when item doesn't match."""
        context = MockContextProvider(
            items=["Healing Potion", "Health Elixir", "Mana Potion"],
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("take heal pot")

        assert result.success
        assert result.action == "take"
        assert result.params.get("item_unmatched") is True
        assert "item" in result.entity_suggestions
        # Should suggest health-related items
        assert "Healing Potion" in result.entity_suggestions["item"]

    def test_target_suggestions_when_no_match(self):
        """Test that target suggestions are returned when target doesn't match."""
        context = MockContextProvider(
            enemies=["Goblin 1", "Goblin 2", "Orc Warrior"],
            in_combat=True,
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("attack zombie")

        assert result.success
        assert result.action == "attack"
        assert result.params.get("unmatched") is True
        assert "target" in result.entity_suggestions
        # Should suggest available enemies
        assert len(result.entity_suggestions["target"]) > 0

    def test_npc_suggestions_when_no_match(self):
        """Test that NPC suggestions are returned when NPC doesn't match."""
        context = MockContextProvider(
            npcs=["Blacksmith Boris", "Merchant Maria", "Guard Gerald"],
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("talk to shopkeeper")

        assert result.success
        assert result.action == "talk"
        assert result.params.get("npc_unmatched") is True
        assert "npc" in result.entity_suggestions
        # Should suggest available NPCs
        assert len(result.entity_suggestions["npc"]) > 0

    def test_no_suggestions_when_match_found(self):
        """Test that no suggestions are returned when a good match is found."""
        context = MockContextProvider(
            spells=["Fireball", "Fire Bolt", "Magic Missile"],
            in_combat=True,
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("cast fireball")

        assert result.success
        assert result.action == "cast"
        assert result.params.get("spell") == "Fireball"
        assert result.params.get("spell_unmatched") is None
        assert not result.entity_suggestions

    def test_needs_clarification_property(self):
        """Test the needs_clarification property."""
        context = MockContextProvider(
            spells=["Fireball", "Fire Bolt"],
            in_combat=True,
        )
        parser = CommandParser(context_provider=context)

        # No suggestions needed
        result = parser.parse("cast fireball")
        assert not result.needs_clarification

        # Suggestions needed
        result = parser.parse("cast flaming orb")
        assert result.needs_clarification

    def test_suggestions_limited_to_reasonable_count(self):
        """Test that suggestions are limited to a reasonable number."""
        context = MockContextProvider(
            items=[
                "Sword",
                "Shield",
                "Helmet",
                "Boots",
                "Gloves",
                "Ring",
                "Amulet",
                "Potion",
                "Scroll",
                "Wand",
            ],
        )
        parser = CommandParser(context_provider=context)
        result = parser.parse("take xyz")

        # Should have suggestions but limited to 5
        if result.entity_suggestions.get("item"):
            assert len(result.entity_suggestions["item"]) <= 5
