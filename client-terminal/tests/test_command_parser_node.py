# ABOUTME: Unit tests for node-surface intents in the command parser (issue #684 slice 5).
# ABOUTME: Covers enter_node routing, node social intents, surface remapping, and fuzzy node names.

import pytest

from terminal_client.nlp.command_parser import CommandParser

LAB_NODES = ["Lab Square", "The Testing Tankard", "The Old Gate"]


class NodeContextProvider:
    """Context provider fake with node-surface awareness."""

    def __init__(
        self,
        nodes: list[str] | None = None,
        npcs: list[str] | None = None,
        items: list[str] | None = None,
        node_surface: bool = True,
        in_combat: bool = False,
    ):
        self._nodes = nodes if nodes is not None else list(LAB_NODES)
        self._npcs = npcs or []
        self._items = items or []
        self._node_surface = node_surface
        self._in_combat = in_combat

    def get_available_enemies(self) -> list[str]:
        return []

    def get_available_items(self) -> list[str]:
        return self._items

    def get_available_spells(self) -> list[str]:
        return []

    def get_available_npcs(self) -> list[str]:
        return self._npcs

    def get_party_member_names(self) -> list[str]:
        return []

    def is_in_combat(self) -> bool:
        return self._in_combat

    def is_node_surface(self) -> bool:
        return self._node_surface

    def get_available_nodes(self) -> list[str]:
        return self._nodes


class LegacyContextProvider:
    """Pre-node provider shape: no node methods at all."""

    def get_available_enemies(self) -> list[str]:
        return []

    def get_available_items(self) -> list[str]:
        return []

    def get_available_spells(self) -> list[str]:
        return []

    def get_available_npcs(self) -> list[str]:
        return []

    def get_party_member_names(self) -> list[str]:
        return []

    def is_in_combat(self) -> bool:
        return False


@pytest.fixture
def node_parser():
    return CommandParser(context_provider=NodeContextProvider())


@pytest.fixture
def grid_parser():
    return CommandParser(context_provider=NodeContextProvider(node_surface=False))


class TestEnterNodeIntent:
    """Prose destination commands resolve to enter_node on a node surface."""

    @pytest.mark.parametrize(
        "text,expected_node",
        [
            ("go to the tankard", "The Testing Tankard"),
            ("visit the old gate", "The Old Gate"),
            ("head to lab square", "Lab Square"),
            ("go tankard", "The Testing Tankard"),
            ("walk to the testing tankard", "The Testing Tankard"),
            ("enter the tankard", "The Testing Tankard"),
        ],
    )
    def test_prose_routes_to_enter_node(self, node_parser, text, expected_node):
        result = node_parser.parse(text)
        assert result.success, result.error
        assert result.action == "enter_node"
        assert result.params["node"] == expected_node

    def test_typo_in_node_name_fuzzy_matches(self, node_parser):
        result = node_parser.parse("go to the tankerd")
        assert result.success, result.error
        assert result.action == "enter_node"
        assert result.params["node"] == "The Testing Tankard"

    def test_unknown_node_flags_unmatched(self, node_parser):
        result = node_parser.parse("go to zzqxv")
        assert result.action == "enter_node"
        assert result.params.get("node_unmatched") is True

    def test_bare_destination_keyword_prompts_for_node(self, node_parser):
        result = node_parser.parse("go")
        assert result.action == "enter_node"
        assert "node" not in result.params


class TestNodeSocialIntents:
    """Node vocabulary actions parse from natural phrasings."""

    @pytest.mark.parametrize(
        "text",
        ["gather rumors", "ask around", "rumors", "gossip"],
    )
    def test_gather_rumors(self, node_parser, text):
        result = node_parser.parse(text)
        assert result.success, result.error
        assert result.action == "gather_rumors"

    @pytest.mark.parametrize(
        "text",
        ["read the job board", "job board", "read board", "notice board", "read the board"],
    )
    def test_read_job_board(self, node_parser, text):
        result = node_parser.parse(text)
        assert result.success, result.error
        assert result.action == "read_job_board"

    def test_read_of_other_things_is_not_job_board(self, node_parser):
        # "read the plaque" must not open the job board
        result = node_parser.parse("read the plaque")
        assert result.action != "read_job_board"

    def test_examine_target_not_hijacked_by_inventory(self):
        # On a node, examine targets are authored actions; inventory names
        # (Scimitar fuzzy-matches "altar") must not substitute the target.
        parser = CommandParser(context_provider=NodeContextProvider(items=["Scimitar"]))
        result = parser.parse("examine the altar")
        assert result.success, result.error
        assert result.action == "look"
        assert result.params["item"] == "altar"

    @pytest.mark.parametrize("text", ["depart", "leave", "set out"])
    def test_depart(self, node_parser, text):
        result = node_parser.parse(text)
        assert result.success, result.error
        assert result.action == "depart"

    def test_talk_still_matches_npcs_on_node_surface(self):
        parser = CommandParser(context_provider=NodeContextProvider(npcs=["Marta"]))
        result = parser.parse("talk to marta")
        assert result.success, result.error
        assert result.action == "talk"
        assert result.params["npc"] == "Marta"


