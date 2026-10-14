"""shared/schemas/*.json is the source of truth; the pydantic models must match it.

Both sides are reduced to a structural signature (property names, required
fields, types, enums, consts, numeric bounds) that ignores cosmetic keys such
as titles, descriptions and defaults.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from agents.models import DeploymentState
from events import EventAdapter

SCHEMAS = Path(__file__).resolve().parents[2] / "shared" / "schemas"


def load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text())


def sig(node: dict[str, Any]) -> str:
    if "$ref" in node:
        return "ref:" + node["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in node:
        return "|".join(sorted(sig(option) for option in node["anyOf"]))
    if "const" in node:
        return f"const:{node['const']}"
    if "enum" in node:
        return "enum:" + ",".join(sorted(node["enum"]))
    kind = node.get("type")
    if kind == "array":
        return f"array<{sig(node['items'])}>"
    if kind == "object" and isinstance(node.get("additionalProperties"), dict):
        keys = sig(node["propertyNames"]) if "propertyNames" in node else "string"
        return f"map<{keys},{sig(node['additionalProperties'])}>"
    bounds = "".join(f"[{k}={node[k]}]" for k in ("minimum", "maximum") if k in node)
    fmt = f":{node['format']}" if "format" in node else ""
    return f"{kind}{fmt}{bounds}"


def shape(definition: dict[str, Any]) -> Any:
    if "enum" in definition:
        return ("enum", sorted(definition["enum"]))
    return (
        "object",
        {name: sig(prop) for name, prop in definition["properties"].items()},
        sorted(definition.get("required", [])),
        definition.get("additionalProperties", True),
    )


def shapes(schema: dict[str, Any], root_name: str | None = None) -> dict[str, Any]:
    defs = {
        name: shape(d)
        for name, d in schema.get("$defs", {}).items()
        if "$ref" not in d  # cross-file aliases are checked via the referenced file
    }
    if root_name:
        defs[root_name] = shape(schema)
    return defs


def state_shapes_from_shared() -> dict[str, Any]:
    return shapes(load("state.schema.json"), root_name="DeploymentState")


def test_state_schema_matches_pydantic() -> None:
    generated = shapes(
        DeploymentState.model_json_schema(mode="serialization"), root_name="DeploymentState"
    )
    assert state_shapes_from_shared() == generated


def test_event_schema_matches_pydantic() -> None:
    shared = load("event.schema.json")
    generated = EventAdapter.json_schema(mode="serialization")

    expected = {**state_shapes_from_shared(), **shapes(shared)}
    assert expected == shapes(generated)
    assert sorted(sig(v) for v in shared["oneOf"]) == sorted(sig(v) for v in generated["oneOf"])
    assert shared["discriminator"]["propertyName"] == generated["discriminator"]["propertyName"]


@pytest.mark.parametrize("alias", ["AgentName", "AgentStatus", "DeploymentState"])
def test_event_schema_aliases_resolve(alias: str) -> None:
    ref = load("event.schema.json")["$defs"][alias]["$ref"]
    file, _, pointer = ref.partition("#")
    target = load(file)
    for part in filter(None, pointer.split("/")):
        target = target[part]
    assert target
