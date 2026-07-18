# ABOUTME: Schema validation for node-surface locations (settlements presented as theater-of-the-mind nodes).
# ABOUTME: Enforces the fixed action vocabulary and the gated-action prose rules from issue #684.

from typing import Any

# Simple actions the engine dispatches without extra authoring. examine_* is
# deliberately absent: it is skill-gated by definition, so it must be authored
# in object form where the gate and both prose branches live.
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

VALID_SURFACES = frozenset({"grid", "node"})


class NodeSchemaError(Exception):
    """Raised when a node-surface location file violates the schema.

    The message always includes the offending key path so an author can fix
    the JSON without spelunking through tracebacks.
    """


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

    surface = data.get("surface")
    if surface not in VALID_SURFACES:
        raise NodeSchemaError(
            f"Unknown surface {surface!r}{where}; expected one of {sorted(VALID_SURFACES)}"
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

    for prose_field in ("name", "blurb", "description"):
        value = node.get(prose_field)
        if not isinstance(value, str) or not value.strip():
            raise NodeSchemaError(f"{path} requires non-empty '{prose_field}'{where}")

    npcs = node.get("npcs", [])
    if not isinstance(npcs, list) or any(not isinstance(n, str) for n in npcs):
        raise NodeSchemaError(f"{path}.npcs must be a list of NPC ids{where}")

    for index, action in enumerate(node.get("actions", [])):
        _validate_action(f"{path}.actions[{index}]", action, where)

    if "transition" in node:
        _validate_transition(f"{path}.transition", node["transition"], where)


def _validate_action(path: str, action: Any, where: str) -> None:
    if isinstance(action, str):
        if action.startswith(EXAMINE_PREFIX):
            raise NodeSchemaError(
                f"{path}: {action!r} is skill-gated and must be authored in object "
                f"form with 'gate', 'on_success', and 'on_failure'{where}"
            )
        if action not in NODE_ACTION_VOCABULARY:
            raise NodeSchemaError(
                f"{path}: unknown action {action!r}{where}; "
                f"expected one of {sorted(NODE_ACTION_VOCABULARY)} or an object form"
            )
        return

    if not isinstance(action, dict):
        raise NodeSchemaError(f"{path} must be a string or object{where}")

    action_id = action.get("id")
    if not isinstance(action_id, str) or not (
        action_id in NODE_ACTION_VOCABULARY or action_id.startswith(EXAMINE_PREFIX)
    ):
        raise NodeSchemaError(
            f"{path}: unknown action id {action_id!r}{where}; "
            f"expected one of {sorted(NODE_ACTION_VOCABULARY)} or '{EXAMINE_PREFIX}*'"
        )

    _validate_gate_and_prose(path, action, where)


def _validate_transition(path: str, transition: Any, where: str) -> None:
    if not isinstance(transition, dict):
        raise NodeSchemaError(f"{path} must be an object{where}")

    destination = transition.get("to")
    if not isinstance(destination, str) or not destination.strip():
        raise NodeSchemaError(f"{path} requires a non-empty 'to' destination{where}")

    _validate_gate_and_prose(path, transition, where)


def _validate_gate_and_prose(path: str, entry: dict[str, Any], where: str) -> None:
    """A gate makes an entry a skill check; every check authors both outcomes."""
    gate = entry.get("gate")
    if gate is None:
        return

    if not isinstance(gate, dict):
        raise NodeSchemaError(f"{path}.gate must be an object{where}")
    if not isinstance(gate.get("skill"), str) or not gate.get("skill"):
        raise NodeSchemaError(f"{path}.gate requires 'skill'{where}")
    if not isinstance(gate.get("dc"), int):
        raise NodeSchemaError(f"{path}.gate requires an integer 'dc'{where}")

    for branch in ("on_success", "on_failure"):
        value = entry.get(branch)
        if not isinstance(value, str) or not value.strip():
            raise NodeSchemaError(
                f"{path}: gated entries require non-empty '{branch}' prose{where}"
            )
