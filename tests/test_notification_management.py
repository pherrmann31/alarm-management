"""Separated navigation, reset rejection delivery and scoped popup acknowledgement."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import types
import unittest

import test_inputs as inputs
import test_outputs as outputs
import test_rules as rules
import test_session as sessions
import test_notifications as notifications
import test_form_defaults as defaults
import test_simulation as old


class NotificationNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_notification_menu_has_no_entity_target_and_no_actuator_kinds(self):
        flow=outputs.OutputFlowTests().flow()
        menu=await flow.async_step_notifications()
        self.assertIn('notification_add',menu['menu_options'])
        form=await flow.async_step_notification_add()
        fields={field.key:value for field,value in form['data_schema'].schema.items()}
        self.assertNotIn('entity_id',fields)
        self.assertEqual(fields['kind'].config['options'],['notification','overlay'])
        await flow.async_step_outputs()
        form=await flow.async_step_output_add()
        fields={field.key:value for field,value in form['data_schema'].schema.items()}
        self.assertIn('entity_id',fields)
        self.assertEqual(fields['kind'].config['options'],['switch','short_text','long_text'])

    async def test_wrong_menu_cannot_create_notification(self):
        flow=outputs.OutputFlowTests().flow()
        form=await flow.async_step_output_add({'kind':'notification'})
        self.assertEqual(form['errors'],{'kind':'invalid_output'})
        self.assertIsNone(flow._pending_output)

    async def test_list_choices_are_separated_with_stable_ids(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        actuator=outputs.config.build_output(outputs.values())
        notification=notifications.definition()
        flow._outputs=[actuator,notification]
        await flow.async_step_outputs()
        self.assertEqual([item['value'] for item in flow._output_choices().config['options']],[actuator.id])
        await flow.async_step_notifications()
        self.assertEqual([item['value'] for item in flow._output_choices().config['options']],[notification.id])

    async def test_rule_edit_splits_and_preserves_both_assignments(self):
        flow,sources=rules.RuleFlowTests().flow()
        await flow.async_step_init()
        actuator=outputs.config.build_output(outputs.values())
        notification=notifications.definition()
        flow._outputs=[actuator,notification]
        rule=flow._rules[0]
        flow._bindings[rule.id]=[actuator.id,notification.id]
        form=await flow.async_step_rule_edit({'rule_id':rule.id})
        data=defaults.frontend_initial_data(form['data_schema'])
        self.assertEqual(data['then']['output_ids'],[actuator.id])
        self.assertEqual(data['then']['notification_ids'],[notification.id])
        result=await flow.async_step_rule_edit_details(data)
        saved,bindings=outputs.config.load_output_config(result['data'],flow._rules)
        self.assertEqual(bindings[rule.id],[actuator.id,notification.id])
        self.assertEqual({item.id for item in saved},{actuator.id,notification.id})

    async def test_rule_selector_contains_names_without_or_and_suffix(self):
        flow,_=rules.RuleFlowTests().flow()
        await flow.async_step_init()
        self.assertEqual([item['label'] for item in flow._rule_choices().config['options']],[rule.name for rule in flow._rules])

    async def test_new_notification_has_acknowledgement_and_reset_defaults(self):
        flow=outputs.OutputFlowTests().flow()
        form=await flow.async_step_notification_add({'kind':'notification'})
        data=defaults.frontend_initial_data(form['data_schema'])
        self.assertIn('quittiert',data['acknowledged']['acknowledged_value'])
        self.assertIn('Reset erfolgreich',data['idle']['idle_value'])
        saved=notifications.definition(acknowledged_value='',idle_value='')
        edited=defaults.frontend_initial_data(flow._output_schema(saved.to_dict()))
        self.assertEqual(edited['acknowledged']['acknowledged_value'],'')
        self.assertEqual(edited['idle']['idle_value'],'')


class NotificationFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def manager(self,item=None):
        return await notifications.NotificationExecutionTests.manager(self,item)

    async def shutdown(self,manager):
        await notifications.NotificationExecutionTests.shutdown(self,manager)

    async def test_reset_rejection_sends_the_reason_without_resetting_alarm(self):
        item=notifications.definition(routes=['mobile_app:notify.mobile_app_phone'])
        manager,item=await self.manager(item)
        manager.executor.start()
        await manager.async_drain()
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action('reset')
        await manager.async_drain()
        message=manager.hass.services.async_call.await_args.args[2]['message']
        self.assertIn('Reset nicht möglich',message)
        self.assertIn('Quelle a',message)
        self.assertIn('weiterhin ausgelöst',message)
        self.assertEqual(manager.session.state,'active')
        self.assertEqual(manager.hass.services.async_call.await_count,2)
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count,2)

    async def test_unknown_input_reason_is_delivered(self):
        manager,item=await self.manager(notifications.definition(routes=['mobile_app:notify.mobile_app_phone']))
        manager.executor.start()
        await manager.async_drain()
        await manager.async_process_inputs([sessions.source(status='unknown')])
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action('reset')
        await manager.async_drain()
        message=manager.hass.services.async_call.await_args.args[2]['message']
        self.assertIn('Eingangsstatus nicht eindeutig',message)

    async def test_rejected_reset_does_not_change_actuator_request(self):
        manager,item=await self.manager(notifications.definition())
        actuator=outputs.config.build_output(outputs.values())
        manager.outputs=(item,actuator)
        manager.output_bindings={'rule':[item.id,actuator.id]}
        await manager.async_process_inputs([sessions.source()])
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action('reset')
        self.assertEqual(manager.session.output_plan[actuator.id]['value'],'on')
        self.assertIn('Reset nicht möglich',manager.session.output_plan[item.id]['value'])

    async def test_unrelated_notification_is_not_repeated_on_reset_error(self):
        a=notifications.definition(routes=['mobile_app:notify.mobile_app_a'])
        b=notifications.definition(routes=['mobile_app:notify.mobile_app_b'])
        manager,_=await self.manager(a)
        manager.outputs=(a,b)
        manager.rules=(rules.live_rule(ids=('a',)),replace(rules.live_rule(ids=('b',)),id='other',name='Andere Regel'))
        manager.output_bindings={'rule':[a.id],'other':[b.id]}
        await manager.async_process_inputs([sessions.source(),sessions.source('b')])
        manager.executor.start()
        await manager.async_drain()
        await manager.async_process_inputs([sessions.source(),sessions.source('b','not_matching')])
        await manager.async_drain()
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action('reset')
        await manager.async_drain()
        calls=manager.hass.services.async_call.await_args_list
        self.assertEqual(sum(call.args[1]=='mobile_app_b' for call in calls),1)
        self.assertEqual(sum(call.args[1]=='mobile_app_a' for call in calls),2)

    async def test_popup_button_acknowledges_and_returns_server_confirmation(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        manager.executor.start()
        await manager.async_drain()
        popup=manager.hass.services.async_call.await_args.args[2]
        self.assertEqual(popup['right_button'],'Quittieren')
        self.assertFalse(popup['right_button_close'])
        self.assertEqual(popup['right_button_action']['service'],'alarm_management.acknowledge_popup')
        data=popup['right_button_action']['data']
        await manager.async_acknowledge_popup(data['output_id'],data['token'])
        await manager.async_drain()
        self.assertEqual(manager.session.state,'acknowledged')
        self.assertEqual(manager.session.history[-1]['event'],'popup_acknowledged')
        feedback=manager.hass.services.async_call.await_args.args[2]
        self.assertIn('Quittierung übernommen',feedback['content'])
        self.assertNotIn('right_button_action',feedback)
        sessions.session_module.AlarmSession.from_dict(manager.session.to_dict())

    async def test_popup_acknowledgement_does_not_touch_other_rule_or_manual_alarm(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        manager.rules=(rules.live_rule(ids=('a',)),replace(rules.live_rule(ids=('b',)),id='other',name='Andere Regel'))
        await manager.async_process_inputs([sessions.source(),sessions.source('b')])
        await manager.async_action('trigger_test')
        plan=manager.session.output_plan[item.id]
        token=notifications.notify.popup_token(item.id,[manager.session.alarms['rule']])
        await manager.async_acknowledge_popup(item.id,token)
        self.assertEqual(manager.session.alarms['rule']['state'],'acknowledged')
        self.assertEqual(manager.session.alarms['other']['state'],'active')
        self.assertEqual(manager.session.manual.state,'active')

    async def test_full_length_custom_ack_text_still_returns_popup_feedback(self):
        manager,item=await self.manager(notifications.definition('overlay',acknowledged_value='q'*1024))
        token=notifications.notify.popup_token(item.id,list(manager.session.alarms.values()))
        await manager.async_acknowledge_popup(item.id,token)
        plan=manager.session.output_plan[item.id]
        self.assertEqual(plan['status'],'planned')
        self.assertEqual(plan['value'],'q'*1024)

    async def test_stale_popup_cannot_acknowledge_a_new_occurrence(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        token=notifications.notify.popup_token(item.id,list(manager.session.alarms.values()))
        await manager.async_process_inputs([sessions.source(status='not_matching')])
        await manager.async_action('reset')
        await manager.async_process_inputs([sessions.source()])
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_acknowledge_popup(item.id,token)
        self.assertEqual(manager.session.state,'active')
        self.assertEqual(manager.session.history[-1]['event'],'popup_acknowledge_rejected')
        self.assertIn('veraltet',manager.session.output_plan[item.id]['value'])

    async def test_new_source_in_same_rule_invalidates_old_popup(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        manager.rules=(rules.live_rule(ids=('a','b')),)
        await manager.async_process_inputs([sessions.source(),sessions.source('b','not_matching')])
        token=notifications.notify.popup_token(item.id,list(manager.session.alarms.values()))
        await manager.async_process_inputs([sessions.source(),sessions.source('b')])
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_acknowledge_popup(item.id,token)
        self.assertEqual(manager.session.state,'active')

    async def test_failed_storage_does_not_confirm_popup_acknowledgement(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        token=notifications.notify.popup_token(item.id,list(manager.session.alarms.values()))
        manager.store.fail=True
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_acknowledge_popup(item.id,token)
        self.assertEqual(manager.session.state,'active')
        self.assertNotEqual(manager.session.history[-1]['event'],'popup_acknowledged')

    async def test_input_arriving_while_ack_is_stored_is_not_discarded(self):
        manager,item=await self.manager(notifications.definition('overlay'))
        manager.rules=(rules.live_rule(ids=('a',)),replace(rules.live_rule(ids=('b',)),id='other',name='Andere Regel'))
        snapshot=[sessions.source(),sessions.source('b','not_matching')]
        manager.inputs=types.SimpleNamespace(snapshot=snapshot,stop=lambda:None)
        await manager.async_process_inputs(snapshot)
        manager.executor.start()
        await manager.async_drain()
        token=notifications.notify.popup_token(item.id,[manager.session.alarms['rule']])
        began=asyncio.Event()
        release=asyncio.Event()
        original_save=manager.store.async_save
        async def save(data):
            began.set()
            await release.wait()
            await original_save(data)
        manager.store.async_save=save
        ack=asyncio.create_task(manager.async_acknowledge_popup(item.id,token))
        await began.wait()
        manager.inputs.snapshot=[sessions.source(),sessions.source('b')]
        manager.inputs_changed()
        release.set()
        await ack
        await manager.async_drain()
        self.assertEqual(manager.session.alarms['rule']['state'],'acknowledged')
        self.assertEqual(manager.session.alarms['other']['state'],'active')
        self.assertIn('Quittierung übernommen',manager.hass.services.async_call.await_args.args[2]['content'])
