#!/usr/bin/env python3

import json
import gzip
import os
import pprint
import requests
import time

user_id = os.environ['USER_ID']
api_token = os.environ['API_TOKEN']

def make_method(name, f):
    def new_f(path, **kwargs):
        url = ('https://habitrpg.com/api/v2/' + path.lstrip('/')).format(**kwargs)
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
    )) + '.gz'
    print(target)

    try:
        os.makedirs(os.path.dirname(target))
    except:
        pass

    fout = gzip.open(target, 'wb')
    try:
        fout.write(bytes(json.dumps(response.json(), default = str, indent = 4, sort_keys = True), 'UTF-8'))
    except:
        fout.write(bytes(response.text, 'UTF-8'))
    fout.close()

api_get = make_method('GET', requests.get)

backup(api_get('/export/history'), '{year}/{date}/history.{date}.csv')
backup(api_get('/user'), '{year}/{date}/user.{date}.json')
backup(api_get('/user/tasks'), '{year}/{date}/tasks.{date}.json')
backup(api_get('/groups/party'), '{year}/{date}/party.{date}.json')
