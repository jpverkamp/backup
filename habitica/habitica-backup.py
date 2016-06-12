#!/usr/bin/env python3

import json
import gzip
import os
import pprint
import requests
import sys
import time

user_id = os.environ['USER_ID']
api_token = os.environ['API_TOKEN']

def make_method(name, f):
    def new_f(path, **kwargs):
        if path.startswith('https://'):
            url = path
        else:
            url = 'https://habitica.com/api/v3/' + path.lstrip('/')
        url = url.format(**kwargs)
        print(name, url)

        return f(url, headers = {
            'x-api-user': user_id,
            'x-api-key': api_token,
            'Content-Type': 'application/json; charset=utf-8'
        })
    return new_f

def backup(response, target):
    target = os.path.join('data', user_id, target.format(
        year = time.strftime('%Y'),
        month = time.strftime('%m'),
        day = time.strftime('%d'),
        date = time.strftime('%Y%m%d')
    ))
    print(target)

    # Assume json, fallback to text
    try:
        output = json.dumps(response.json()['data'], default = str, indent = 4, sort_keys = True)
    except:
        output = response.text

    # Guarantee directory exists
    try:
        os.makedirs(os.path.dirname(target))
    except:
        pass

    # Write uncompressed version (when debugging)
    if '--debug' in sys.argv:
        with open(target, 'w') as fout:
            fout.write(output)

    # Write compressed version
    with gzip.open(target + '.gz', 'wb') as fout:
        fout.write(output.encode('utf-8'))

api_get = make_method('GET', requests.get)

backup(api_get('https://habitica.com/export/history.csv'), '{year}/{date}/history.{date}.csv')
backup(api_get('/user'), '{year}/{date}/user.{date}.json')
backup(api_get('/tasks/user'), '{year}/{date}/tasks.{date}.json')
backup(api_get('/groups/party'), '{year}/{date}/party.{date}.json')
