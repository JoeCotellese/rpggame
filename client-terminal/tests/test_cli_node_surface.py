# ABOUTME: Integration tests for the CLI node-surface branch (issue #684 slice 5).
# ABOUTME: Covers three-zone render, numbered/prose hybrid input, seam arrivals, and reset.

from unittest.mock import Mock, patch

import pytest

from terminal_client.ui.cli import CLI
from terminal_client.ui.rich_ui import console
from tests.support import make_lab_game_state


def _make_cli(dungeon_name: str) -> CLI:
    return CLI(make_lab_game_state(dungeon_name), Mock(), "lab", auto_save_enabled=False)


@pytest.fixture
def node_cli():
    return _make_cli("lab_settlement")


@pytest.fixture
def grid_cli():
    return _make_cli("lab_dungeon")


def _capture(callable_, *args, **kwargs) -> str:
    with console.capture() as cap:
        callable_(*args, **kwargs)
    return cap.get()


class TestDisplayNode:
    """Three zones: status strip, prose, numbered actions."""

    def test_renders_node_name_and_description(self, node_cli):
        output = _capture(node_cli.display_node)
        assert "Lab Square" in output
        assert "notice board" in output

    def test_status_strip_has_settlement_time_and_gold(self, node_cli):
        output = _capture(node_cli.display_node)
        assert "Lab Settlement" in output
        assert "gp" in output

    def test_renders_numbered_actions_with_go_elsewhere(self, node_cli):
        output = _capture(node_cli.display_node)
        assert "1." in output
        assert "Go elsewhere" in output

    def test_display_location_dispatches_by_surface(self, node_cli, grid_cli):
        node_output = _capture(node_cli.display_location)
        assert "Lab Square" in node_output
        grid_output = _capture(grid_cli.display_location)
        assert "Lab Dungeon Entry" in grid_output


class TestNodeMenu:
    """Menu contents reflect the authored actions of the current node."""

    def test_lab_square_menu(self, node_cli):
        _capture(node_cli.display_node)
        labels = [item["label"] for item in node_cli._node_menu]
        assert any("rumors" in label.lower() for label in labels)
        assert any("job board" in label.lower() for label in labels)
        assert any("Go elsewhere" in label for label in labels)
        assert not any("Talk" in label for label in labels)
        assert not any("Rest" in label for label in labels)
        assert not any("Depart" in label for label in labels)

    def test_lab_gate_menu_brackets_mechanics(self, node_cli):
        node_cli.game_state.enter_node("lab_gate")
        _capture(node_cli.display_node)
        labels = [item["label"] for item in node_cli._node_menu]
        assert any("[Religion DC 12]" in label for label in labels)
        assert any("Depart" in label and "[Athletics DC 10]" in label for label in labels)


class TestNumberedDispatch:
    """A typed number runs the corresponding menu item."""

    def test_number_runs_menu_item(self, node_cli):
        _capture(node_cli.display_node)
        rumor_index = next(
            i for i, item in enumerate(node_cli._node_menu, 1) if "rumors" in item["label"].lower()
        )
        output = _capture(node_cli.process_node_command, str(rumor_index))
        assert "no one" in output.lower()

    def test_out_of_range_number_reports_bounds(self, node_cli):
        _capture(node_cli.display_node)
        output = _capture(node_cli.process_node_command, "99")
        assert "number" in output.lower()


class TestProseInput:
    """Typed prose routes through the parser to node intents."""

    def test_go_to_node_by_prose(self, node_cli):
        _capture(node_cli.display_node)
        output = _capture(node_cli.process_node_command, "go to the tankard")
        assert node_cli.game_state.current_node_id == "lab_tavern"
        assert "Testing Tankard" in output

    def test_typo_still_resolves_node(self, node_cli):
        _capture(node_cli.display_node)
        _capture(node_cli.process_node_command, "visit the tankerd")
        assert node_cli.game_state.current_node_id == "lab_tavern"

    def test_gather_rumors_by_prose(self, node_cli):
        output = _capture(node_cli.process_node_command, "gather rumors")
        assert "no one" in output.lower()

    def test_read_job_board_by_prose(self, node_cli):
        output = _capture(node_cli.process_node_command, "read the job board")
        assert "board" in output.lower()

    def test_grid_only_command_gets_friendly_error(self, node_cli):
        output = _capture(node_cli.process_node_command, "search")
        assert "settlement" in output.lower()
        assert "unknown command" not in output.lower()

    def test_look_rerenders_node(self, node_cli):
        output = _capture(node_cli.process_node_command, "look")
        assert "Lab Square" in output

    def test_fuzzy_help_shows_settlement_help(self, node_cli):
        output = _capture(node_cli.process_node_command, "commands")
        assert "Settlement Commands" in output

    def test_menu_reprints_when_actions_change(self, node_cli):
        _capture(node_cli.display_node)
        assert any("job board" in item["label"].lower() for item in node_cli._node_menu)
        # Simulate node state changing between render and dispatch
        node_cli.game_state.dungeon["nodes"]["lab_square"]["actions"].remove("read_job_board")
        output = _capture(node_cli.process_node_command, "1")
        assert not any("job board" in item["label"].lower() for item in node_cli._node_menu)
        assert "What do you do?" in output


