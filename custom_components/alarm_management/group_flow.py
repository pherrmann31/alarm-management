"""Native Home Assistant group and discovery options."""

from copy import deepcopy
from uuid import uuid4
import probatio
from homeassistant.helpers.selector import SelectSelector

from .groups import KEY, SMOKE_ALL, SMOKE_DEFAULT, HOUSE_ALL, HOUSE_DEFAULT, load_groups, move_source
from .discovery import candidates


class GroupFlow:
    def _discovery_targets(self, identity):
        from .rule_config import default_rule_id
        rule_id=default_rule_id(identity)
        return list(dict.fromkeys(self._bindings.get(rule_id,[])+self._groups['assignments'].get(rule_id,[])))

    def _target_selector(self):
        return SelectSelector({'options':[{'value':o.id,'label':o.name} for o in self._outputs]+[
            {'value':g['id'],'label':'Gruppe: '+g['name']} for g in self._groups['items'] if g['kind']!='input'],'multiple':True})

    def _set_auto_rule(self, identity, targets, alarm_type):
        from .rule_config import AlarmRule, default_rule_id
        if not isinstance(targets,list) or not targets:
            raise ValueError('Choose targets')
        output_ids={o.id for o in self._outputs}
        group_ids={g['id'] for g in self._groups['items'] if g['kind']!='input'}
        if not set(targets) <= output_ids | group_ids:
            raise ValueError('Unknown targets')
        rule_id=default_rule_id(identity)
        rule=AlarmRule(rule_id,'Feueralarm – alle Rauchmelder' if alarm_type=='fire' else 'Hausalarm – alle Taster',(identity,),'any',alarm_type,True)
        self._rules=[r for r in self._rules if r.id!=rule_id]+[rule]
        self._bindings[rule_id]=list(dict.fromkeys(t for t in targets if t in output_ids))
        self._groups['assignments'][rule_id]=list(dict.fromkeys(t for t in targets if t in group_ids))

    async def async_step_groups(self, user_input=None):
        self._ensure_sources()
        return self.async_show_menu(step_id='groups', menu_options=['group_add', 'group_edit', 'group_move', 'group_remove', 'group_test', 'discovery', 'house_discovery', 'init'])

    def _group_select(self, include_builtin=True):
        return SelectSelector({'options': [{'value': g['id'], 'label': g['name']} for g in self._groups['items']
            if g['id'] not in (SMOKE_ALL,HOUSE_ALL) and (include_builtin or g['id'] not in (SMOKE_DEFAULT,HOUSE_DEFAULT))], 'mode': 'dropdown'})

    async def async_step_group_add(self, user_input=None):
        if user_input is not None:
            self._group_selected = None
            self._group_kind = user_input['kind']
            return await self.async_step_group_details()
        return self.async_show_form(step_id='group_add', data_schema=probatio.Schema({
            probatio.Required('kind', default='input'): SelectSelector({'options': [
                {'value':'input','label':'Meldergruppe'}, {'value':'output','label':'Ausgabegruppe'},
                {'value':'notification','label':'Benachrichtigungsgruppe'}]})}))

    async def async_step_group_edit(self, user_input=None):
        if user_input is not None:
            self._group_selected = user_input['group_id']
            group = next(g for g in self._groups['items'] if g['id'] == self._group_selected)
            self._group_kind = group['kind']
            return await self.async_step_group_details()
        return self.async_show_form(step_id='group_edit', data_schema=probatio.Schema({probatio.Required('group_id'): self._group_select()}))

    async def async_step_group_details(self, user_input=None):
        group = next((g for g in self._groups['items'] if g['id'] == self._group_selected), None)
        choices = self._sources if self._group_kind == 'input' else [o for o in self._outputs if bool(o.notification) == (self._group_kind == 'notification')]
        values = deepcopy(group) if group else {'name':'', 'members':[], 'mode':'any'}
        errors = {}
        if user_input is not None:
            values.update(user_input)
            if not isinstance(values['name'], str) or not 1 <= len(values['name'].strip()) <= 80:
                errors['name'] = 'invalid_name'
            elif not set(values['members']) <= {item.id for item in choices}:
                errors['members'] = 'unknown_input'
            else:
                identity = group['id'] if group else uuid4().hex
                updated = {'id': identity, 'kind': self._group_kind, 'name': values['name'].strip(),
                           'members': list(dict.fromkeys(values['members'])), 'mode': values.get('mode','any')}
                if identity in (SMOKE_DEFAULT,HOUSE_DEFAULT):
                    updated['mode'] = 'any'
                self._groups['items'] = [g for g in self._groups['items'] if g['id'] != identity] + [updated]
                return self._finish(self._sources)
        schema = {probatio.Required('name', default=values['name']): str,
                  probatio.Optional('members', default=values['members']): SelectSelector({'options': [
                      {'value': item.id, 'label': item.name} for item in choices], 'multiple': True})}
        if self._group_kind == 'input' and self._group_selected not in (SMOKE_DEFAULT,HOUSE_DEFAULT):
            schema[probatio.Required('mode', default=values['mode'])] = SelectSelector({'options': [
                {'value':'any','label':'Mindestens ein Mitglied löst aus'}, {'value':'all','label':'Alle Mitglieder lösen gleichzeitig aus'}]})
        return self.async_show_form(step_id='group_details', data_schema=probatio.Schema(schema), errors=errors)

    async def async_step_group_move(self, user_input=None):
        if user_input is not None:
            self._groups = move_source(self._groups, user_input['source_id'], user_input['group_id'])
            return self._finish(self._sources)
        return self.async_show_form(step_id='group_move', data_schema=probatio.Schema({
            probatio.Required('source_id'): self._source_choices(),
            probatio.Required('group_id'): SelectSelector({'options': [{'value':g['id'],'label':g['name']}
                for g in self._groups['items'] if g['kind']=='input' and g['id'] not in (SMOKE_ALL,HOUSE_ALL)]})}))

    async def async_step_group_remove(self, user_input=None):
        errors = {}
        if user_input is not None:
            identity = user_input['group_id']
            used = any(identity in rule.input_ids for rule in self._rules) or any(identity in ids for ids in self._groups['assignments'].values())
            if used or identity in (SMOKE_ALL, SMOKE_DEFAULT,HOUSE_ALL,HOUSE_DEFAULT):
                errors['base'] = 'group_in_use'
            else:
                self._groups['items'] = [g for g in self._groups['items'] if g['id'] != identity]
                return self._finish(self._sources)
        return self.async_show_form(step_id='group_remove', data_schema=probatio.Schema({probatio.Required('group_id'):self._group_select(False)}), errors=errors)

    async def async_step_discovery(self, user_input=None):
        found = [item for item in candidates(self.hass) if item['device_class'] == 'smoke' and not item['disabled']]
        errors={}
        if user_input is not None:
            try:
                if user_input['auto_smoke']:
                    self._set_auto_rule(SMOKE_ALL,user_input.get('targets',[]),'fire')
                self._groups['auto_smoke'] = user_input['auto_smoke']
                return self._finish(self._sources)
            except ValueError:
                errors['base']='choose_discovery_targets'
        return self.async_show_form(step_id='discovery', data_schema=probatio.Schema({
            probatio.Required('auto_smoke', default=self._groups['auto_smoke']): bool,
            probatio.Optional('targets',default=self._discovery_targets(SMOKE_ALL)):self._target_selector()}),errors=errors,
            description_placeholders={'devices':'\n'.join('• '+item['name']+' ('+item['entity_id']+')' for item in found) or 'Keine passenden Melder gefunden.'})

    async def async_step_house_discovery(self, user_input=None):
        errors={}
        if user_input is not None:
            proposed=deepcopy(self._groups)
            proposed.update({k:v for k,v in user_input.items() if k!='targets'})
            try:
                proposed=load_groups({KEY:proposed})
                if proposed['auto_house']:
                    self._set_auto_rule(HOUSE_ALL,user_input.get('targets',[]),'house')
                proposed['assignments']=deepcopy(self._groups['assignments'])
                self._groups=proposed
                return self._finish(self._sources)
            except ValueError:
                errors['base']='invalid_house_discovery'
        return self.async_show_form(step_id='house_discovery',errors=errors,data_schema=probatio.Schema({
            probatio.Required('auto_house',default=self._groups['auto_house']):bool,
            probatio.Optional('house_pattern',default=self._groups['house_pattern']):str,
            probatio.Optional('house_label',default=self._groups['house_label']):str,
            probatio.Required('house_trigger',default=self._groups['house_trigger']):str,
            probatio.Optional('targets',default=self._discovery_targets(HOUSE_ALL)):self._target_selector()}))

    async def async_step_group_test(self, user_input=None):
        result='Wähle eine Meldergruppe. Die Vorschau berechnet die Verteilung ohne Geräteaktionen oder Nachrichtenversand.'
        if user_input is not None:
            from .session import AlarmSession, reconcile
            from .output_engine import plan_outputs
            from datetime import datetime, timezone
            manager=getattr(self.config_entry,'runtime_data',None)
            if manager is None:
                return self.async_abort(reason='invalid_configuration')
            group=next(g for g in self._groups['items'] if g['id']==user_input['group_id'] and g['kind']=='input')
            members=self._groups['smoke_ids'] if group['id']==SMOKE_ALL else self._groups['house_ids'] if group['id']==HOUSE_ALL else group['members']
            snapshot=deepcopy(manager.inputs.snapshot)
            for item in snapshot:
                item['status']='matching' if item['id'] in members and item['enabled'] else 'not_matching'
            evaluated=manager.evaluate(snapshot)
            session=reconcile(AlarmSession(),evaluated,datetime.now(timezone.utc).isoformat())
            plans=plan_outputs(manager.outputs,manager.output_bindings,manager.rules,session)
            names=[rule['rule_name'] for rule in evaluated if rule['status']=='matching']
            targets=[plan['name']+': '+str(plan['value']) for plan in plans.values() if plan['phase']=='alarm' and plan['status']!='disabled']
            result='Vorschau: Alle aktivierten Mitglieder dieser Gruppe lösen aus. Andere Eingänge sind in dieser Vorschau inaktiv.\n\nRegeln: '+(', '.join(names) or 'Keine')+'\n\nAusgaben:\n'+('\n'.join('• '+item for item in targets) or 'Keine Zuordnung')+'\n\nEs wurde nichts geschaltet oder versendet. Dies prüft keine Erreichbarkeit der Geräte.'
        return self.async_show_form(step_id='group_test',description_placeholders={'result':result},data_schema=probatio.Schema({
            probatio.Required('group_id'):SelectSelector({'options':[{'value':g['id'],'label':g['name']} for g in self._groups['items'] if g['kind']=='input']})}))
