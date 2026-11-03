"""Versioned source model. Pure data logic, independent of HA or frontend."""

from dataclasses import asdict, dataclass
import re
from uuid import uuid4

from .const import ALARM_TYPES, INPUT_CONFIG_KEY, INPUT_CONFIG_VERSION, MAX_INPUTS


class InputValidationError(ValueError):
    def __init__(self, field: str, key: str) -> None:
        super().__init__(f"{field}: {key}")
        self.field = field
        self.key = key


@dataclass(frozen=True)
class InputSource:
    id: str
    name: str
    entity_id: str
    entity_registry_id: str | None
    trigger_state: str
    alarm_type: str
    enabled: bool

    def to_dict(self) -> dict:
        return asdict(self)


def build_source(data: dict, *, source_id: str | None = None,
                 registry_id: str | None = None) -> InputSource:
    """Create/update one source while preserving its ID when editing."""
    if not isinstance(data, dict):
        raise InputValidationError("base", "invalid_input")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise InputValidationError("name", "invalid_name")
    entity_id = data.get("entity_id")
    if not isinstance(entity_id, str) or not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
        raise InputValidationError("entity_id", "invalid_entity")
    value = data.get("trigger_state")
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 255:
        raise InputValidationError("trigger_state", "invalid_state")
    value = value.strip()
    if value in ("unknown", "unavailable"):
        raise InputValidationError("trigger_state", "invalid_state")
    if data.get("alarm_type") not in ALARM_TYPES:
        raise InputValidationError("alarm_type", "invalid_alarm_type")
    if type(data.get("enabled")) is not bool:
        raise InputValidationError("enabled", "invalid_input")
    source_id = source_id if source_id is not None else uuid4().hex
    if not isinstance(source_id, str) or not re.fullmatch(r"[0-9a-f]{32}", source_id):
        raise InputValidationError("base", "invalid_input")
    if registry_id is not None and (not isinstance(registry_id, str) or not registry_id):
        raise InputValidationError("base", "invalid_input")
    return InputSource(source_id, name.strip(), entity_id, registry_id,
                       value, data["alarm_type"], data["enabled"])


def load_sources(options: dict) -> tuple[InputSource, ...]:
    """An absent namespace is the backwards-compatible v0.1 default."""
    config = options.get(INPUT_CONFIG_KEY)
    if config is None and INPUT_CONFIG_KEY not in options:
        return ()
    if (not isinstance(config, dict) or set(config) != {"version", "inputs"}
            or type(config["version"]) is not int or config["version"] != INPUT_CONFIG_VERSION
            or not isinstance(config["inputs"], list) or len(config["inputs"]) > MAX_INPUTS):
        raise ValueError("Invalid or unsupported input configuration")
    result = []
    for raw in config["inputs"]:
        if not isinstance(raw, dict) or set(raw) != set(InputSource.__dataclass_fields__):
            raise ValueError("Invalid input fields")
        result.append(build_source(raw, source_id=raw["id"], registry_id=raw["entity_registry_id"]))
    if len({source.id for source in result}) != len(result):
        raise ValueError("Duplicate input IDs")
    return tuple(result)


def serialize_sources(sources) -> dict:
    config = {"version": INPUT_CONFIG_VERSION, "inputs": [source.to_dict() for source in sources]}
    load_sources({INPUT_CONFIG_KEY: config})
    return config


def evaluate_source(source: InputSource, state: str | None) -> str:
    """A current-state comparison, not a latching alarm or rule engine."""
    if not source.enabled:
        return "disabled"
    if state is None:
        return "missing"
    if state in ("unknown", "unavailable"):
        return state
    return "matching" if state == source.trigger_state else "not_matching"
