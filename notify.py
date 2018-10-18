import time
from datetime import datetime, timedelta
import re
import socket
import json
import pickle
from simplejson.scanner import JSONDecodeError
import requests
from settings import (
    LIMIT,
    BASEURL,
    EVENTS_TO_NOTIFY,
    USERNAME, PASSWORD,
    BLACKLIST,
    PA_APP_TOKEN,
    PA_USER_KEY
)



def main():
    # pylint: disable=no-member
    requests.packages.urllib3.disable_warnings(
        requests.packages.urllib3.exceptions.InsecureRequestWarning
    )
    # pylint: enable=no-member

    sess = login()
    last_ts = get_tsdump()
    mac_map = {}
    mac_map_time = None
    while True:
        try:
            if not mac_map_time or datetime.utcnow() - mac_map_time > timedelta(hours=1):
                mac_map = get_replace_map(sess)
                mac_map_time = datetime.utcnow()
                print('refresh mac_map')
                with open('tsdump.pkl', 'wb') as dumpfile:
                    pickle.dump(last_ts, dumpfile)
            response = sess.get(BASEURL + '/s/default/stat/event?_limit=%s' % LIMIT, verify=False)
            result = response.json()
            if result['meta']['rc'] == 'error' and result['meta']['msg'] == 'api.err.LoginRequired':
                sess = login()
                continue
            for event in sorted(result['data'], key=lambda x: x['time']):
                if event['time'] <= last_ts:
                    continue
                print(event['key'], event['datetime'])
                if event['key'].upper() in EVENTS_TO_NOTIFY:
                    msg = format_message(event, mac_map)
                    print(msg)
                    if event.get('user') not in BLACKLIST:
                        send_message_retry(msg)
                        # wait for a little bit with sending messages
                        time.sleep(2)
                last_ts = event['time']
            time.sleep(5)
        except (requests.exceptions.ConnectionError, JSONDecodeError) as exc:
            print(exc)
            time.sleep(2)
        except KeyboardInterrupt:
            print('saving')
            with open('tsdump.pkl', 'wb') as dumpfile:
                pickle.dump(last_ts, dumpfile)
            raise

def login():
    data = {
        'password': PASSWORD,
        'username': USERNAME,
        'sesstionTimeout': 3600000,
    }
    sess = requests.Session()
    sess.post(BASEURL + '/login', data=json.dumps(data), verify=False)
    return sess

def format_message(event, mac_map):
    message = '{msg} ({datetime})'.format(**event)
    pattern = re.compile(r'\b(' + '|'.join(mac_map.keys()) + r')\b')
    return pattern.sub(lambda x: mac_map[x.group()], message)

def get_replace_map(sess):
    mac_map = {}
    users = get_users(sess)
    devices = get_devices(sess)
    for device in users + devices:
        if 'name' in device and device['name']:
            mac_map[device['mac']] = device['name']
        elif 'hostname' in device and device['hostname']:
            mac_map[device['mac']] = device['hostname']
    return mac_map


def get_users(sess):
    response = sess.get(BASEURL + '/s/default/rest/user', verify=False)
    result = response.json()
    if result['meta']['rc'] == 'ok':
        return result['data']

def get_devices(sess):
    response = sess.get(BASEURL + '/s/default/stat/device', verify=False)
    result = response.json()
    if result['meta']['rc'] == 'ok':
        return result['data']

def send_message_retry(message, retries=3):

    for _retry in range(retries):
        try:
            _response = requests.post(
                'https://api.pushover.net/1/messages.json',
                data={'token': PA_APP_TOKEN, 'user': PA_USER_KEY, 'message': message},
            )
            break
        except socket.gaierror:
            print('retry')
            time.sleep(1)
            continue

def get_tsdump():
    try:
        with open('tsdump.pkl', 'rb') as dumpfile:
            tsdump = pickle.load(dumpfile)
        return tsdump
    except Exception as exc: # pylint: disable=broad-except
        import traceback

        traceback.print_exc()
        print('file not found', exc)
        return 0


if __name__ == '__main__':
    main()
