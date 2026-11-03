"""HA frontend default precedence, including unopened sections.

Contract: compute-initial-ha-form-data.ts uses a section's explicit default
before considering child defaults. A default={} therefore hides child values.
The previous flow doubles did not simulate this browser-side initialization.
"""
from copy import deepcopy
import unittest

import test_inputs as inputs
import test_outputs as outputs
import test_rules as rules


def frontend_initial_data(schema):
    """Emulate the relevant documented frontend precedence, not server validation."""
    data={}
    for marker,validator in schema.schema.items():
        if 'suggested_value' in marker.description:
            data[marker.key]=deepcopy(marker.description['suggested_value'])
        elif marker.default is not None:
            data[marker.key]=deepcopy(marker.default)
        elif isinstance(validator,inputs.FakeSection):
            data[marker.key]=frontend_initial_data(validator.schema)
    return data


class FormDefaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_saves_without_opening_optional_pushover_section(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        form=await flow.async_step_output_add({'kind':'notification'})
        payload=frontend_initial_data(form['data_schema'])
        self.assertEqual(payload['pushover']['priority'],'0')
        self.assertEqual(payload['delivery']['title'],'Alarm Management')
        self.assertEqual(payload['acknowledged']['acknowledged_value'],'')
        payload['delivery']['routes']=['mobile_app:notify.mobile_app_phone']
        payload['alarm']['alarm_value']='Testalarm'
        result=await flow.async_step_output_details(payload)
        self.assertEqual(result['step_id'],'output_after_add')
        self.assertEqual(flow._outputs[0].notification['priority'],0)

    async def test_overlay_keeps_title_and_default_message(self):
        flow=outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        form=await flow.async_step_output_add({'kind':'overlay'})
        payload=frontend_initial_data(form['data_schema'])
        self.assertEqual(payload['delivery']['title'],'Alarm Management')
        self.assertIn('{quelle}',payload['alarm']['alarm_value'])
        self.assertNotIn('pushover',payload)

    async def test_rule_edit_preserves_existing_nested_values(self):
        flow,sources=rules.RuleFlowTests().flow()
        await flow.async_step_init()
        original=flow._rules[0]
        values={**original.to_dict(),'mode':'all','alarm_type':'intrusion','input_ids':[source.id for source in sources]}
        schema=flow._rule_schema(values)
        payload=frontend_initial_data(schema)
        self.assertEqual(payload['when']['input_ids'],values['input_ids'])
        self.assertEqual(payload['when']['mode'],'all')
        self.assertEqual(payload['then']['alarm_type'],'intrusion')

    async def test_closed_format_and_phase_sections_preserve_saved_settings(self):
        flow=outputs.OutputFlowTests().flow()
        values=outputs.values('short_text',encoding='ascii',alarm_value='ALARM',acknowledged_value='ACK',idle_value='READY')
        schema=flow._output_schema(values)
        payload=frontend_initial_data(schema)
        self.assertEqual(payload['format']['encoding'],'ascii')
        self.assertEqual(payload['acknowledged']['acknowledged_value'],'ACK')
        self.assertEqual(payload['idle']['idle_value'],'READY')
        for marker,validator in schema.schema.items():
            if isinstance(validator,inputs.FakeSection):
                self.assertIsNone(marker.default,'An empty outer default masks defaults inside the section')
