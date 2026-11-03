"""Notification rendering and occurrence identities, without external side effects."""
from hashlib import sha256
import html
import json
from string import Formatter


def alarm_context(alarms, phase):
    def unique(values):
        return ', '.join(dict.fromkeys(values))
    sources = [source for alarm in alarms for source in alarm['sources']]
    return {'regel':unique(item['rule_name'] for item in alarms), 'quelle':unique(item['name'] for item in sources),
            'bereich':unique(item['area_name'] or 'Ohne Bereich' for item in sources),
            'alarmtyp':unique({'house':'Hausalarm','fire':'Feuer','intrusion':'Einbruch'}[item['alarm_type']] for item in alarms),
            'status':{'alarm':'aktiv','acknowledged':'quittiert','idle':'Ruhezustand'}[phase]}


def delivery_id(output_id, route):
    return output_id + '_notify_' + sha256(route.encode()).hexdigest()[:32]


def request(output, plan, session, route):
    rules = {item['id'] for item in plan['rules']}
    alarms = [record for key,record in session.alarms.items() if key in rules]
    title = Formatter().vformat(output.notification['title'], (), alarm_context(alarms,plan['phase']))
    body = plan['value'] or ''
    if len(title)>80 or len(body)>1024:
        raise ValueError('Nachricht überschreitet 80 Zeichen Titel oder 1024 Zeichen Text')
    if route.startswith('mobile_app:') and (body.startswith('command_') or body in ('clear_notification','request_location_update','update_widgets')):
        raise ValueError('App-Steuerbefehle sind keine Alarmnachrichten')
    routing = [output.notification['devices'],output.notification['priority']] if route.startswith('pushover:') else None
    reset = next((item['time'] for item in reversed(session.history) if item['event']=='reset'),None) if plan['phase']=='idle' else None
    identity = [route, routing, title, body, plan['phase'], reset,
                sorted((item['rule_id'],item['triggered_at'],item['state'],sorted(source['id'] for source in item['sources'])) for item in alarms)]
    fingerprint = 'notification:' + sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if route.startswith('browser:'):
        return fingerprint, 'browser_mod', 'popup', {'browser_id':[route.split(':',1)[1]], 'title':title,
                'content':html.escape(body).replace('\n','<br>'), 'dismissable':True}, None
    if route.startswith('entity:'):
        return fingerprint, 'notify', 'send_message', {'title':title,'message':body}, {'entity_id':route.split(':',1)[1]}
    _,address = route.split(':',1)
    data = {'title':title,'message':body}
    if route.startswith('pushover:'):
        data['data']={'priority':output.notification['priority']}
        if output.notification['devices']:
            data['target']=output.notification['devices'].split(',')
    return fingerprint, 'notify', address.split('.',1)[1], data, None
