# ABOUTME: Schema validation for node-surface locations (settlements presented as theater-of-the-mind nodes).
# ABOUTME: Enforces the fixed action vocabulary and the gated-action prose rules from issue #684.

from typing import Any

# Simple actions the engine dispatches without extra authoring. examine_* is
# deliberately absent: it is a skill check, so it must be authored in object
# form where the gate and both prose branches live.
NODE_ACTION_VOCABULARY = frozenset(
    {
        "talk",
        "shop",
        "rest",
        "gather_rumors",
        "read_job_board",
    }
)

EXAMINE_PREFIX = "examine_"

# Every key a node may carry. Unknown keys fail at load so a typo like
# "transtion" can't silently drop content.
NODE_KEYS = frozenset(
    {
        "name",
        "blurb",
        "description",
        "npcs",
        "actions",
        "transition",
        "quest_hook",
    }
)


class NodeSchemaError(Exception):
    """Raised when a node-surface location file violates the schema.

    The message always includes the offending key path so an author can fix
    the JSON without spelunking through tracebacks.
    """


def validate_location_surface(data: Any, source: str = "") -> None:
    """
    Validate any parsed location JSON according to its declared surface.

    The single entry point for every load path (DataLoader, RoomRegistry).
    Locations without a ``surface`` key are legacy grid dungeons and pass
    through untouched, as do non-dict payloads.

    Args:
        data: Parsed location JSON.
        source: Optional file path for error messages.

    Raises:
        NodeSchemaError: On an unknown surface value or any node-schema
            violation.
    """
    if not isinstance(data, dict):
        return

    surface = data.get("surface")
    if surface is None or surface == "grid":
        return
    if surface == "node":
        validate_node_location(data, source=source)
        return

    where = f" in {source}" if source else ""
    raise NodeSchemaError(f"Unknown surface {surface!r}{where}; expected 'grid' or 'node'")


def validate_node_location(data: dict[str, Any], source: str = "") -> None:
    """
    Validate a location dict that declares ``surface: "node"``.

    Args:
        data: Parsed location JSON.
        source: Optional file path for error messages.

    Raises:
        NodeSchemaError: On any schema violation.
    """
    where = f" in {source}" if source else ""

    if data.get("surface") != "node":
        raise NodeSchemaError(
            f"validate_node_location called for surface {data.get('surface')!r}{where}; "
            "expected 'node'"
        )

    if "rooms" in data:
        raise NodeSchemaError(
            f"Node-surface location declares 'rooms'{where}; "
            "'rooms' and 'nodes' are mutually exclusive"
        )

    nodes = data.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise NodeSchemaError(f"Node-surface location requires a non-empty 'nodes' mapping{where}")

    start_node = data.get("start_node")
    if not start_node:
        raise NodeSchemaError(f"Node-surface location requires 'start_node'{where}")
    if start_node not in nodes:
        raise NodeSchemaError(f"start_node {start_node!r} is not a key in 'nodes'{where}")

    for node_id, node in nodes.items():
        _validate_node(node_id, node, where)


def _validate_node(node_id: str, node: Any, where: str) -> None:
    path = f"nodes.{node_id}"
    if not isinstance(node, dict):
        raise NodeSchemaError(f"{path} must be an object{where}")

    unknown_keys = set(node) - NODE_KEYS
    if unknown_keys:
        raise NodeSchemaError(
            f"{path} has unknown key(s) {sorted(unknown_keys)}{where}; "
            f"expected only {sorted(NODE_KEYS)}"
        )

    for prose_field in ("name", "blurb", "description"):
        _require_nonempty_str(node, prose_field, path, where)

    npcs = node.get("npcs", [])
    if not isinstance(npcs, list) or any(not isinstance(n, str) for n in npcs):
        raise NodeSchemaError(f"{path}.npcs must be a list of NPC ids{where}")

    actions = node.get("actions", [])
    if not isinstance(actions, list):
        raise NodeSchemaError(f"{path}.actions must be a list{where}")
    for index, action in enumerate(actions):
        _validate_action(f"{path}.actions[{index}]", action, where)

    if "transition" in node:
        _validate_transition(f"{path}.transition", node["transition"], where)


def _validate_action(path: str, action: Any, where: str) -> None:
    # String actions are shorthand for {"id": <string>}; one branch validates both.
    if isinstance(action, str):
        action = {"id": action}
    elif not isinstance(action, dict):
        raise NodeSchemaError(f"{path} must be a string or object{where}")

    action_id = action.get("id")
    if not isinstance(action_id, str) or not (
        action_id in NODE_ACTION_VOCABULARY or action_id.startswith(EXAMINE_PREFIX)
    ):
        raise NodeSchemaError(
            f"{path}: unknown action {action_id!r}{where}; "
            f"expected one of {sorted(NODE_ACTION_VOCABULARY)} or '{EXAMINE_PREFIX}*'"
        )

    if action_id.startswith(EXAMINE_PREFIX) and "gate" not in action:
        raise NodeSchemaError(
            f"{path}: {action_id!r} is a skill check and must be authored in object "
            f"form with 'gate', 'on_success', and 'on_failure'{where}"
        )

    _validate_gate_and_prose(path, action, where)


def _validate_transition(path: str, transition: Any, where: str) -> None:
    if not isinstance(transition, dict):
        raise NodeSchemaError(f"{path} must be an object{where}")

    _require_nonempty_str(transition, "to", path, where)
    _validate_gate_and_prose(path, transition, where)


def _validate_gate_and_prose(path: str, entry: dict[str, Any], where: str) -> None:
    """A gate makes an entry a skill check; every check authors both outcomes."""
    gate = entry.get("gate")
    if gate is None:
        return

    if not isinstance(gate, dict):
        raise NodeSchemaError(f"{path}.gate must be an object{where}")
    _require_nonempty_str(gate, "skill", f"{path}.gate", where)
    dc = gate.get("dc")
    if not isinstance(dc, int) or isinstance(dc, bool):
        raise NodeSchemaError(f"{path}.gate requires an integer 'dc'{where}")

    for branch in ("on_success", "on_failure"):
        _require_nonempty_str(entry, branch, path, where)


def _require_nonempty_str(container: dict[str, Any], field: str, path: str, where: str) -> None:
    value = container.get(field)
    if not isinstance(value, str) or not value.strip():
        raise NodeSchemaError(f"{path} requires non-empty '{field}'{where}")
