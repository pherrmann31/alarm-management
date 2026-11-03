"""Notification routing, persistent per-recipient deduplication, UI and regressions."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import importlib
import types
import unittest
from unittest.mock import AsyncMock

import test_inputs as inputs
import test_outputs as outputs
import test_live_outputs as live_tests
import test_platforms as platforms
import test_session as sessions
import test_simulation as old

notify=importlib.import_module(f'{old.PACKAGE}.notification')


def definition(kind='notification', routes=None, **updates):
    data=outputs.values(kind,**{'alarm_value':'{alarmtyp}: {quelle} ({bereich})','acknowledged_value':'','idle_value':'',**updates})
    data['notification']['routes']=routes or (['mobile_app:notify.mobile_app_phone','entity:notify.tablet'] if kind=='notification' else ['browser:'+'a'*32])
    return outputs.config.build_output(data)


class NotificationConfigTests(unittest.TestCase):
    def test_legacy_config_migrates_and_ids_are_preserved(self):
        item=outputs.config.build_output(outputs.values())
        record=item.to_dict()
        record.pop('notification')
        legacy={'output_config':{'version':1,'outputs':[record],'bindings':{}}}
        migrated=outputs.config.ensure_output_options(legacy,[])
        loaded,_=outputs.config.load_output_config(migrated,[])
        self.assertEqual(migrated['output_config']['version'],2)
        self.assertEqual(loaded[0],item)
        self.assertEqual(legacy['output_config']['version'],1)
        with self.assertRaises(ValueError):
            outputs.config.load_output_config({'output_config':dict(legacy['output_config'],version=True)},[])

    def test_notification_destinations_and_metadata_restricted(self):
        original=definition().to_dict()
        for route in ('script.any','entity:light.kitchen','pushover:notify.send_message','browser:'+'a'*32):
            data=deepcopy(original)
            data['notification']['routes']=[route]
            with self.subTest(route=route),self.assertRaises(ValueError):
                outputs.config.build_output(data)
        for value in ([],['mobile_app:notify.mobile_app_phone']*2,['mobile_app:notify.mobile_app_phone']*21):
            data=deepcopy(original)
            data['notification']['routes']=value
            with self.assertRaises(ValueError):
                outputs.config.build_output(data)

    def test_overlay_never_has_empty_or_global_targets(self):
        data=definition('overlay').to_dict()
        for routes in ([],['browser:all'],['browser:THIS'],['entity:notify.phone']):
            data['notification']['routes']=routes
            with self.assertRaises(ValueError):
                outputs.config.build_output(data)

    def test_priority_two_and_unapproved_metadata_are_rejected(self):
        data=definition(routes=['pushover:notify.pushover']).to_dict()
        data['notification']['priority']=2
        with self.assertRaises(ValueError):
            outputs.config.build_output(data)
        data['notification']['priority']=0
        data['notification']['data']={'action':'anything'}
        with self.assertRaises(ValueError):
            outputs.config.build_output(data)

    def test_shared_alarm_content_and_size_limits(self):
        item=definition()
        plan=outputs.plan(item)
        self.assertIn('Feuer',plan['value'])
        self.assertIn('Flur',plan['value'])
        long=replace(item,alarm_value='x'*1025)
        self.assertEqual(outputs.plan(long)['error'],'notification_too_long')

    def test_new_device_does_not_change_existing_recipient_identity(self):
        item=definition()
        session=outputs.alarm_session()
        plan=outputs.plan(item,session)
        oldkey=notify.request(item,plan,session,item.notification['routes'][0])[0]
        data=deepcopy(item.notification)
        data['routes'].append('entity:notify.extra')
        updated=replace(item,notification=data)
        self.assertEqual(oldkey,notify.request(updated,plan,session,data['routes'][0])[0])


class NotificationExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def manager(self,item=None,source_on=True):
        # Existing device adapter tests provide an isolated HA service registry.
        manager,item=await live_tests.LiveExecutionTests.make_manager(self,item or definition(),source_on=source_on,update_state=False)
        manager.hass.services.async_call=AsyncMock()
        return manager,item

    async def shutdown(self,manager):
        await live_tests.LiveExecutionTests.shutdown(self,manager)

    async def test_multiple_devices_receive_rendered_message_and_no_device_state_writes(self):
        manager,item=await self.manager()
        manager.executor.start()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,2)
        calls=manager.hass.services.async_call.await_args_list
        self.assertEqual(calls[0].args[:2],('notify','mobile_app_phone'))
        self.assertEqual(calls[1].kwargs['target'],{'entity_id':'notify.tablet'})
        self.assertIn('Feuer',calls[0].args[2]['message'])
        self.assertEqual(manager.session.executions[item.id]['status'],'sent')
        self.assertFalse(manager.session.executions[item.id]['owned'])
        entry=types.SimpleNamespace(entry_id='integration',runtime_data=manager)
        self.assertEqual(platforms.sensor.OutputValueSensor(entry,item).native_value,'An HA übergeben')
        self.assertEqual(platforms.sensor.OutputSummarySensor(entry).native_value,'Bereit')

    async def test_repeat_refresh_reload_and_successful_manual_retry_do_not_repeat_push(self):
        manager,item=await self.manager()
        manager.executor.start()
        await manager.async_drain()
        for _ in range(3):
            await manager.async_process_inputs([sessions.source()])
            await manager.async_drain()
        manager.session=sessions.session_module.AlarmSession.from_dict(manager.session.to_dict())
        manager.executor.stop()
        manager.executor=live_tests.live.LiveOutputExecutor(manager)
        manager.executor.start()
        await manager.async_drain()
        manager.executor.retry()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,2)

    async def test_new_identical_alarm_occurrence_is_sent_again(self):
        manager,item=await self.manager()
        manager.executor.start()
        await manager.async_drain()
        await manager.async_process_inputs([sessions.source(status='not_matching')])
        await manager.async_action('reset')
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,2)
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,4)

    async def test_partial_failure_does_not_resend_successful_recipient(self):
        manager,item=await self.manager()
        async def call(domain,service,data,**kwargs):
            if service=='send_message':
                raise old.FakeHomeAssistantError('Tablet offline')
        manager.hass.services.async_call.side_effect=call
        manager.executor.start()
        await manager.async_drain()
        self.assertEqual(manager.session.executions[item.id]['status'],'failed')
        manager.executor.schedule()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,2)
        manager.hass.services.async_call.side_effect=None
        manager.executor.retry()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,3)
        self.assertEqual(manager.session.executions[item.id]['status'],'sent')

    async def test_unknown_pending_after_restart_does_not_blindly_send(self):
        item=definition(routes=['mobile_app:notify.mobile_app_phone'])
        manager,item=await self.manager(item)
        plan=manager.session.output_plan[item.id]
        key=notify.request(item,plan,manager.session,item.notification['routes'][0])[0]
        child=replace(item,id=notify.delivery_id(item.id,item.notification['routes'][0]))
        await manager.record_delivery(child,plan,key,'pending',None,False)
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertEqual(manager.session.executions[item.id]['status'],'failed')

    async def test_storage_failure_prevents_any_notification(self):
        manager,item=await self.manager()
        manager.store.fail=True
        manager.executor.start()
        with self.assertLogs(level='ERROR'):
            await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()

    async def test_idle_installation_and_disabled_output_are_silent(self):
        item=definition(idle_value='Bereit')
        manager,item=await self.manager(item,source_on=False)
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        for _ in range(3):
            await manager.async_process_inputs([sessions.source(status='not_matching')])
            await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        manager.outputs=(replace(item,enabled=False),)
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()

    async def test_reset_messages_work_after_silent_alarm_and_acknowledgement(self):
        item=definition(alarm_value='',acknowledged_value='',idle_value='Bereit')
        manager,item=await self.manager(item)
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        for count in (2,4):
            await manager.async_process_inputs([sessions.source(status='not_matching')])
            await manager.async_action('reset')
            await manager.async_drain()
            self.assertEqual(manager.hass.services.async_call.await_count,count)
            await manager.async_process_inputs([sessions.source()])
            await manager.async_drain()

    async def test_reset_during_inflight_notification_drops_remaining_old_recipients(self):
        manager,item=await self.manager()
        began=asyncio.Event()
        release=asyncio.Event()
        async def call(*args,**kwargs):
            began.set()
            await release.wait()
        manager.hass.services.async_call.side_effect=call
        manager.executor.start()
        await began.wait()
        await manager.async_process_inputs([sessions.source(status='not_matching')])
        await manager.async_action('reset')
        release.set()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,1)

    async def test_removed_recipients_are_pruned_without_removing_history(self):
        manager,item=await self.manager()
        manager.executor.start()
        await manager.async_drain()
        children=[key for key in manager.session.executions if '_notify_' in key]
        self.assertEqual(len(children),2)
        changed=replace(item,notification={**item.notification,'routes':[item.notification['routes'][0]]})
        manager.outputs=(changed,)
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        self.assertEqual(len([key for key in manager.session.executions if '_notify_' in key]),1)
        self.assertGreaterEqual(len(manager.session.delivery_history),4)

    async def test_optional_acknowledgement_and_reset_messages(self):
        item=definition(acknowledged_value='Quittiert',idle_value='Bereit')
        manager,item=await self.manager(item)
        manager.executor.start()
        await manager.async_drain()
        await manager.async_action('acknowledge')
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,4)
        await manager.async_process_inputs([sessions.source(status='not_matching')])
        await manager.async_action('reset')
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,6)

    async def test_overlay_uses_explicit_browser_device_and_escapes_html(self):
        item=definition('overlay',alarm_value='<script>danger</script>\nAlarm')
        manager,item=await self.manager(item)
        manager.executor.start()
        await manager.async_drain()
        call=manager.hass.services.async_call.await_args
        self.assertEqual(call.args[:2],('browser_mod','popup'))
        self.assertEqual(call.args[2]['browser_id'],['a'*32])
        self.assertNotIn('<script>',call.args[2]['content'])
        self.assertIn('&lt;script&gt;',call.args[2]['content'])
        self.assertNotIn('user_id',call.args[2])

    async def test_pushover_has_explicit_device_and_non_emergency_priority(self):
        item=definition(routes=['pushover:notify.pushover'])
        settings={**item.notification,'devices':'tablet,phone','priority':1}
        manager,item=await self.manager(replace(item,notification=settings))
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_awaited_once_with('notify','pushover',
            {'title':'Alarm','message':'Feuer: Quelle a (Flur)','target':['tablet','phone'],'data':{'priority':1}},blocking=True)


class NotificationFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_devices_have_names_and_multiple_selection(self):
        flow=outputs.OutputFlowTests().flow()
        device=types.SimpleNamespace(id='a'*32,name_by_user='Flur Tablet',name='Tablet',identifiers={('browser_mod','browser-flur')})
        flow.hass.devices[device.id]=device
        await flow.async_step_init()
        form=await flow.async_step_notification_add({'kind':'overlay'})
        delivery=next(value for field,value in form['data_schema'].schema.items() if field.key=='delivery')
        selector=next(value for field,value in delivery.schema.schema.items() if field.key=='routes')
        self.assertTrue(selector.config['multiple'])
        self.assertIn({'value':'browser:'+'a'*32,'label':'Flur Tablet'},selector.config['options'])
        result=await flow.async_step_output_details({'name':'Tablet','enabled':True,'delivery':{'routes':['browser:'+'a'*32],'title':'Alarm'},
            'alarm':{'alarm_value':'{quelle}'},'acknowledged':{'acknowledged_value':''},'idle':{'idle_value':''}})
        self.assertEqual(result['type'],'menu')
        saved=flow._outputs[0]
        self.assertEqual(saved.notification['routes'],['browser:'+'a'*32])

    async def test_native_app_entities_are_selectable_by_friendly_name(self):
        flow=outputs.OutputFlowTests().flow()
        entity=flow.hass.registry.add('notify.phone')
        entity.platform='mobile_app'
        flow.hass.values['notify.phone']='unknown'
        choices=flow._notification_choices('notification',[]).config['options']
        self.assertIn('entity:notify.phone',[item['value'] for item in choices])
