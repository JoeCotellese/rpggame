# ABOUTME: Tests for EngineAdapter.load_party_from_vault default behavior and error handling.
# ABOUTME: Verifies the adapter loads vault characters by default and raises PartyLoadError with context.

"""Tests for engine adapter party loading."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    """Point CharacterVaultV2 at an isolated vault under tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    vault_path = home / ".dnd_game" / "character_vault.json"
    return vault_path


def _write_vault(vault_path: Path, characters: dict) -> None:
    """Write a minimal vault file with the given characters dict."""
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    vault_path.write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "created_at": "2026-05-17T00:00:00",
                "characters": characters,
            }
        )
    )


class TestPartyLoadDefaults:
    """When no character_ids passed, load_party_from_vault uses vault contents."""

    def test_loads_all_characters_when_vault_has_few(self, isolated_vault):
        """Default load returns every character in the vault, in insertion order."""
        from client_2d.integration.engine_adapter import EngineAdapter

        ids = [f"{i:08d}-1111-1111-1111-111111111111" for i in range(3)]
        _write_vault(
            isolated_vault,
            characters={
                cid: _minimal_character_record(cid, name=name)
                for cid, name in zip(ids, ["Bob", "Tim", "Wizzy"], strict=True)
            },
        )

        adapter = EngineAdapter()
        loaded = adapter.load_party_from_vault()

        assert [entry["name"] for entry in loaded] == ["Bob", "Tim", "Wizzy"]

    def test_caps_party_at_four_when_vault_has_more(self, isolated_vault):
        """Default load caps at MAX_PARTY_SIZE characters."""
        from client_2d.integration.engine_adapter import (
            MAX_PARTY_SIZE,
            EngineAdapter,
        )

        ids = [f"{i:08d}-2222-2222-2222-222222222222" for i in range(MAX_PARTY_SIZE + 2)]
        _write_vault(
            isolated_vault,
            characters={
                cid: _minimal_character_record(cid, name=f"Char{i}")
                for i, cid in enumerate(ids)
            },
        )

        adapter = EngineAdapter()
        loaded = adapter.load_party_from_vault()

        assert len(loaded) == MAX_PARTY_SIZE


class TestPartyLoadError:
    """PartyLoadError surfaces actionable context instead of bare FileNotFoundError."""

    def test_empty_vault_raises_party_load_error(self, isolated_vault):
        """Empty vault raises PartyLoadError when caller relies on defaults."""
        from client_2d.integration.engine_adapter import (
            EngineAdapter,
            PartyLoadError,
        )

        _write_vault(isolated_vault, characters={})
        adapter = EngineAdapter()

        with pytest.raises(PartyLoadError) as exc_info:
            adapter.load_party_from_vault()

        err = exc_info.value
        assert err.vault_path == isolated_vault
        assert err.vault_character_count == 0
        assert err.available_characters == []

    def test_explicit_missing_ids_are_reported(self, isolated_vault):
        """Caller-supplied IDs that aren't in vault show up in missing_ids."""
        from client_2d.integration.engine_adapter import (
            EngineAdapter,
            PartyLoadError,
        )

        present_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        missing_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        _write_vault(
            isolated_vault,
            characters={
                present_id: _minimal_character_record(present_id, name="Bob"),
            },
        )
        adapter = EngineAdapter()

        with pytest.raises(PartyLoadError) as exc_info:
            adapter.load_party_from_vault(character_ids=[present_id, missing_id])

        err = exc_info.value
        assert err.missing_ids == [missing_id]
        assert err.vault_character_count == 1
        assert (present_id, "Bob") in err.available_characters

    def test_error_message_contains_vault_path_and_available(self, isolated_vault):
        """str(error) mentions vault path and surfaces what's available."""
        from client_2d.integration.engine_adapter import (
            EngineAdapter,
            PartyLoadError,
        )

        other_id = "11111111-1111-1111-1111-111111111111"
        missing_id = "99999999-9999-9999-9999-999999999999"
        _write_vault(
            isolated_vault,
            characters={
                other_id: _minimal_character_record(other_id, name="Wanda"),
            },
        )
        adapter = EngineAdapter()

        with pytest.raises(PartyLoadError) as exc_info:
            adapter.load_party_from_vault(character_ids=[missing_id])

        message = str(exc_info.value)
        assert str(isolated_vault) in message
        assert "Wanda" in message
        assert missing_id in message


def _minimal_character_record(char_id: str, *, name: str) -> dict:
    """Build a vault record with the minimum fields CharacterVaultV2 needs to load."""
    return {
        "id": char_id,
        "created_at": "2026-05-17T00:00:00",
        "last_modified": "2026-05-17T00:00:00",
        "last_used": None,
        "times_used": 0,
        "save_slots_used": [],
        "character": {
            "name": name,
            "character_class": "fighter",
            "level": 1,
            "race": "human",
            "subclass": None,
            "xp": 0,
            "max_hp": 12,
            "current_hp": 12,
            "ac": 16,
            "abilities": {
                "strength": 16,
                "dexterity": 13,
                "constitution": 15,
                "intelligence": 9,
                "wisdom": 14,
                "charisma": 11,
            },
            "inventory": {
                "items": [],
                "equipped": {},
                "currency": {
                    "copper": 0,
                    "silver": 0,
                    "electrum": 0,
                    "gold": 0,
                    "platinum": 0,
                },
            },
            "conditions": [],
            "resource_pools": [],
            "saving_throw_proficiencies": ["str", "con"],
            "skill_proficiencies": [],
            "expertise_skills": [],
            "weapon_proficiencies": ["simple", "martial"],
            "armor_proficiencies": ["light", "medium", "heavy", "shields"],
            "tool_proficiencies": [],
            "spellcasting_ability": None,
            "known_spells": [],
            "prepared_spells": [],
            "speed": 30,
        },
    }
