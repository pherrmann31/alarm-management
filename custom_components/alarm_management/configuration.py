"""Validate upgrades without deleting sources, rules, outputs or alarm history."""
from copy import deepcopy

from .groups import KEY, load_groups, validate_catalogue
from .input_config import load_sources
from .rule_config import ensure_rule_options, load_rules
from .output_config import ensure_output_options, load_output_config


def prepare_configuration(raw):
    options = deepcopy(dict(raw))
    stage = 'Eingangsquellen'
    try:
        sources = load_sources(options)
        stage = 'Gruppenkonfiguration'
        groups = load_groups(options)
        options[KEY] = groups
        stage = 'Alarmregeln'
        options = ensure_rule_options(options, sources)
        rules = load_rules(options, sources)
        stage = 'Ausgänge und Benachrichtigungen'
        options = ensure_output_options(options, rules)
        outputs, bindings = load_output_config(options, rules)
        stage = 'Gruppenverknüpfungen'
        validate_catalogue(groups, sources, rules, outputs)
    except (ValueError, TypeError, KeyError) as err:
        raise ValueError(f'{stage}: {err}') from err
    return options, sources, rules, outputs, bindings
