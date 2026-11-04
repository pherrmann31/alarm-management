"""Serialized v0.9 upgrade and partial v1 schema regression tests."""
import importlib
from copy import deepcopy
import unittest

import test_inputs as inputs
import test_outputs as outputs
import test_rules as rules
import test_notifications as notifications
import test_session as sessions

configuration = importlib.import_module(inputs.NAME + '.configuration')
groups = importlib.import_module(inputs.NAME + '.groups')


class UpgradeTests(unittest.TestCase):
    def legacy(self):
        source = inputs.model.build_source(inputs.payload())
        rule = rules.model.build_rule(dict(name='Feuer Küche',input_ids=[source.id],mode='any',alarm_type='fire',enabled=True),[source.id])
        actor = outputs.config.build_output(outputs.values())
        notification = notifications.definition()
        options = inputs.options_for([source])
        options['rule_config'] = rules.model.serialize_rules([rule],[source])
        options['output_config'] = outputs.config.serialize_output_config([actor,notification],{rule.id:[actor.id,notification.id]},[rule])
        return options,source,rule,actor,notification

    def test_v09_options_preserved_with_notifications_and_bindings(self):
        raw,source,rule,actor,notification = self.legacy()
        before=deepcopy(raw)
        migrated,sources,loaded,targets,bindings=configuration.prepare_configuration(raw)
        self.assertEqual(raw,before)
        for key in ('input_config','rule_config','output_config'):
            self.assertEqual(migrated[key],raw[key])
        self.assertEqual(sources,(source,))
        self.assertEqual(loaded,(rule,))
        self.assertEqual(targets,(actor,notification))
        self.assertEqual(bindings,{rule.id:[actor.id,notification.id]})
        self.assertFalse(migrated['groups']['auto_smoke'])
        self.assertEqual(configuration.prepare_configuration(migrated)[0],migrated)

    def test_active_v09_alarm_survives_adding_groups(self):
        raw,source,rule,_,_=self.legacy()
        snapshot=[dict(id=source.id,name=source.name,entity_id=source.entity_id,status='matching',area_id='kitchen',area_name='Küche')]
        evaluated=rules.engine.evaluate_rules([rule],snapshot)
        state=sessions.session_module.reconcile(sessions.session_module.AlarmSession(),evaluated,'2026-11-04T12:00:00+00:00')
        restored=sessions.session_module.AlarmSession.from_dict(state.to_dict())
        configuration.prepare_configuration(raw)
        self.assertEqual(restored,state)
        self.assertEqual(restored.state,'active')

    def test_partial_group_draft_gains_defaults_without_losing_custom_group(self):
        raw,*_=self.legacy()
        config=groups.initial_config()
        custom=dict(id='c'*32,name='Erdgeschoss',kind='input',members=[],mode='any')
        config['items']=[config['items'][0],config['items'][1],custom]
        for key in ('priorities','house_ids','auto_house','house_pattern','house_label','house_trigger'):
            del config[key]
        raw['groups']=config
        migrated,*_=configuration.prepare_configuration(raw)
        self.assertIn(custom,migrated['groups']['items'])
        self.assertEqual(len(migrated['groups']['items']),5)

    def test_corrupt_values_not_silently_discarded_and_error_names_section(self):
        raw,*_=self.legacy()
        raw['groups']=groups.initial_config()
        raw['groups']['priorities']={'rule':'invalid'}
        with self.assertRaisesRegex(ValueError,'Gruppenkonfiguration'):
            configuration.prepare_configuration(raw)
        raw,*_=self.legacy()
        raw['output_config']['version']=999
        with self.assertRaisesRegex(ValueError,'Ausgänge und Benachrichtigungen'):
            configuration.prepare_configuration(raw)

    def test_dangling_group_members_give_specific_error(self):
        raw,*_=self.legacy()
        raw['groups']=groups.initial_config()
        raw['groups']['items'][0]['members']=['missing']
        with self.assertRaisesRegex(ValueError,'Gruppenverknüpfungen'):
            configuration.prepare_configuration(raw)