class TestSurfaceRemap:
    """The same keywords resolve per surface: directions on grid, nodes in settlements."""

    def test_go_direction_still_moves_on_grid(self, grid_parser):
        result = grid_parser.parse("go north")
        assert result.success, result.error
        assert result.action == "move"
        assert result.params["direction"] == "north"

    def test_visit_remaps_to_move_on_grid(self, grid_parser):
        result = grid_parser.parse("visit the tavern")
        assert result.action == "move"

    def test_depart_remaps_to_move_on_grid(self, grid_parser):
        result = grid_parser.parse("leave")
        assert result.action == "move"

    def test_leave_during_grid_combat_means_flee(self):
        parser = CommandParser(
            context_provider=NodeContextProvider(node_surface=False, in_combat=True)
        )
        result = parser.parse("leave")
        assert result.success, result.error
        assert result.action == "flee"

    def test_read_on_grid_is_not_a_settlement_error(self, grid_parser):
        result = grid_parser.parse("read the inscription")
        assert result.error is None or "settlement" not in result.error

    def test_validation_errors_use_spaced_names(self, grid_parser):
        result = grid_parser.parse("gather rumors")
        assert "gather rumors" in result.error
        assert "gather_rumors" not in result.error

    def test_gather_rumors_rejected_on_grid(self, grid_parser):
        result = grid_parser.parse("gather rumors")
        assert not result.success
        assert "settlement" in result.error

    def test_read_job_board_rejected_on_grid(self, grid_parser):
        result = grid_parser.parse("job board")
        assert not result.success
        assert "settlement" in result.error

    @pytest.mark.parametrize("text", ["search", "take the sword", "unlock north"])
    def test_grid_only_actions_rejected_on_node_surface(self, node_parser, text):
        result = node_parser.parse(text)
        assert not result.success
        assert "settlement" in result.error


class TestNodeCombatValidation:
    """Node actions are exploration-only."""

    @pytest.mark.parametrize("text", ["gather rumors", "job board", "depart", "go to the tankard"])
    def test_node_actions_rejected_in_combat(self, text):
        parser = CommandParser(context_provider=NodeContextProvider(in_combat=True))
        result = parser.parse(text)
        assert not result.success
        assert "combat" in result.error


class TestAdapterNodeIntegration:
    """CLIContextAdapter over a real GameState on the lab settlement."""

    @pytest.fixture
    def lab_adapter(self):
        from terminal_client.nlp.cli_context_adapter import CLIContextAdapter
        from tests.support import make_lab_game_state

        return CLIContextAdapter(make_lab_game_state())

    def test_reports_node_surface(self, lab_adapter):
        assert lab_adapter.is_node_surface() is True

    def test_lists_node_names(self, lab_adapter):
        assert lab_adapter.get_available_nodes() == [
            "Lab Square",
            "The Testing Tankard",
            "The Old Gate",
        ]

    def test_npc_lookup_keys_by_node_id(self, lab_adapter):
        class RecordingNPCManager:
            def __init__(self):
                self.queried_with = None

            def get_npcs_in_room(self, location_id):
                self.queried_with = location_id
                return []

        manager = RecordingNPCManager()
        lab_adapter.game_state.npc_manager = manager
        assert lab_adapter.get_available_npcs() == []
        assert manager.queried_with == "lab_square"

    def test_get_available_items_over_real_engine_on_node(self, lab_adapter):
        # Regression for #691: adapter item lookup must survive real
        # GameState/Inventory objects (no mocked attribute names).
        assert isinstance(lab_adapter.get_available_items(), list)

    def test_get_available_items_over_real_engine_on_grid(self):
        from terminal_client.nlp.cli_context_adapter import CLIContextAdapter
        from tests.support import make_lab_game_state

        grid_adapter = CLIContextAdapter(make_lab_game_state("lab_dungeon"))
        assert isinstance(grid_adapter.get_available_items(), list)

    def test_parser_end_to_end_over_real_adapter(self, lab_adapter):
        parser = CommandParser(context_provider=lab_adapter)
        result = parser.parse("head to the old gate")
        assert result.success, result.error
        assert result.action == "enter_node"
        assert result.params["node"] == "The Old Gate"


class TestLegacyProviderCompatibility:
    """Providers without node methods degrade to grid behavior."""

    def test_move_parses_with_legacy_provider(self):
        parser = CommandParser(context_provider=LegacyContextProvider())
        result = parser.parse("go north")
        assert result.success, result.error
        assert result.action == "move"

    def test_node_actions_rejected_with_legacy_provider(self):
        parser = CommandParser(context_provider=LegacyContextProvider())
        result = parser.parse("gather rumors")
        assert not result.success
        assert "settlement" in result.error
