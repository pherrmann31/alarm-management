"""Group contracts, lossless rule evaluation and stable automatic enrollment."""
import importlib
from copy import deepcopy
import unittest
import types
import asyncio
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import test_inputs as inputs
import test_rules as rules
import test_outputs as outputs
import test_session as sessions
import test_simulation as old
import test_platforms as platforms

groups = importlib.import_module(inputs.NAME + '.groups')
discovery = importlib.import_module(inputs.NAME + '.discovery_model')


class GroupsTests(unittest.TestCase):
    def candidate(self, identity='registry-kitchen', **kw):
        return dict(registry_id=identity, entity_id='binary_sensor.kitchen', name='Küche', device_class='smoke', disabled=False, **kw)

    def test_discovery_is_opt_in(self):
        sources, config, added = discovery.discover([], groups.initial_config(), [self.candidate()])
        self.assertEqual(sources, ())
        self.assertEqual(added, [])

    def enrolled(self):
        config = groups.initial_config()
        config['auto_smoke'] = True
        return discovery.discover([], config, [self.candidate()])

    def test_auto_enrollment_idempotent_and_standard_membership(self):
        sources, config, added = self.enrolled()
        self.assertEqual(config['items'][0]['members'], [sources[0].id])
        self.assertEqual(config['smoke_ids'], [sources[0].id])
        again, revised, added = discovery.discover(sources, config, [self.candidate()])
        self.assertEqual(again, sources)
        self.assertEqual(revised, config)
        self.assertEqual(added, [])

    def test_move_persists_and_next_detector_goes_to_standard(self):
        sources, config, _ = self.enrolled()
        floor='f'*32
        config['items'].append(dict(id=floor,name='EG',kind='input',members=[],mode='any'))
        config=groups.move_source(config,sources[0].id,floor)
        second=self.candidate('new')
        second['entity_id']='binary_sensor.hall'
        revised,config,added=discovery.discover(sources,config,[self.candidate(),second])
        self.assertEqual(config['items'][0]['members'],[added[0].id])
        self.assertEqual(config['items'][-1]['members'],[sources[0].id])
        self.assertEqual(set(config['smoke_ids']),{s.id for s in revised})

    def test_unrelated_battery_and_disabled_not_adopted(self):
        config=groups.initial_config();config['auto_smoke']=True
        for changes in ({'device_class':'battery'},{'disabled':True},{'entity_id':'sensor.smoke'}):
            candidate=self.candidate();candidate.update(changes)
            self.assertEqual(discovery.discover([],config,[candidate])[0],())

    def test_empty_group_unknown(self):
        self.assertTrue(all(item['status']=='unknown' for item in groups.aggregate([],groups.initial_config())))

    def test_contributors_survive_group_and_direct_duplicate(self):
        sources,config,_=self.enrolled();source=sources[0]
        snapshot=[dict(id=source.id,name='Küche',entity_id=source.entity_id,status='matching',area_id='eg',area_name='Küche')]
        rule=rules.model.build_rule(dict(name='Feuer',input_ids=[groups.SMOKE_ALL,source.id],mode='any',alarm_type='fire',enabled=True),[groups.SMOKE_ALL,source.id])
        result=rules.engine.evaluate_rules([rule],groups.aggregate(snapshot,config))[0]
        self.assertEqual(result['status'],'matching')
        self.assertEqual([s['id'] for s in result['sources']],[source.id])
        self.assertEqual(result['area_name'],'Küche')
        session=sessions.session_module.reconcile(sessions.session_module.AlarmSession(),[result],'2026-11-04T12:00:00+00:00')
        self.assertEqual(sessions.session_module.AlarmSession.from_dict(session.to_dict()),session)

    def test_output_group_expansion_deduplicates(self):
        config=groups.initial_config()
        config['items'].append(dict(id='f'*32,name='Sirenen',kind='output',members=['a','b'],mode='any'))
        self.assertEqual(groups.expand_bindings({'rule':['a','f'*32]},config),{'rule':['a','b']})

    def test_nested_groups_rejected(self):
        config=groups.initial_config();config['items'][0]['members']=[groups.SMOKE_ALL]
        with self.assertRaises(ValueError):groups.load_groups({groups.KEY:config})

    def test_house_discovery_requires_pattern_or_label(self):
        config=groups.initial_config();config['auto_house']=True
        with self.assertRaises(ValueError):groups.load_groups({groups.KEY:config})

    def test_house_event_matches_pattern_and_event_type(self):
        config=groups.initial_config();config.update(auto_house=True,house_pattern='event.alarm_*',house_trigger='single')
        candidate=self.candidate();candidate.update(entity_id='event.alarm_hall',device_class='button',event_types=['single','double'])
        sources,config,added=discovery.discover([],config,[candidate])
        self.assertEqual(len(added),1)
        self.assertEqual(added[0].alarm_type,'house')
        self.assertIn(added[0].id,config['house_ids'])
        candidate['event_types']=['double']
        self.assertEqual(discovery.discover([],config,[candidate])[0],())

    def test_event_pulse_not_replayed_at_startup(self):
        hass=inputs.FakeHass()
        source=inputs.model.build_source(inputs.payload(entity_id='event.alarm',trigger_state='single'))
        timestamp=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        current=types.SimpleNamespace(entity_id='event.alarm',state=timestamp,attributes={'event_type':'single'})
        hass.states.get=lambda entity:current
        monitor=inputs.monitor_module.InputMonitor(hass,'integration',[source])
        observed=[]
        monitor.start(lambda:observed.append(deepcopy(monitor.snapshot)))
        self.assertEqual(observed[-1][0]['status'],'not_matching')
        old=current
        current=types.SimpleNamespace(entity_id='event.alarm',state=datetime.now(timezone.utc).isoformat(),attributes={'event_type':'single'})
        monitor._state_changed(types.SimpleNamespace(data={'new_state':current,'old_state':old}))
        self.assertEqual([s[0]['status'] for s in observed],['not_matching','matching','not_matching'])
        monitor.stop()


class GroupFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_managed_smoke_rule_preserves_output_group_reference(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        output=outputs.config.build_output(outputs.values())
        flow._outputs=[output]
        identity='d'*32
        flow._groups['items'].append(dict(id=identity,name='Haus',kind='output',members=[output.id],mode='any'))
        flow._set_auto_rule(groups.SMOKE_ALL,[identity],'fire')
        result=flow._finish(flow._sources)
        self.assertEqual(result['type'],'create_entry')
        config=groups.load_groups(result['data'])
        loaded=rules.model.load_rules(result['data'],flow._sources)
        groups.validate_catalogue(config,flow._sources,loaded,flow._outputs)
        self.assertEqual(groups.expand_bindings(config['assignments'],config)[loaded[-1].id],[output.id])

    async def test_deleting_member_in_group_is_blocked(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        source=inputs.model.build_source(inputs.payload())
        flow._sources=[source]
        flow._groups['items'][0]['members']=[source.id]
        result=flow._finish([])
        self.assertEqual(result['reason'],'group_member_in_use')

    async def test_discovery_enrolls_and_triggers_already_active_detector_live(self):
        config=groups.initial_config();config['auto_smoke']=True
        hass=inputs.FakeHass({groups.KEY:config})
        hass.loop=asyncio.get_running_loop();hass.async_create_task=asyncio.create_task
        hass.config_entries=types.SimpleNamespace(async_update_entry=lambda entry,**kw:setattr(entry,'options',kw['options']))
        hass.values['binary_sensor.kitchen']='on'
        hass.registry.add('binary_sensor.kitchen','registry-kitchen')
        manager=old.manager_module.AlarmManager(hass,'integration')
        await manager.async_load();manager.running=True;manager.groups=config
        rule=rules.model.build_rule(dict(name='Feuer',input_ids=[groups.SMOKE_ALL],mode='any',alarm_type='fire',enabled=True),[groups.SMOKE_ALL])
        manager.rules=(rule,)
        manager.inputs=inputs.monitor_module.InputMonitor(hass,'integration',())
        manager.inputs.start(manager.inputs_changed)
        scanner=platforms.lifecycle.SmokeDiscovery(hass,hass.entry,manager)
        with patch.dict(scanner.refresh.__globals__,{'candidates':lambda hass:[GroupsTests().candidate()]}):
            await scanner.refresh()
            await manager.async_drain()
        self.assertEqual(manager.session.state,'active')
        self.assertEqual(len(manager.inputs.sources),1)
        self.assertEqual(manager.session.alarms[rule.id]['sources'][0]['entity_id'],'binary_sensor.kitchen')
        self.assertTrue(any(event['event']=='discovery_added' for event in manager.session.history))
        sessions.session_module.AlarmSession.from_dict(manager.session.to_dict())
        manager.running=False;manager.stop_inputs();await manager.async_drain()

    async def test_rule_can_reference_empty_standard_group(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        form=await flow._rule_form('rule_add',dict(name='Feuer',input_ids=[groups.SMOKE_ALL],mode='any',alarm_type='fire',enabled=True))
        self.assertEqual(form['type'],'menu')
        result=flow._finish(flow._sources)
        self.assertEqual(result['type'],'create_entry')
        rules.model.load_rules(result['data'],flow._sources)

    async def test_group_crud_and_rule_roundtrip(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        await flow.async_step_group_add({'kind':'input'})
        result=await flow.async_step_group_details({'name':'EG','members':[],'mode':'any'})
        config=groups.load_groups(result['data'])
        identity=config['items'][-1]['id']
        flow._groups=config
        await flow._rule_form('rule_add',dict(name='EG Alarm',input_ids=[identity],mode='any',alarm_type='fire',enabled=True))
        result=flow._finish(flow._sources)
        self.assertEqual(result['type'],'create_entry')
        rules.model.load_rules(result['data'],flow._sources)
