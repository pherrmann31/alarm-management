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


def popup_token(output_id, alarms):
    """Bind acknowledgement to exactly the alarm occurrences shown in a popup."""
    identity=[output_id,sorted((item['rule_id'],item['triggered_at'],sorted(source['id'] for source in item['sources'])) for item in alarms)]
    return sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()


def reset_error_message(blocked):
    lines=['Reset nicht möglich.']
    for rule in blocked[:3]:
        if rule.get('status')=='matching':
            names=', '.join(source['name'][:60] for source in rule.get('sources',[])[:2])
            reason='weiterhin ausgelöst'+(': '+names if names else '')
        else:
            reason='Eingangsstatus nicht eindeutig; Verbindung und Eingang prüfen'
        lines.append(rule['name'][:80]+': '+reason+'.')
    if len(blocked)>3:
        lines.append(f'Weitere {len(blocked)-3} Regeln betroffen; Details im Alarmverlauf.')
    return '\n'.join(lines)


def notification_event(session, output_id, bindings, alarms):
    """Unrelated alarms must not discard an already stored feedback message."""
    assigned={rule_id for rule_id,outputs in bindings.items() if output_id in outputs}
    for event in reversed(session.history):
        affected={item.get('rule_id',item['id']) for item in event['sources']}
        if event['event']=='reset_blocked' and assigned & affected:
            return event
        if event['event'] in ('popup_acknowledged','popup_acknowledge_rejected'):
            feedback=next((item for item in event['sources'] if item.get('notification_id')==output_id),None)
            if feedback:
                return event if feedback.get('token')==popup_token(output_id,alarms) else None
        if event['event']=='reset' or assigned & affected:
            return None
    return None


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
    event=notification_event(session,output.id,{rule_id:[output.id] for rule_id in rules},alarms)
    event_key=(event['event'],event['time']) if event else None
    identity = [route, routing, title, body, plan['phase'], reset, event_key,
                sorted((item['rule_id'],item['triggered_at'],item['state'],sorted(source['id'] for source in item['sources'])) for item in alarms)]
    fingerprint = 'notification:' + sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if route.startswith('browser:'):
        data={'browser_id':[route.split(':',1)[1]], 'title':title,
              'content':html.escape(body).replace('\n','<br>'), 'dismissable':True,
              'left_button':'Schließen', 'left_button_close':True}
        if plan['phase']=='alarm' and any(item['state']=='active' for item in alarms) and not (event and event['event']=='popup_acknowledge_rejected'):
            data.update(right_button='Quittieren',right_button_close=False,
                        right_button_action={'service':'alarm_management.acknowledge_popup',
                            'data':{'output_id':output.id,'token':popup_token(output.id,alarms)}})
        return fingerprint, 'browser_mod', 'popup', data, None
    if route.startswith('entity:'):
        return fingerprint, 'notify', 'send_message', {'title':title,'message':body}, {'entity_id':route.split(':',1)[1]}
    _,address = route.split(':',1)
    data = {'title':title,'message':body}
    if route.startswith('pushover:'):
        data['data']={'priority':output.notification['priority']}
        if output.notification['devices']:
            data['target']=output.notification['devices'].split(',')
    return fingerprint, 'notify', address.split('.',1)[1], data, None
