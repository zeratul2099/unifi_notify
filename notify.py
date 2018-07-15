import time
from datetime import datetime, timedelta
import re
import socket
import json
import pickle
import requests
from settings import LIMIT, BASEURL, EVENTS_TO_NOTIFY, USERNAME, PASSWORD, BLACKLIST, PA_APP_TOKEN, PA_USER_KEY


# TODO;
# validate result
# black
# readme


def main():
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    sess = login()
    last_ts = get_tsdump()
    mac_map = {}
    mac_map_time = None
    while(True):
        try:
            if not mac_map_time or datetime.utcnow() - mac_map_time > timedelta(hours=1):
                mac_map = get_replace_map(sess)
                mac_map_time = datetime.utcnow()
                print('refresh mac_map')
            r = sess.get(BASEURL + '/s/default/stat/event?_limit=%s' % LIMIT, verify=False)
            result = r.json()
            if result['meta']['rc'] == 'error' and result['meta']['msg'] == 'api.err.LoginRequired':
                sess = login()
            for event in sorted(result['data'], key=lambda x: x['time']):
                if event['time'] <= last_ts:
                    continue
                print(event['key'], event['datetime'])
                if event['key'].upper() in EVENTS_TO_NOTIFY:
                    msg = replace_users(event['msg'], mac_map)
                    print(msg)
                    if event.get('user') not in BLACKLIST:
                        send_message_retry(msg)
                last_ts = event['time']
        except requests.exceptions.ConnectionError as e:
            print(e)
        with open('tsdump.pkl', 'wb') as dumpfile:
            pickle.dump(last_ts, dumpfile)
        time.sleep(5)

def login():
    data = {
        'password': PASSWORD,
        'username': USERNAME,
        'sesstionTimeout': 3600000,
    }
    sess = requests.Session()
    sess.post(BASEURL + '/login', data=json.dumps(data), verify=False)
    return sess

def replace_users(msg, mac_map):
    pattern = re.compile(r'\b(' + '|'.join(mac_map.keys()) + r')\b')
    return pattern.sub(lambda x: mac_map[x.group()], msg)

def get_replace_map(sess):
    mac_map = {}
    users = get_users(sess)
    devices = get_devices(sess)
    for device in users + devices:
        if 'name' in device:
            mac_map[device['mac']] = device['name']
        elif 'hostname' in device:
            mac_map[device['mac']] = device['hostname']
    return mac_map


def get_users(sess):
    r = sess.get(BASEURL + '/s/default/rest/user', verify=False)
    result = r.json()
    if result['meta']['rc'] == 'ok':
        return result['data']
    else:
        return None

def get_devices(sess): 
    r = sess.get(BASEURL + '/s/default/stat/device', verify=False)
    result = r.json()
    if result['meta']['rc'] == 'ok':
        return result['data']
    else:
        return None

def send_message_retry(message, retries=3):

    for retry in range(retries):
        try:
            r = requests.post(
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
    except Exception as e:
        import traceback

        traceback.print_exc()
        print('file not found', e)
        return 0


if __name__ == '__main__':
    main()

