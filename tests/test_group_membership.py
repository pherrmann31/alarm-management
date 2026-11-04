"""Creating and clearing group membership through the native checkbox form."""
import unittest
import test_inputs as inputs
import test_outputs as outputs
import test_form_defaults as defaults
import test_groups as groups


class MembershipTests(unittest.IsolatedAsyncioTestCase):
    async def fixture(self):
        flow=outputs.OutputFlowTests().flow()
        source=inputs.model.build_source(inputs.payload())
        flow.hass.entry.options=inputs.options_for([source])
        await flow.async_step_init()
        return flow,source

    async def test_create_group_with_members_immediately(self):
        flow,source=await self.fixture()
        form=await flow.async_step_group_add({'kind':'input'})
        selector=next(value for key,value in form['data_schema'].schema.items() if key.key=='members')
        self.assertEqual(selector.config['mode'],'list')
        self.assertTrue(selector.config['multiple'])
        self.assertEqual(selector.config['options'][0]['value'],source.id)
        result=await flow.async_step_group_details({'name':'EG','members':[source.id],'mode':'any'})
        config=groups.groups.load_groups(result['data'])
        self.assertEqual(config['items'][-1]['members'],[source.id])

    async def test_edit_checks_members_and_allows_clearing_without_touching_other_groups(self):
        flow,source=await self.fixture()
        flow._groups['items'] += [dict(id='d'*32,name='EG',kind='input',members=[source.id],mode='any'),
                                  dict(id='e'*32,name='Haus',kind='input',members=[source.id],mode='any')]
        form=await flow.async_step_group_edit({'group_id':'d'*32})
        self.assertEqual(defaults.frontend_initial_data(form['data_schema'])['members'],[source.id])
        result=await flow.async_step_group_details({'name':'EG','members':[],'mode':'any'})
        items={g['id']:g for g in groups.groups.load_groups(result['data'])['items']}
        self.assertEqual(items['d'*32]['members'],[])
        self.assertEqual(items['e'*32]['members'],[source.id])
        self.assertNotIn('group_move',(await flow.async_step_groups())['menu_options'])

    async def test_omitted_empty_checkbox_value_clears_members(self):
        flow,source=await self.fixture()
        flow._groups['items'].append(dict(id='d'*32,name='EG',kind='input',members=[source.id],mode='any'))
        await flow.async_step_group_edit({'group_id':'d'*32})
        result=await flow.async_step_group_details({'name':'EG','mode':'any'})
        group=next(g for g in result['data']['groups']['items'] if g['id']=='d'*32)
        self.assertEqual(group['members'],[])
