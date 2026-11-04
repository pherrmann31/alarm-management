"""Pure automatic enrollment policy, independent of Home Assistant."""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5
from .const import MAX_INPUTS
from .groups import SMOKE_DEFAULT
from .input_config import build_source
from .groups import HOUSE_DEFAULT
from fnmatch import fnmatchcase

def discover(sources, config, candidates):
    """Never infer a smoke alarm from a name, battery sensor or unavailable state."""
    result = list(sources)
    groups = deepcopy(config)
    added = []
    default = next(g for g in groups['items'] if g['id'] == SMOKE_DEFAULT)
    for item in candidates:
        identity = item['registry_id']
        if identity in groups['excluded'] or item['entity_id'].split('.')[0] != 'binary_sensor' or item['device_class'] != 'smoke' or item['disabled']:
            continue
        existing = next((s for s in result if s.entity_registry_id == identity or s.entity_id == item['entity_id']), None)
        if existing:
            if existing.trigger_state == 'on' and existing.id not in groups['smoke_ids']:
                groups['smoke_ids'].append(existing.id)
            continue
        if not groups['auto_smoke'] or len(result) >= MAX_INPUTS:
            continue
        source = build_source({'name': item['name'][:80], 'entity_id': item['entity_id'], 'trigger_state': 'on',
                               'alarm_type': 'fire', 'enabled': True},
                              source_id=uuid5(NAMESPACE_URL, 'alarm_management:discovery:' + identity).hex,
                              registry_id=identity)
        result.append(source)
        groups['smoke_ids'].append(source.id)
        default['members'].append(source.id)
        added.append(source)
    if groups['auto_house']:
        default = next(g for g in groups['items'] if g['id'] == HOUSE_DEFAULT)
        for item in candidates:
            if item['disabled'] or item['registry_id'] in groups['excluded'] or item['device_class']=='smoke':
                continue
            if item['entity_id'].split('.')[0] not in ('event','binary_sensor','sensor','input_boolean'):
                continue
            if groups['house_label'] and groups['house_label'] not in item.get('labels',[]):
                continue
            pattern=groups['house_pattern'].strip().casefold()
            if pattern and not (fnmatchcase(item['entity_id'].casefold(),pattern) or fnmatchcase(item['name'].casefold(),pattern)):
                continue
            if item['entity_id'].startswith('event.') and groups['house_trigger'] not in item.get('event_types',[]):
                continue
            existing=next((s for s in result if s.entity_registry_id==item['registry_id'] or s.entity_id==item['entity_id']),None)
            if existing:
                if existing.trigger_state==groups['house_trigger'] and existing.id not in groups['house_ids']:
                    groups['house_ids'].append(existing.id)
                continue
            if len(result)>=MAX_INPUTS:
                break
            source=build_source({'name':item['name'][:80], 'entity_id':item['entity_id'], 'trigger_state':groups['house_trigger'],
                'alarm_type':'house','enabled':True},source_id=uuid5(NAMESPACE_URL,'alarm_management:discovery:'+item['registry_id']).hex,registry_id=item['registry_id'])
            result.append(source);groups['house_ids'].append(source.id);default['members'].append(source.id);added.append(source)
    return tuple(result), groups, added