class TestNodeRest:
    """Rest routes through the engine's node dispatch and respects authoring."""

    def test_rest_unauthored_node_declines(self, node_cli):
        output = _capture(node_cli.process_node_command, "rest")
        assert "nowhere to rest" in output.lower()

    def test_rest_authored_node_heals(self, node_cli):
        node_cli.game_state.enter_node("lab_tavern")
        hero = node_cli.game_state.party.characters[0]
        hero.current_hp = 1
        with patch("builtins.input", return_value="2"):
            _capture(node_cli.process_node_command, "rest")
        assert hero.current_hp == hero.max_hp


class TestGoElsewhere:
    """The node list hides behind Go elsewhere."""

    def test_go_elsewhere_lists_and_enters(self, node_cli):
        _capture(node_cli.display_node)
        with patch("builtins.input", return_value="2"):
            output = _capture(node_cli.handle_go_elsewhere)
        assert node_cli.game_state.current_node_id == "lab_tavern"
        assert "Testing Tankard" in output

    def test_go_elsewhere_accepts_name(self, node_cli):
        with patch("builtins.input", return_value="old gate"):
            _capture(node_cli.handle_go_elsewhere)
        assert node_cli.game_state.current_node_id == "lab_gate"

    def test_go_elsewhere_blank_cancels(self, node_cli):
        with patch("builtins.input", return_value=""):
            _capture(node_cli.handle_go_elsewhere)
        assert node_cli.game_state.current_node_id == "lab_square"


class TestSkillGatedActions:
    """Examine and depart resolve authored gates; DC forced to pin outcomes."""

    def _gate_node(self, cli):
        cli.game_state.enter_node("lab_gate")
        return cli.game_state.dungeon["nodes"]["lab_gate"]

    def test_examine_success_prose(self, node_cli):
        node = self._gate_node(node_cli)
        node["actions"][0]["gate"]["dc"] = 0
        character = node_cli.game_state.party.characters[0]
        with patch.object(node_cli, "_prompt_character_for_skill_check", return_value=character):
            _capture(node_cli.display_node)
            output = _capture(
                node_cli.process_node_command,
                str(
                    next(
                        i
                        for i, item in enumerate(node_cli._node_menu, 1)
                        if "Examine" in item["label"]
                    )
                ),
            )
        assert "ward against the restless dead" in output

    def test_examine_failure_prose(self, node_cli):
        node = self._gate_node(node_cli)
        node["actions"][0]["gate"]["dc"] = 40
        character = node_cli.game_state.party.characters[0]
        with patch.object(node_cli, "_prompt_character_for_skill_check", return_value=character):
            _capture(node_cli.display_node)
            output = _capture(
                node_cli.process_node_command,
                str(
                    next(
                        i
                        for i, item in enumerate(node_cli._node_menu, 1)
                        if "Examine" in item["label"]
                    )
                ),
            )
        assert "meaning escapes you" in output

    def test_depart_success_crosses_seam(self, node_cli):
        node = self._gate_node(node_cli)
        node["transition"]["gate"]["dc"] = 0
        character = node_cli.game_state.party.characters[0]
        with patch.object(node_cli, "_prompt_character_for_skill_check", return_value=character):
            output = _capture(node_cli.handle_node_depart)
        assert not node_cli.game_state.is_node_surface()
        assert node_cli.game_state.current_room_id == "lab_entry"
        assert "stale air" in output

    def test_depart_failure_stays_on_node(self, node_cli):
        node = self._gate_node(node_cli)
        node["transition"]["gate"]["dc"] = 40
        character = node_cli.game_state.party.characters[0]
        with patch.object(node_cli, "_prompt_character_for_skill_check", return_value=character):
            output = _capture(node_cli.handle_node_depart)
        assert node_cli.game_state.is_node_surface()
        assert node_cli.game_state.current_node_id == "lab_gate"
        assert "will not budge" in output


class TestReverseSeamArrival:
    """A grid exit into a settlement renders the node, not a crash."""

    def test_move_into_settlement_renders_node(self, grid_cli):
        output = _capture(grid_cli.handle_move, "up")
        assert grid_cli.game_state.is_node_surface()
        assert grid_cli.game_state.current_node_id == "lab_gate"
        assert "Old Gate" in output


class TestResetIntoSettlement:
    """Reset lands on the settlement's start node without a false failure."""

    def test_reset_renders_node(self, node_cli):
        node_cli.game_state.enter_node("lab_gate")
        with patch("builtins.input", return_value="y"):
            output = _capture(node_cli.handle_reset, "reset")
        assert "Failed to reset" not in output
        assert "Lab Square" in output


class TestStatusBarOnNodeSurface:
    """The prompt-toolkit toolbar must not raise on a node surface."""

    def test_status_bar_shows_node_identity(self, node_cli):
        status = str(node_cli._get_status_bar())
        assert "Lab Settlement" in status
        assert "Lab Square" in status


class TestTalkOnNodeSurface:
    """Talk keys NPC lookup by node id and degrades kindly when empty."""

    def test_talk_with_no_npcs(self, node_cli):
        class EmptyNPCManager:
            def __init__(self):
                self.queried_with = None

            def get_npcs_in_room(self, location_id):
                self.queried_with = location_id
                return []

        manager = EmptyNPCManager()
        node_cli.game_state.npc_manager = manager
        output = _capture(node_cli.handle_talk, "marta")
        assert "no one" in output.lower()
        assert manager.queried_with == "lab_square"
