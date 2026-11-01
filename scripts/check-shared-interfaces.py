#!/usr/bin/env python3
"""Check captured @main caller inputs against shared component interfaces."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "tests" / "caller-contracts.json"


def load_yaml(path: Path) -> dict[str, Any]:
    # BaseLoader keeps GitHub's `on` key a string instead of YAML 1.1 boolean.
    loaded = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return loaded


def interface_for(kind: str, component: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if kind == "workflow":
        path = ROOT / ".github" / "workflows" / component
        definition = load_yaml(path)
        call = definition.get("on", {}).get("workflow_call")
        if call in (None, ""):
            return {}, {}
        if not isinstance(call, dict):
            raise ValueError(f"{path.relative_to(ROOT)} has no on.workflow_call interface")
        return call.get("inputs") or {}, call.get("secrets") or {}

    if kind == "action":
        path = ROOT / ".github" / "actions" / component / "action.yaml"
        definition = load_yaml(path)
        return definition.get("inputs") or {}, {}

    raise ValueError(f"unknown component kind {kind!r}")


def required_names(definitions: dict[str, Any]) -> set[str]:
    return {
        name
        for name, details in definitions.items()
        if isinstance(details, dict) and details.get("required", "false").lower() == "true"
    }


def check_call(call: dict[str, Any]) -> list[str]:
    label = f"{call['caller']} ({call['context']})"
    try:
        inputs, secrets = interface_for(call["kind"], call["component"])
    except (OSError, ValueError, yaml.YAMLError) as error:
        return [f"{label}: {error}"]

    errors = []
    captured_inputs = call.get("with", {})
    provided_inputs = set(captured_inputs)
    unknown_inputs = provided_inputs - inputs.keys()
    if unknown_inputs:
        errors.append(f"{label}: removed or unknown inputs: {', '.join(sorted(unknown_inputs))}")

    missing_inputs = required_names(inputs) - provided_inputs
    if missing_inputs:
        errors.append(f"{label}: new required inputs: {', '.join(sorted(missing_inputs))}")

    if call["kind"] == "workflow":
        for name, value_kind in captured_inputs.items():
            if value_kind not in {"string", "boolean", "number"} or name not in inputs:
                continue
            declared_type = inputs[name].get("type", "string")
            if declared_type != value_kind:
                errors.append(
                    f"{label}: input {name!r} receives {value_kind} values, but is now {declared_type}"
                )

    provided_secrets = call.get("secrets", [])
    inherited = provided_secrets == "inherit"
    if inherited:
        provided_secret_names = set()
    elif isinstance(provided_secrets, list):
        provided_secret_names = set(provided_secrets)
        unknown_secrets = provided_secret_names - secrets.keys()
        if unknown_secrets:
            errors.append(f"{label}: removed or unknown secrets: {', '.join(sorted(unknown_secrets))}")
    else:
        errors.append(f"{label}: malformed captured secrets contract")
        provided_secret_names = set()

    missing_secrets = required_names(secrets) - provided_secret_names
    if missing_secrets:
        qualifier = "required secrets cannot be verified for inherited secrets" if inherited else "new required secrets"
        errors.append(f"{label}: {qualifier}: {', '.join(sorted(missing_secrets))}")

    return errors


def main() -> int:
    calls = json.loads(CONTRACTS.read_text())
    errors = [error for call in calls for error in check_call(call)]
    if errors:
        print("Shared interface compatibility failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(calls)} captured @main caller contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
