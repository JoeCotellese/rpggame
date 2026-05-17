# ABOUTME: YAML scenario loader — builds a deterministic GameState from a fixture file.
# ABOUTME: Pure-engine; client-2d wraps this in EngineAdapter for visual placement.

"""ScenarioLoader for reproducible playtests (issue #361).

A scenario file captures a map + party + enemies + seed so that a known
game state is one ``load(path)`` call away. The loader is engine-only:
positions are returned as data on :class:`LoadedScenario` and applied to
the visual entity layer by the client adapter.

YAML schema (v1) is documented at
``dnd-engine/tests/scenarios/yaml/_schema.md``. The validator surfaces
:class:`ScenarioValidationError` with the offending key/path on every
failure so a human can fix the file without spelunking through tracebacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "name",
    "seed",
    "map",
    "party",
    "enemies",
)

REQUIRED_MAP_KEYS: tuple[str, ...] = ("dungeon", "campaign")

REQUIRED_PARTY_MEMBER_KEYS: tuple[str, ...] = (
    "class",
    "race",
    "weapons",
    "position",
)

REQUIRED_ENEMY_KEYS: tuple[str, ...] = ("monster_id", "position")


class ScenarioValidationError(Exception):
    """Raised when a scenario YAML is missing keys, has wrong types, or
    references an unknown class/race/monster.

    The message always includes enough context (key path, offending value,
    file path when relevant) for the human to fix the YAML without
    additional debugging.
    """


@dataclass
class LoadedScenario:
    """Result of loading a scenario YAML.

    ``game_state`` is ready to play. Positions are returned alongside so
    the client (or test harness) can wire the visual layer; the pure
    engine has no creature coordinates of its own.
    """

    name: str
    seed: int
    game_state: Any  # forward-typed to avoid importing GameState at module load
    party_positions: dict[str, tuple[int, int]] = field(default_factory=dict)
    enemy_positions: dict[str, tuple[int, int]] = field(default_factory=dict)
    script: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    map_config: dict[str, Any] = field(default_factory=dict)


class ScenarioLoader:
    """Loads a YAML scenario file and constructs a fully wired ``GameState``.

    Construction defers all engine imports so importing the loader module
    doesn't drag in the whole engine when a caller only needs to validate
    schemas.
    """

    def load(self, path: str | Path) -> LoadedScenario:
        """Parse ``path``, validate it, and build the resulting state.

        Args:
            path: Path to a YAML scenario file.

        Returns:
            :class:`LoadedScenario` carrying the engine state and the
            positions to apply on the visual layer.

        Raises:
            ScenarioValidationError: For any schema, parse, or content
                error. The message identifies the offending key, value,
                and (when relevant) the file path.
        """
        scenario_path = Path(path)
        data = self._parse_yaml(scenario_path)
        self._validate(data)

        from dnd_engine.core.character_factory import CharacterFactory
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.core.game_state import GameState
        from dnd_engine.core.party import Party
        from dnd_engine.rules.loader import DataLoader
        from dnd_engine.systems.inventory import EquipmentSlot
        from dnd_engine.utils.events import EventBus

        seed = int(data["seed"])
        map_cfg = data["map"]
        dungeon = str(map_cfg["dungeon"])
        campaign = str(map_cfg["campaign"])
        start_room = map_cfg.get("start_room")

        data_loader = DataLoader()
        dice_roller = DiceRoller(seed=seed)

        # Build party first — GameState requires it at construction.
        factory = CharacterFactory()
        characters: list[Any] = []
        party_positions: dict[str, tuple[int, int]] = {}
        for i, member in enumerate(data["party"]):
            try:
                character = factory.create_character(
                    class_name=str(member["class"]),
                    race_name=str(member["race"]),
                    data_loader=data_loader,
                    level=int(member.get("level", 1)),
                    name=member.get("name"),
                )
            except ValueError as exc:
                # CharacterFactory raises ValueError for unknown class/race;
                # surface as ScenarioValidationError so callers don't have
                # to special-case engine exception types.
                raise ScenarioValidationError(
                    f"party[{i}]: {exc}"
                ) from exc

            for j, weapon_id in enumerate(member["weapons"]):
                character.inventory.add_item(weapon_id, category="weapons")
                if j == 0:
                    character.inventory.equip_item(weapon_id, EquipmentSlot.WEAPON)

            characters.append(character)
            entity_id = f"pc_{character.name.lower().replace(' ', '_')}"
            x, y = member["position"]
            party_positions[entity_id] = (int(x), int(y))

        party = Party(characters)

        event_bus = EventBus()
        game_state = GameState(
            party=party,
            dungeon_name=dungeon,
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
            campaign_id=campaign,
        )
        if start_room:
            game_state.current_room_id = str(start_room)

        # Push scenario enemies. Mirrors the path used by
        # EngineAdapter.spawn_monster so behaviour stays consistent
        # whether enemies arrive via spawn tool or via scenario load.
        enemy_positions: dict[str, tuple[int, int]] = {}
        for i, enemy in enumerate(data["enemies"]):
            monster_id = str(enemy["monster_id"])
            try:
                creature = data_loader.create_monster(monster_id)
            except KeyError as exc:
                raise ScenarioValidationError(
                    f"enemies[{i}]: unknown monster_id '{monster_id}'"
                ) from exc
            game_state.active_enemies.append(creature)
            entity_id = f"{monster_id}_{i}"
            x, y = enemy["position"]
            enemy_positions[entity_id] = (int(x), int(y))

        if game_state.active_enemies:
            game_state._start_combat()

        return LoadedScenario(
            name=str(data["name"]),
            seed=seed,
            game_state=game_state,
            party_positions=party_positions,
            enemy_positions=enemy_positions,
            script=list(data.get("script") or []),
            assertions=list(data.get("assertions") or []),
            map_config=dict(map_cfg),
        )

    @staticmethod
    def _parse_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ScenarioValidationError(
                f"Scenario file not found: {path}"
            )
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ScenarioValidationError(
                f"Malformed YAML in {path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise ScenarioValidationError(
                f"Scenario root in {path} must be a mapping, got "
                f"{type(data).__name__}"
            )
        return data

    @classmethod
    def _validate(cls, data: dict[str, Any]) -> None:
        missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in data]
        if missing:
            raise ScenarioValidationError(
                f"Scenario missing required key(s): {', '.join(missing)}"
            )

        if not isinstance(data["seed"], int) or isinstance(data["seed"], bool):
            raise ScenarioValidationError(
                f"`seed` must be an int, got {type(data['seed']).__name__}"
            )

        cls._validate_map(data["map"])
        cls._validate_party(data["party"])
        cls._validate_enemies(data["enemies"])

    @staticmethod
    def _validate_map(map_block: Any) -> None:
        if not isinstance(map_block, dict):
            raise ScenarioValidationError(
                f"`map` must be a mapping, got {type(map_block).__name__}"
            )
        missing = [k for k in REQUIRED_MAP_KEYS if k not in map_block]
        if missing:
            raise ScenarioValidationError(
                f"`map` missing required key(s): {', '.join(missing)}"
            )
        if "tiles" in map_block:
            raise ScenarioValidationError(
                "Inline `map.tiles` is not yet implemented; use "
                "`map.dungeon` + `map.campaign` to reference an existing "
                "dungeon."
            )

    @classmethod
    def _validate_party(cls, party: Any) -> None:
        if not isinstance(party, list):
            raise ScenarioValidationError(
                f"`party` must be a list, got {type(party).__name__}"
            )
        for i, member in enumerate(party):
            if not isinstance(member, dict):
                raise ScenarioValidationError(
                    f"party[{i}] must be a mapping, got "
                    f"{type(member).__name__}"
                )
            missing = [k for k in REQUIRED_PARTY_MEMBER_KEYS if k not in member]
            if missing:
                raise ScenarioValidationError(
                    f"party[{i}] missing required key(s): {', '.join(missing)}"
                )
            if not isinstance(member["weapons"], list) or not member["weapons"]:
                raise ScenarioValidationError(
                    f"party[{i}].weapons must be a non-empty list of "
                    f"weapon IDs"
                )
            cls._validate_position(member["position"], f"party[{i}].position")

    @classmethod
    def _validate_enemies(cls, enemies: Any) -> None:
        if not isinstance(enemies, list):
            raise ScenarioValidationError(
                f"`enemies` must be a list, got {type(enemies).__name__}"
            )
        for i, enemy in enumerate(enemies):
            if not isinstance(enemy, dict):
                raise ScenarioValidationError(
                    f"enemies[{i}] must be a mapping, got "
                    f"{type(enemy).__name__}"
                )
            missing = [k for k in REQUIRED_ENEMY_KEYS if k not in enemy]
            if missing:
                raise ScenarioValidationError(
                    f"enemies[{i}] missing required key(s): "
                    f"{', '.join(missing)}"
                )
            cls._validate_position(enemy["position"], f"enemies[{i}].position")

    @staticmethod
    def _validate_position(value: Any, label: str) -> None:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(c, int) and not isinstance(c, bool) for c in value)
        ):
            raise ScenarioValidationError(
                f"{label} must be a list of two ints [x, y]; got {value!r}"
            )
