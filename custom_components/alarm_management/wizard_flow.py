"""Staged setup: save once, reload once, return to the options overview."""
from copy import deepcopy
import logging
import probatio
from homeassistant.helpers.selector import SelectSelector
from .const import MAX_INPUTS, MAX_OUTPUTS, MAX_RULES
from .presentation import markdown_text

_LOGGER=logging.getLogger(__name__)


class WizardFlow:
    def _wizard_menu(self):
        stage=self._wizard_stage
        add={'inputs':'add','outputs':'output_add','rules':'rule_add','notifications':'notification_add'}[stage]
        allowed={'inputs':len(self._sources)<MAX_INPUTS,'outputs':len(self._outputs)<MAX_OUTPUTS,
                 'rules':len(self._rules)<MAX_RULES,'notifications':len(self._outputs)<MAX_OUTPUTS}[stage]
        return self.async_show_menu(step_id='wizard_'+stage,menu_options=([add] if allowed else [])+
            ['wizard_next','wizard_previous','wizard_cancel'],description_placeholders={
                'inputs':str(len(self._sources)),'outputs':str(sum(not o.notification for o in self._outputs)),
                'rules':str(len(self._rules)),'notifications':str(sum(bool(o.notification) for o in self._outputs))})

    async def async_step_wizard(self,user_input=None):
        self._ensure_sources()
        self._wizard_active=True
        self._wizard_stage='inputs'
        self._wizard_original_ids={'inputs':{s.id for s in self._sources},'outputs':{o.id for o in self._outputs},'rules':{r.id for r in self._rules}}
        self._wizard_selected_rules=[]
        self._wizard_routes_set=False
        self._wizard_visited={'inputs'}
        self._notification_mode=False
        if len(self._sources)<MAX_INPUTS:
            return await self.async_step_add()
        return self._wizard_menu()

    async def async_step_wizard_next(self,user_input=None):
        if not self._wizard_active:
            return await self.async_step_init()
        stages=['inputs','outputs','rules','notifications','review']
        self._wizard_stage=stages[stages.index(self._wizard_stage)+1]
        return await self._wizard_open_stage()

    async def async_step_wizard_previous(self,user_input=None):
        if not self._wizard_active:
            return await self.async_step_init()
        stages=['inputs','outputs','rules','notifications','review']
        self._wizard_stage=stages[max(0,stages.index(self._wizard_stage)-1)]
        return await self._wizard_open_stage()

    async def _wizard_open_stage(self):
        self._notification_mode=self._wizard_stage=='notifications'
        if self._wizard_stage=='review':
            return await self.async_step_wizard_routes()
        if self._wizard_stage not in self._wizard_visited:
            self._wizard_visited.add(self._wizard_stage)
            if self._wizard_stage=='outputs' and len(self._outputs)<MAX_OUTPUTS:
                return await self.async_step_output_add()
            if self._wizard_stage=='rules' and len(self._rules)<MAX_RULES:
                return await self.async_step_rule_add()
            if self._wizard_stage=='notifications' and len(self._outputs)<MAX_OUTPUTS:
                return await self.async_step_notification_add()
        return self._wizard_menu()

    async def async_step_wizard_inputs(self,user_input=None):
        self._wizard_stage='inputs'
        return self._wizard_menu()

    async def async_step_wizard_outputs(self,user_input=None):
        self._wizard_stage='outputs';self._notification_mode=False
        return self._wizard_menu()

    async def async_step_wizard_rules(self,user_input=None):
        self._wizard_stage='rules'
        return self._wizard_menu()

    async def async_step_wizard_notifications(self,user_input=None):
        self._wizard_stage='notifications';self._notification_mode=True
        return self._wizard_menu()

    async def async_step_wizard_routes(self,user_input=None):
        if not self._wizard_active:
            return await self.async_step_init()
        new_notifications=[o for o in self._outputs if o.notification and o.id not in self._wizard_original_ids['outputs']]
        if not new_notifications:
            return await self.async_step_wizard_review()
        if user_input is not None:
            selected=user_input.get('rule_ids',[])
            if not isinstance(selected,list) or not set(selected)<={r.id for r in self._rules}:
                return self.async_abort(reason='invalid_configuration')
            self._wizard_selected_rules=list(selected)
            self._wizard_routes_set=True
            for rule in self._rules:
                assigned=[identity for identity in self._bindings.get(rule.id,[]) if identity not in {o.id for o in new_notifications}]
                if rule.id in selected:
                    assigned.extend(o.id for o in new_notifications)
                self._bindings[rule.id]=list(dict.fromkeys(assigned))
            return await self.async_step_wizard_review()
        defaults=self._wizard_selected_rules if self._wizard_routes_set else [r.id for r in self._rules if r.id not in self._wizard_original_ids['rules']]
        return self.async_show_form(step_id='wizard_routes',last_step=False,
            description_placeholders={'notifications':', '.join(markdown_text(o.name) for o in new_notifications)},
            data_schema=probatio.Schema({probatio.Optional('rule_ids',default=defaults):SelectSelector({
                'options':[{'value':r.id,'label':r.name} for r in self._rules],'multiple':True})}))

    def _wizard_summary(self):
        names={o.id:o.name for o in self._outputs}
        groups={g['id']:g['name'] for g in self._groups['items']}
        lines=[]
        for rule in self._rules:
            if rule.id not in self._wizard_original_ids['rules'] or rule.id in self._wizard_selected_rules:
                targets=[names[x] for x in self._bindings.get(rule.id,[]) if x in names]
                targets.extend(groups[x] for x in self._groups['assignments'].get(rule.id,[]) if x in groups)
                lines.append(markdown_text(rule.name)+' → '+(', '.join(markdown_text(x) for x in targets) or 'Keine Alarmziele zugeordnet'))
        new_sources=[s.name for s in self._sources if s.id not in self._wizard_original_ids['inputs']]
        new_outputs=[o.name for o in self._outputs if o.id not in self._wizard_original_ids['outputs']]
        return {'inputs':', '.join(markdown_text(x) for x in new_sources) or '—',
                'outputs':', '.join(markdown_text(x) for x in new_outputs) or '—',
                'routing':'\n\n'.join(lines) or 'Keine neuen oder zugeordneten Regeln.'}

    async def async_step_wizard_review(self,user_input=None):
        if not self._wizard_active:
            return await self.async_step_init()
        errors={}
        if user_input is not None:
            if user_input.get('action')=='back':
                self._wizard_stage='notifications'
                return await self._wizard_open_stage()
            if user_input.get('action')=='cancel':
                return await self.async_step_wizard_cancel()
            if user_input.get('confirm') is not True:
                errors['base']='confirmation_required'
            else:
                result=self._configuration_result(self._sources)
                if result['type']!='create_entry':
                    return result
                from .configuration import prepare_configuration
                options,*_=prepare_configuration(result['data'])
                changed=options!=dict(self.config_entry.options)
                if changed:
                    self.hass.config_entries.async_update_entry(self.config_entry,options=deepcopy(options))
                    # Persist first, then reload. A failed reload must not resend the save.
                    try:
                        loaded=await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                        self._wizard_notice='Einrichtung gespeichert.' if loaded else 'Einrichtung gespeichert. Integration konnte nicht geladen werden; HA-Protokoll prüfen.'
                    except Exception:
                        _LOGGER.exception('Setup wizard saved options, but integration reload failed')
                        self._wizard_notice='Einrichtung gespeichert. Neuladen fehlgeschlagen; HA-Protokoll prüfen.'
                else:
                    self._wizard_notice='Keine Änderungen zu speichern.'
                self._wizard_active=False
                self._notification_mode=False
                self._sources=None
                return await self.async_step_init()
        return self.async_show_form(step_id='wizard_review',last_step=False,errors=errors,
            description_placeholders=self._wizard_summary(),data_schema=probatio.Schema({
                probatio.Required('action',default='save'):SelectSelector({'options':[
                    {'value':'save','label':'Speichern & zur Übersicht'}, {'value':'back','label':'Zurück zu Benachrichtigungen'},
                    {'value':'cancel','label':'Änderungen verwerfen'}]}),
                probatio.Required('confirm',default=False):bool}))

    async def async_step_wizard_cancel(self,user_input=None):
        self._wizard_active=False
        self._notification_mode=False
        self._sources=None
        return await self.async_step_init()
