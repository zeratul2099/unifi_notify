import requests
import json
import time
import re

from settings import LIMIT, BASEURL, EVENTS_TO_NOTIFY, USERNAME, PASSWORD


# TODO;
# relogin
# validate result
# black
# blacklist


def main():
    sess = login()
    last_ts = 0
    mac_map = get_replace_map(sess)
    while(True):
        try:
            r = sess.get(BASEURL + '/s/default/stat/event?_limit=%s' % LIMIT, verify=False)
            for event in sorted(r.json()['data'], key=lambda x: x['time']):
                if event['time'] <= last_ts:
                    continue
                print(event['key'], event['datetime'])
                if event['key'].upper() in EVENTS_TO_NOTIFY:
                    print(replace_users(event['msg'], mac_map))
                last_ts = event['time']
        except requests.exceptions.ConnectionError as e:
            print(e)
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

if __name__ == '__main__':
    main()

