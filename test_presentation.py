"""Native HA presentation boundaries with explicit schema/flow doubles."""
from copy import deepcopy
import importlib
import types
import unittest

import test_inputs as inputs
import test_outputs as outputs
import test_platforms as platforms
import test_rules as rules

ui = importlib.import_module(f'{inputs.NAME}.presentation')


def schema_fields(schema):
    return {key.key: value for key, value in schema.schema.items()}


def grouped_output(values):
    return {**{key:value for key,value in values.items() if key not in set().union(*ui.OUTPUT_SECTIONS.values())},
            **{group:{key:values[key] for key in fields if key in values} for group,fields in ui.OUTPUT_SECTIONS.items()}}


class PresentationTests(unittest.IsolatedAsyncioTestCase):
    def test_flatten_roundtrip_keeps_models_flat(self):
        value = outputs.values('short_text')
        grouped = grouped_output(value)
        snapshot = deepcopy(grouped)
        self.assertEqual(ui.flatten_sections(grouped, ui.OUTPUT_SECTIONS), value)
        self.assertEqual(grouped, snapshot)

    def test_rejects_malformed_or_ambiguous_sections(self):
        for value in ({'alarm':[]}, {'alarm':{'entity_id':'switch.other'}},
                      {'alarm':{'alarm_value':'one'}, 'alarm_value':'two'}):
            with self.subTest(value=value), self.assertRaises(inputs.model.InputValidationError):
                ui.flatten_sections(value, ui.OUTPUT_SECTIONS)

    def test_names_cannot_inject_markdown_or_newlines(self):
        self.assertEqual(ui.markdown_text('**Test**\n[link](target)'), r'\*\*Test\*\* \[link\](target)')

    def test_duplicate_names_keep_entity_disambiguation(self):
        items = [inputs.model.build_source(inputs.payload(name='Flur', entity_id=f'input_boolean.test_{i}')) for i in range(2)]
        labels = ui.selection_labels(items)
        for item in items:
            self.assertIn(item.entity_id, labels[item.id])

    async def test_grouped_rule_saves_same_model_and_binding(self):
        flow, sources = rules.RuleFlowTests().flow(empty=True)
        await flow.async_step_init()
        output = outputs.config.build_output(outputs.values('long_text'))
        flow._outputs.append(output)
        data = {'name':'Wenn Bad, dann Text', 'enabled':True,
                'when':{'input_ids':[sources[0].id], 'mode':'all'},
                'then':{'alarm_type':'fire', 'output_ids':[output.id]}}
        await flow.async_step_rule_add(data)
        result = await flow.async_step_rule_finish()
        saved = rules.model.load_rules(result['data'], sources)[0]
        self.assertEqual((saved.name, saved.mode, saved.alarm_type), (data['name'], 'all', 'fire'))
        self.assertEqual(result['data']['output_config']['bindings'][saved.id], [output.id])
        self.assertNotIn('when', saved.to_dict())

    async def test_grouped_output_edit_preserves_id_and_values(self):
        flow = outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        await flow.async_step_output_add({'kind':'short_text'})
        await flow.async_step_output_details(grouped_output(outputs.values('short_text')))
        original = flow._outputs[0]
        await flow.async_step_output_edit({'output_id':original.id})
        result = await flow.async_step_output_edit_details(grouped_output(outputs.values('short_text', name='Display', idle_value='Alles gut')))
        saved = outputs.config.load_output_config(result['data'], [])[0][0]
        self.assertEqual((saved.id,saved.name,saved.idle_value), (original.id,'Display','Alles gut'))
        self.assertNotIn('idle', saved.to_dict())

    async def test_error_opens_collapsed_section(self):
        flow = outputs.OutputFlowTests().flow()
        await flow.async_step_init()
        await flow.async_step_output_add({'kind':'short_text'})
        result = await flow.async_step_output_details(grouped_output(outputs.values('short_text', idle_value='x'*15)))
        self.assertEqual(result['errors'], {'idle':'short_text_too_long'})
        self.assertFalse(schema_fields(result['data_schema'])['idle'].options['collapsed'])

    async def test_short_text_format_only_where_applicable(self):
        flow = outputs.OutputFlowTests().flow()
        for kind in outputs.config.KINDS:
            fields = schema_fields(flow._output_schema(outputs.values(kind)))
            self.assertEqual('format' in fields, kind == 'short_text')
            self.assertTrue(fields['idle'].options['collapsed'])
            self.assertFalse(fields['alarm'].options['collapsed'])

    async def test_optional_text_target_uses_clearable_suggestion(self):
        flow = outputs.OutputFlowTests().flow()
        schema = flow._output_schema(outputs.values('short_text', entity_id='input_text.target'))
        marker = next(key for key in schema.schema if key.key=='entity_id')
        self.assertIsNone(marker.default)
        self.assertEqual(marker.description, {'suggested_value':'input_text.target'})

    async def test_overviews_navigate_without_save_or_reload(self):
        flow, _ = rules.RuleFlowTests().flow()
        await flow.async_step_init()
        original = deepcopy(flow.hass.entry.options)
        for method, target in ((flow.async_step_status,'init'), (flow.async_step_overview,'inputs'),
                               (flow.async_step_rule_overview,'rules'), (flow.async_step_output_overview,'outputs')):
            result = await method()
            self.assertFalse(result['last_step'])
            result = await method({})
            self.assertEqual((result['type'],result['step_id']), ('menu',target))
        self.assertEqual(flow.hass.entry.options, original)

    async def test_status_snapshot_reports_latched_alarm_and_errors(self):
        flow, _ = rules.RuleFlowTests().flow()
        manager = await platforms.PlatformTests().manager()
        await manager.async_process_inputs([platforms.sessions.source()])
        manager.inputs.snapshot = [{'status':'unavailable'}]
        manager.delivery_failures.add('failed-output')
        flow.hass.entry.runtime_data = manager
        result = await flow.async_step_status()
        summary = result['description_placeholders']
        self.assertEqual((summary['state'],summary['alarms'],summary['source_errors'],summary['output_errors']), ('Alarm aktiv','1','1','1'))
        self.assertIn('Quelle a',summary['sources'])

    async def test_categories_keep_primary_entities_and_stable_ids(self):
        manager = await platforms.PlatformTests().manager()
        entry = types.SimpleNamespace(entry_id='integration',title='Alarm Management',runtime_data=manager)
        sensors = platforms.sensor
        for entity in (sensors.InputStatusSensor(entry),sensors.RuleStatusSensor(entry),sensors.OutputLogSensor(entry),sensors.AlarmDetailSensor(entry,'journal')):
            self.assertEqual(entity._attr_entity_category,'diagnostic')
        for entity in (sensors.AlarmStatusSensor(entry),sensors.OutputSummarySensor(entry),sensors.AlarmDetailSensor(entry,'triggered_by')):
            self.assertNotEqual(getattr(entity,'_attr_entity_category',None),'diagnostic')
        output = outputs.config.build_output(outputs.values('long_text'))
        entity = sensors.OutputValueSensor(entry,output)
        self.assertEqual(entity._attr_unique_id,f'integration_output_{output.id}')
        self.assertEqual(entity._attr_name,f'Langtext · {output.name}')
        self.assertEqual(entity.icon,'mdi:text-long')
        self.assertEqual(sensors.AlarmStatusSensor(entry).icon,'mdi:shield-check-outline')

