"""Stable, non-nested groups and lossless input aggregation."""

from copy import deepcopy
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5
import re

KEY = "groups"
SMOKE_DEFAULT = uuid5(NAMESPACE_URL, "alarm_management:smoke:default").hex
SMOKE_ALL = uuid5(NAMESPACE_URL, "alarm_management:smoke:all").hex
HOUSE_DEFAULT = uuid5(NAMESPACE_URL, "alarm_management:house:default").hex
HOUSE_ALL = uuid5(NAMESPACE_URL, "alarm_management:house:all").hex


def initial_config():
    return {"version": 1, "items": [
        {"id": SMOKE_DEFAULT, "name": "Rauchmelder – Standard", "kind": "input", "members": [], "mode": "any"},
        {"id": SMOKE_ALL, "name": "Alle Rauchmelder", "kind": "input", "members": [], "mode": "any"},
        {"id": HOUSE_DEFAULT, "name": "Hausalarm – Standard", "kind": "input", "members": [], "mode": "any"},
        {"id": HOUSE_ALL, "name": "Alle Hausalarmtaster", "kind": "input", "members": [], "mode": "any"},
    ], "smoke_ids": [], "auto_smoke": False, "excluded": [], "assignments": {},
        "house_ids": [], "auto_house": False, "house_pattern": "", "house_label": "", "house_trigger": "single", "priorities": {}}


def load_groups(options):
    config = deepcopy(options.get(KEY, initial_config()))
    if not isinstance(config, dict) or set(config) != set(initial_config()) or type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("Invalid group configuration")
    if type(config["auto_smoke"]) is not bool or type(config['auto_house']) is not bool:
        raise ValueError("Invalid discovery setting")
    if any(not isinstance(config[k],str) or len(config[k])>255 for k in ('house_pattern','house_label','house_trigger')):
        raise ValueError('Invalid house discovery criteria')
    if config['auto_house'] and (not (config['house_pattern'].strip() or config['house_label'].strip()) or not config['house_trigger'].strip()):
        raise ValueError('House discovery requires explicit matching criteria and trigger')
    for field in ("smoke_ids", "excluded", "house_ids"):
        if not isinstance(config[field], list) or any(not isinstance(x, str) for x in config[field]):
            raise ValueError("Invalid discovery identities")
    if not isinstance(config["items"], list) or len(config["items"]) > 200:
        raise ValueError("Invalid groups")
    if not isinstance(config['assignments'], dict) or any(not isinstance(k,str) or not isinstance(v,list) or any(not isinstance(x,str) for x in v) for k,v in config['assignments'].items()):
        raise ValueError('Invalid group assignments')
    ids = set()
    if not isinstance(config['priorities'],dict) or any(not isinstance(k,str) or type(v) is not int or not 0<=v<=5 for k,v in config['priorities'].items()):
        raise ValueError('Invalid rule priorities')
    for item in config["items"]:
        if not isinstance(item, dict) or set(item) != {"id", "name", "kind", "members", "mode"}:
            raise ValueError("Invalid group fields")
        if not isinstance(item["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", item["id"]) or item["id"] in ids:
            raise ValueError("Duplicate or invalid group identity")
        ids.add(item["id"])
        if not isinstance(item["name"], str) or not 1 <= len(item["name"].strip()) <= 80:
            raise ValueError("Invalid group name")
        if item["kind"] not in ("input", "output", "notification") or item["mode"] not in ("any", "all"):
            raise ValueError("Invalid group type")
        if not isinstance(item["members"], list) or any(not isinstance(x, str) for x in item["members"]) or len(set(item["members"])) != len(item["members"]):
            raise ValueError("Invalid group members")
    if any(ids.intersection(item["members"]) for item in config["items"]):
        raise ValueError("Nested groups are not supported")
    for identity in (SMOKE_DEFAULT, SMOKE_ALL, HOUSE_DEFAULT, HOUSE_ALL):
        item = next((g for g in config["items"] if g["id"] == identity), None)
        if item is None or item["kind"] != "input" or item["mode"] != "any":
            raise ValueError("Missing built-in smoke group")
    return config


@dataclass(frozen=True)
class GroupSource:
    id: str
    name: str
    alarm_type: str = "fire"
    enabled: bool = True


def rule_sources(sources, config):
    return [*sources, *(GroupSource(g["id"], g["name"]) for g in config["items"] if g["kind"] == "input")]


def aggregate(snapshot, config):
    result = deepcopy(snapshot)
    by_id = {item["id"]: item for item in snapshot}
    for group in config["items"]:
        if group["kind"] != "input":
            continue
        members = config["smoke_ids"] if group["id"] == SMOKE_ALL else config['house_ids'] if group['id']==HOUSE_ALL else group["members"]
        items = [by_id.get(identity) for identity in members]
        states = [item["status"] if item else "missing" for item in items]
        if not states:
            status = "unknown"
        elif group["mode"] == "any":
            status = "matching" if "matching" in states else "not_matching" if all(s == "not_matching" for s in states) else "unknown"
        else:
            status = "not_matching" if "not_matching" in states else "matching" if all(s == "matching" for s in states) else "unknown"
        result.append({"id": group["id"], "name": group["name"], "entity_id": "group." + group["id"],
                       "status": status, "area_id": None, "area_name": None,
                       "member_states": dict(zip(members, states, strict=True)),
                       "contributors": [deepcopy(item) for item in items if item and item["status"] == "matching"]})
    return result


def expand_bindings(bindings, config):
    groups = {item["id"]: item for item in config["items"] if item["kind"] != "input"}
    return {rule: list(dict.fromkeys(member for target in targets
            for member in (groups[target]["members"] if target in groups else [target])))
            for rule, targets in bindings.items()}


def validate_catalogue(config, sources, rules, outputs):
    source_ids={s.id for s in sources}
    rule_ids={r.id for r in rules}
    group_ids={g['id'] for g in config['items']}
    if group_ids.intersection(source_ids | {o.id for o in outputs}):
        raise ValueError('Group identity collides with an entity definition')
    for group in config['items']:
        valid=source_ids if group['kind']=='input' else {o.id for o in outputs if bool(o.notification)==(group['kind']=='notification')}
        if not set(group['members'])<=valid:
            raise ValueError('Group contains missing members')
    if not set(config['smoke_ids']+config['house_ids'])<=source_ids:
        raise ValueError('Automatic group contains missing sources')
    destinations={g['id'] for g in config['items'] if g['kind']!='input'}
    if not set(config['assignments'])<=rule_ids or any(not set(ids)<=destinations for ids in config['assignments'].values()):
        raise ValueError('Invalid rule group assignment')


def move_source(config, source_id, destination):
    result = deepcopy(config)
    target = next((g for g in result["items"] if g["id"] == destination and g["kind"] == "input" and g["id"] not in (SMOKE_ALL,HOUSE_ALL)), None)
    if target is None:
        raise ValueError("Unknown destination")
    for group in result["items"]:
        if group["kind"] == "input":
            group["members"] = [identity for identity in group["members"] if identity != source_id]
    target["members"].append(source_id)
    return result
