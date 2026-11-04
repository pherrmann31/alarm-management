"""Versioned, frontend-independent rule model and one-time default generation."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import re
from uuid import NAMESPACE_URL, uuid4, uuid5

from .const import ALARM_TYPES, MAX_RULES, RULE_CONFIG_KEY, RULE_CONFIG_VERSION
from .input_config import InputValidationError


@dataclass(frozen=True)
class AlarmRule:
    id: str
    name: str
    input_ids: tuple[str, ...]
    mode: str
    alarm_type: str
    enabled: bool

    def to_dict(self):
        result = asdict(self)
        result["input_ids"] = list(self.input_ids)
        return result


def default_rule_id(input_id):
    return uuid5(NAMESPACE_URL, f"alarm_management:default:{input_id}").hex


def default_rule_name(name):
    return f"Einzelregel: {name}"[:80]


def build_rule(data, source_ids, *, rule_id=None):
    if not isinstance(data, dict):
        raise InputValidationError("base", "invalid_rule")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise InputValidationError("name", "invalid_name")
    selected = data.get("input_ids")
    if (not isinstance(selected, list) or not selected or not all(isinstance(item, str) for item in selected)
            or len(set(selected)) != len(selected)):
        raise InputValidationError("input_ids", "choose_inputs")
    if not set(selected) <= set(source_ids):
        raise InputValidationError("input_ids", "unknown_input")
    if data.get("mode") not in ("any", "all"):
        raise InputValidationError("mode", "invalid_mode")
    if data.get("alarm_type") not in ALARM_TYPES:
        raise InputValidationError("alarm_type", "invalid_alarm_type")
    if type(data.get("enabled")) is not bool:
        raise InputValidationError("enabled", "invalid_rule")
    rule_id = rule_id if rule_id is not None else uuid4().hex
    if not isinstance(rule_id, str) or not re.fullmatch(r"[0-9a-f]{32}", rule_id):
        raise InputValidationError("base", "invalid_rule")
    return AlarmRule(rule_id, name.strip(), tuple(selected), data["mode"], data["alarm_type"], data["enabled"])


def load_rules(options, sources):
    from .groups import load_groups, rule_sources
    sources = list({source.id: source for source in rule_sources(sources, load_groups(options))}.values())
    config = options.get(RULE_CONFIG_KEY)
    if (not isinstance(config, dict) or set(config) != {"version", "rules"}
            or type(config["version"]) is not int or config["version"] != RULE_CONFIG_VERSION
            or not isinstance(config["rules"], list) or len(config["rules"]) > MAX_RULES):
        raise ValueError("Invalid or unsupported rule configuration")
    rules = []
    for raw in config["rules"]:
        if not isinstance(raw, dict) or set(raw) != set(AlarmRule.__dataclass_fields__):
            raise ValueError("Invalid rule fields")
        rules.append(build_rule(raw, {source.id for source in sources}, rule_id=raw["id"]))
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("Duplicate rule IDs")
    return tuple(rules)


def serialize_rules(rules, sources):
    config = {"version": RULE_CONFIG_VERSION, "rules": [rule.to_dict() for rule in rules]}
    load_rules({RULE_CONFIG_KEY: config}, sources)
    return config


def ensure_rule_options(options, sources):
    """Generate defaults exactly once. An explicit empty rule list stays empty."""
    result = deepcopy(dict(options))
    if RULE_CONFIG_KEY not in result:
        rules = [AlarmRule(default_rule_id(source.id), default_rule_name(source.name),
                           (source.id,), "any", source.alarm_type, source.enabled) for source in sources]
        result[RULE_CONFIG_KEY] = serialize_rules(rules, sources)
    load_rules(result, sources)
    return result
