"""Versioned output definitions, safe text placeholders and rule assignments."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import re
from string import Formatter
from uuid import uuid4

from .const import MAX_LONG_TEXT, MAX_OUTPUTS, OUTPUT_CONFIG_KEY, OUTPUT_CONFIG_VERSION
from .input_config import InputValidationError

KINDS = ("switch", "short_text", "long_text", "notification", "overlay")
PHASES = ("alarm", "acknowledged", "idle")
PLACEHOLDERS = {"regel", "quelle", "bereich", "alarmtyp", "status"}
DOMAINS = {"switch": ("switch", "light", "siren", "input_boolean"),
           "short_text": ("text", "input_text"), "long_text": ("text", "input_text"), "notification": (), "overlay": ()}


@dataclass(frozen=True)
class OutputDefinition:
    id: str
    name: str
    kind: str
    entity_id: str | None
    entity_registry_id: str | None
    enabled: bool
    encoding: str
    alarm_value: str
    acknowledged_value: str
    idle_value: str
    notification: dict | None = None

    def to_dict(self):
        return asdict(self)


def validate_notification(data, kind):
    if not isinstance(data, dict) or set(data) != {"routes", "title", "devices", "priority"}:
        raise InputValidationError("base", "invalid_notification")
    routes = data['routes']
    if (not isinstance(routes, list) or not 1 <= len(routes) <= 20 or
            not all(isinstance(route,str) for route in routes) or len(set(routes)) != len(routes)):
        raise InputValidationError("routes", "invalid_notification")
    for route in routes:
        if not re.fullmatch(r"(entity:notify\.[a-z0-9_]+|mobile_app:notify\.mobile_app_[a-z0-9_]+|pushover:notify\.[a-z0-9_]+|browser:[0-9a-f]{32})", route):
            raise InputValidationError("routes", "invalid_notification")
        if route.startswith('browser:') != (kind == 'overlay'):
            raise InputValidationError('routes', 'invalid_notification')
        if route.split(".")[-1] in ("notify", "send_message", "reload", "send"):
            raise InputValidationError("routes", "invalid_notification")
    if not isinstance(data["title"], str) or len(data["title"]) > 80:
        raise InputValidationError("title", "invalid_notification")
    try:
        validate_text(data["title"], "long_text", "latin-1")
    except ValueError as err:
        raise InputValidationError("title", str(err)) from err
    if (not isinstance(data["devices"], str) or len(data["devices"]) > 200 or
            (data["devices"] and not re.fullmatch(r"[a-zA-Z0-9_-]+(?:,[a-zA-Z0-9_-]+)*", data["devices"]))):
        raise InputValidationError("devices", "invalid_notification")
    if type(data["priority"]) is not int or data["priority"] not in (-2, -1, 0, 1):
        raise InputValidationError("priority", "invalid_notification")
    if not any(route.startswith("pushover:") for route in routes) and (data["devices"] or data["priority"]):
        raise InputValidationError("base", "invalid_notification")
    return deepcopy(data)


def template_fields(value):
    try:
        parts = list(Formatter().parse(value))
    except ValueError as err:
        raise ValueError("invalid_template") from err
    if any(field is not None and (field not in PLACEHOLDERS or spec or conversion)
           for _, field, spec, conversion in parts):
        raise ValueError("invalid_template")
    return parts


def validate_text(value, kind, encoding):
    if not isinstance(value, str) or len(value) > MAX_LONG_TEXT or "\x00" in value:
        raise ValueError("text_too_long")
    parts = template_fields(value)
    if kind == "short_text":
        if "\n" in value or "\r" in value:
            raise ValueError("short_text_invalid")
        literal = "".join(part[0] for part in parts)
        try:
            encoded = literal.encode(encoding)
        except UnicodeEncodeError as err:
            raise ValueError("unsupported_character") from err
        if len(encoded) > 14:
            raise ValueError("short_text_too_long")


def build_output(data, *, output_id=None, registry_id=None):
    if not isinstance(data, dict):
        raise InputValidationError("base", "invalid_output")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise InputValidationError("name", "invalid_name")
    kind = data.get("kind")
    if kind not in KINDS:
        raise InputValidationError("kind", "invalid_output")
    notification = validate_notification(data.get("notification"), kind) if kind in ("notification", "overlay") else None
    if kind not in ("notification", "overlay") and data.get("notification") is not None:
        raise InputValidationError("base", "invalid_notification")
    entity_id = data.get("entity_id") or None
    if notification:
        if entity_id is not None:
            raise InputValidationError("entity_id", "invalid_notification")
    if entity_id is not None:
        if (not isinstance(entity_id, str) or not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id)
                or entity_id.split(".")[0] not in DOMAINS[kind]):
            raise InputValidationError("entity_id", "invalid_output_target")
    if kind == "switch" and entity_id is None:
        raise InputValidationError("entity_id", "output_target_required")
    if type(data.get("enabled")) is not bool:
        raise InputValidationError("enabled", "invalid_output")
    encoding = data.get("encoding", "latin-1")
    if encoding not in ("ascii", "latin-1"):
        raise InputValidationError("encoding", "invalid_output")
    for field in ("alarm_value", "acknowledged_value", "idle_value"):
        value = data.get(field)
        if kind == "switch":
            if value not in ("on", "off"):
                raise InputValidationError(field, "invalid_switch_value")
        else:
            try:
                validate_text(value, kind, encoding)
                if kind in ('notification','overlay') and len(''.join(part[0] for part in template_fields(value))) > 1024:
                    raise ValueError('notification_too_long')
            except ValueError as err:
                raise InputValidationError(field, str(err)) from err
    output_id = output_id if output_id is not None else uuid4().hex
    if not isinstance(output_id, str) or not re.fullmatch(r"[0-9a-f]{32}", output_id):
        raise InputValidationError("base", "invalid_output")
    if registry_id is not None and (not isinstance(registry_id, str) or not registry_id or entity_id is None):
        raise InputValidationError("base", "invalid_output")
    return OutputDefinition(output_id, name.strip(), kind, entity_id, registry_id,
                            data["enabled"], encoding, data["alarm_value"], data["acknowledged_value"], data["idle_value"], notification)


def load_output_config(options, rules):
    config = options.get(OUTPUT_CONFIG_KEY)
    if isinstance(config, dict) and type(config.get('version')) is int and config.get("version") == 1:
        config = deepcopy(config)
        config["version"] = OUTPUT_CONFIG_VERSION
        if isinstance(config.get("outputs"), list):
            for item in config["outputs"]:
                if isinstance(item, dict):
                    item.setdefault("notification", None)
    if (not isinstance(config, dict) or set(config) != {"version", "outputs", "bindings"}
            or type(config["version"]) is not int or config["version"] != OUTPUT_CONFIG_VERSION
            or not isinstance(config["outputs"], list) or len(config["outputs"]) > MAX_OUTPUTS
            or not isinstance(config["bindings"], dict)):
        raise ValueError("Invalid or unsupported output configuration")
    outputs = []
    for item in config["outputs"]:
        if not isinstance(item, dict) or set(item) != set(OutputDefinition.__dataclass_fields__):
            raise ValueError("Invalid output fields")
        outputs.append(build_output(item, output_id=item["id"], registry_id=item["entity_registry_id"]))
    ids = {item.id for item in outputs}
    if len(ids) != len(outputs):
        raise ValueError("Duplicate output IDs")
    # One definition per target avoids contradicting plans for the same actuator/display.
    targets = [item.entity_id for item in outputs if item.entity_id]
    registry_ids = [item.entity_registry_id for item in outputs if item.entity_registry_id]
    if len(set(targets)) != len(targets) or len(set(registry_ids)) != len(registry_ids):
        raise InputValidationError("entity_id", "duplicate_output_target")
    if not set(config["bindings"]) <= {rule.id for rule in rules}:
        raise ValueError("Unknown rule assignment")
    for assigned in config["bindings"].values():
        if (not isinstance(assigned, list) or not all(isinstance(item, str) for item in assigned)
                or len(set(assigned)) != len(assigned) or not set(assigned) <= ids):
            raise ValueError("Unknown or duplicate output assignment")
    return tuple(outputs), deepcopy(config["bindings"])


def serialize_output_config(outputs, bindings, rules):
    config = {"version": OUTPUT_CONFIG_VERSION, "outputs": [item.to_dict() for item in outputs], "bindings": deepcopy(bindings)}
    load_output_config({OUTPUT_CONFIG_KEY: config}, rules)
    return config


def ensure_output_options(options, rules):
    result = deepcopy(dict(options))
    if OUTPUT_CONFIG_KEY not in result:
        result[OUTPUT_CONFIG_KEY] = serialize_output_config([], {}, rules)
    outputs, bindings = load_output_config(result, rules)
    result[OUTPUT_CONFIG_KEY] = serialize_output_config(outputs, bindings, rules)
    return result
