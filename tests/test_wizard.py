"""End-to-end staged setup, single save, conflict and cancellation contracts."""
from copy import deepcopy
import types
import unittest
from unittest.mock import AsyncMock, Mock

import test_inputs as inputs
import test_outputs as outputs
import test_rules as rules
import test_form_defaults as defaults


class WizardTests(unittest.IsolatedAsyncioTestCase):
    def flow(self):
        flow=outputs.OutputFlowTests().flow()
        flow.hass.config_entries=types.SimpleNamespace(
            async_update_entry=Mock(side_effect=lambda entry,**kw:setattr(entry,'options',deepcopy(kw['options']))),
            async_reload=AsyncMock(return_value=True))
        return flow

    async def prepared(self):
        flow=self.flow()
        result=await flow.async_step_wizard()
        self.assertEqual(result['step_id'],'add')
        await flow.async_step_add({'entity_id':'input_boolean.test_alarm'})
        result=await flow.async_step_add_details(inputs.payload())
        self.assertEqual(result['step_id'],'wizard_inputs')
        result=await flow.async_step_wizard_next()
        self.assertEqual(result['step_id'],'output_add')
        await flow.async_step_output_add({'kind':'switch','entity_id':'input_boolean.siren'})
        result=await flow.async_step_output_details(outputs.values())
        self.assertEqual(result['step_id'],'wizard_outputs')
        result=await flow.async_step_wizard_next()
        self.assertEqual(result['step_id'],'rule_add')
        values=defaults.frontend_initial_data(result['data_schema'])
        self.assertEqual(values['when']['input_ids'],[flow._sources[0].id])
        self.assertEqual(values['then']['output_ids'],[flow._outputs[0].id])
        values['name']='Hausalarm'
        result=await flow.async_step_rule_add(values)
        self.assertEqual(result['step_id'],'wizard_rules')
        result=await flow.async_step_wizard_next()
        self.assertEqual(result['step_id'],'notification_add')
        result=await flow.async_step_notification_add({'kind':'notification'})
        values=defaults.frontend_initial_data(result['data_schema'])
        values['delivery']['routes']=['mobile_app:notify.mobile_app_phone']
        result=await flow.async_step_notification_details(values)
        self.assertEqual(result['step_id'],'wizard_notifications')
        self.assertEqual(flow.hass.entry.options,{})
        flow.hass.config_entries.async_update_entry.assert_not_called()
        flow.hass.config_entries.async_reload.assert_not_awaited()
        return flow

    async def test_complete_flow_saves_once_and_returns_overview_with_routing(self):
        flow=await self.prepared()
        result=await flow.async_step_wizard_next()
        self.assertEqual(result['step_id'],'wizard_routes')
        values=defaults.frontend_initial_data(result['data_schema'])
        self.assertEqual(values['rule_ids'],[flow._rules[0].id])
        result=await flow.async_step_wizard_routes(values)
        self.assertEqual(result['step_id'],'wizard_review')
        expected={o.id for o in flow._outputs}
        rule_id=flow._rules[0].id
        result=await flow.async_step_wizard_review({'action':'save','confirm':True})
        self.assertEqual(result['step_id'],'init')
        self.assertFalse(flow._wizard_active)
        flow.hass.config_entries.async_update_entry.assert_called_once()
        flow.hass.config_entries.async_reload.assert_awaited_once_with('integration')
        self.assertEqual(set(flow.hass.entry.options['output_config']['bindings'][rule_id]),expected)
        self.assertEqual(len(flow._sources),1)
        self.assertEqual(len(flow._rules),1)

    async def test_cancel_discards_every_staged_definition(self):
        flow=await self.prepared()
        result=await flow.async_step_wizard_cancel()
        self.assertEqual(result['step_id'],'init')
        self.assertEqual(flow.hass.entry.options,{})
        self.assertEqual(flow._sources,[])
        self.assertEqual(flow._outputs,[])
        flow.hass.config_entries.async_update_entry.assert_not_called()

    async def test_conflict_prevents_overwriting_automatic_enrollment(self):
        flow=await self.prepared()
        flow.hass.entry.options={'input_config':{'version':1,'inputs':[]}}
        result=await flow.async_step_wizard_review({'confirm':True})
        self.assertEqual(result['reason'],'configuration_changed')
        flow.hass.config_entries.async_update_entry.assert_not_called()

    async def test_review_requires_confirmation(self):
        flow=await self.prepared()
        result=await flow.async_step_wizard_review({'confirm':False})
        self.assertEqual(result['errors'],{'base':'confirmation_required'})
        flow.hass.config_entries.async_update_entry.assert_not_called()

    async def test_previous_step_keeps_staged_data(self):
        flow=await self.prepared()
        result=await flow.async_step_wizard_previous()
        self.assertEqual(result['step_id'],'wizard_rules')
        self.assertFalse(flow._notification_mode)
        self.assertEqual(len(flow._outputs),2)
        self.assertEqual(flow.hass.entry.options,{})

    async def test_reload_failure_preserves_saved_configuration_and_returns_overview(self):
        flow=await self.prepared()
        flow.hass.config_entries.async_reload.return_value=False
        result=await flow.async_step_wizard_review({'confirm':True})
        self.assertEqual(result['step_id'],'init')
        self.assertIn('nicht geladen',result['description_placeholders']['notice'])
        self.assertTrue(flow.hass.entry.options['input_config']['inputs'])

    async def test_explicit_empty_notification_selection_survives_backtracking(self):
        flow=await self.prepared()
        await flow.async_step_wizard_next()
        await flow.async_step_wizard_routes({'rule_ids':[]})
        await flow.async_step_wizard_review({'action':'back'})
        result=await flow.async_step_wizard_next()
        self.assertEqual(defaults.frontend_initial_data(result['data_schema'])['rule_ids'],[])
        self.assertNotIn(flow._outputs[-1].id,flow._bindings.get(flow._rules[0].id,[]))

    async def test_existing_definitions_are_preserved(self):
        flow=self.flow()
        source=inputs.model.build_source(inputs.payload())
        flow.hass.entry.options=inputs.options_for([source])
        await flow.async_step_init()
        baseline=deepcopy(flow.hass.entry.options)
        await flow.async_step_wizard()
        await flow.async_step_wizard_cancel()
        self.assertEqual(flow.hass.entry.options,baseline)
        self.assertEqual(flow._sources[0].id,source.id)
