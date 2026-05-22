# ABOUTME: End-to-end tests for the character creation wizard, driving run()
# ABOUTME: through real data with only the questionary input layer mocked.

from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from terminal_client.ui.character_wizard import CharacterCreationWizard, CreationPath


class _QuestionaryDriver:
    """Helper that hands back queued answers to each questionary.* call.

    Each entry in ``answers`` is the next value any ``.ask()`` will return,
    regardless of which questionary helper raised it. This mirrors the
    deterministic order of prompts the wizard issues, so the test reads as
    a script of user keystrokes.
    """

    def __init__(self, answers):
        self._queue: deque = deque(answers)

    def __call__(self, *args, **kwargs):
        mock = MagicMock()
        if not self._queue:
            raise AssertionError("Ran out of queued questionary answers")
        mock.ask.return_value = self._queue.popleft()
        return mock

    @property
    def remaining(self):
        return list(self._queue)


@pytest.fixture
def wizard():
    dice_roller = DiceRoller(seed=42)
    return CharacterCreationWizard(
        character_factory=CharacterFactory(dice_roller=dice_roller),
        data_loader=DataLoader(),
        dice_roller=dice_roller,
    )


def _run_wizard_with_inputs(
    wizard, select_answers, text_answers, confirm_answers, checkbox_answers
):
    """Drive ``wizard.run()`` with queued answers per questionary helper.

    Returns the resulting Character (or None).
    """
    select_driver = _QuestionaryDriver(select_answers)
    text_driver = _QuestionaryDriver(text_answers)
    confirm_driver = _QuestionaryDriver(confirm_answers)
    checkbox_driver = _QuestionaryDriver(checkbox_answers)

    with patch("terminal_client.ui.character_wizard.questionary.select", side_effect=select_driver):
        with patch("terminal_client.ui.character_wizard.questionary.text", side_effect=text_driver):
            with patch(
                "terminal_client.ui.character_wizard.questionary.confirm",
                side_effect=confirm_driver,
            ):
                with patch(
                    "terminal_client.ui.character_wizard.questionary.checkbox",
                    side_effect=checkbox_driver,
                ):
                    return wizard.run()


def test_full_custom_path_with_equipment_choice(wizard):
    """End-to-end: a player walks through the entire custom wizard and
    chooses the Skirmisher (option 1) fighter loadout.

    Verifies acceptance criterion #6 from issue #382 — the equipment
    choice survives every wizard step and ends up in the final Character.
    """
    # questionary.select sequence — in the exact order the wizard issues them:
    select_answers = [
        CreationPath.CUSTOM,  # _step_choose_path
        "human",  # _custom_step_race: race select
        "next",  # nav after race
        "fighter",  # _custom_step_class: class select
        "next",  # nav after class
        # _custom_step_abilities: no swap, so confirm() returns False; just one nav select
        "next",  # nav after abilities
        "next",  # nav after skills
        1,  # _custom_step_equipment: pick Skirmisher (index 1)
        "next",  # nav after equipment
        "next",  # nav after name
        "confirm",  # _finalize_character
    ]
    text_answers = ["TestHero"]  # _custom_step_name
    confirm_answers = [False]  # "Would you like to swap any abilities?" -> No
    checkbox_answers = [["athletics", "intimidation"]]  # _custom_step_skills

    character = _run_wizard_with_inputs(
        wizard,
        select_answers=select_answers,
        text_answers=text_answers,
        confirm_answers=confirm_answers,
        checkbox_answers=checkbox_answers,
    )

    assert character is not None
    assert character.name == "TestHero"
    assert character.race == "human"
    # Skirmisher (option 1) loadout for fighter:
    assert character.inventory.has_item("longbow")
    assert character.inventory.has_item("studded_leather")
    assert character.inventory.has_item("arrows")
    assert character.inventory.has_item("quiver")
    # And NOT the standard loadout's chain mail / longsword
    assert not character.inventory.has_item("chain_mail")
    assert not character.inventory.has_item("longsword")
    # Skirmisher gold
    assert character.inventory.gold == 11
