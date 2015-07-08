import codecs
import datetime
import requests
import os
import time
import webbrowser
import yaml

with open('config.yaml', 'r') as fin:
    config = yaml.load(fin)

if not config:
    config = {}

# Wrapper around requests to shorten things

def makeMethod(f):
    def run(url, **kwargs):

        if 'access_token' in config:
            headers = {'Authorization': 'Bearer {access_token}'.format(access_token = config['access_token'])}
        else:
            headers = {}

        url = 'https://api.moves-app.com/api/1.1' + url.format(**kwargs)

        if 'data' in kwargs:
            return f(url, data = kwargs['data'], headers = headers)
        else:
            return f(url, headers = headers)

    return run

get = makeMethod(requests.get)
post = makeMethod(requests.post)

# Request a new access token

if not 'access_token' in config:
    url = 'https://api.moves-app.com/oauth/v1/authorize?response_type=code&client_id={client_id}&scope={scope}'.format(
        client_id = config['client_id'],
        scope = 'activity location'
    )
    print('Opening URL in browser...')
    webbrowser.open(url)
    code = raw_input('Please follow prompts and enter code: ')

    response = requests.post('https://api.moves-app.com/oauth/v1/access_token?grant_type=authorization_code&code={code}&client_id={client_id}&client_secret={client_secret}&redirect_uri={redirect_uri}'.format(
        code = code,
        client_id = config['client_id'],
        client_secret = config['client_secret'],
        redirect_uri = 'http://localhost/',
    ))
    js = response.json()
    print(js)

    config['access_token'] = js['access_token']
    config['refresh_token'] = js['refresh_token']
    config['user_id'] = js['user_id']

    with open('config.yaml', 'w') as fout:
        yaml.safe_dump(config, fout, default_flow_style=False)

# Perform a refresh on the access token just as a matter of course

response = requests.post('https://api.moves-app.com/oauth/v1/access_token', data = {
    'grant_type': 'refresh_token',
    'refresh_token': config['refresh_token'],
    'client_id': config['client_id'],
    'client_secret': config['client_secret']
})
js = response.json()

config['access_token'] = js['access_token']
config['refresh_token'] = js['refresh_token']
config['user_id'] = js['user_id']

with open('config.yaml', 'w') as fout:
    yaml.safe_dump(config, fout, default_flow_style=False)

# Load the user profile to see how far back data goes

user_profile = get('/user/profile').json()

# Loop through all missing files, or force load anything less than a week ago

date = datetime.datetime.strptime(user_profile['profile']['firstDate'], '%Y%m%d')
today = datetime.datetime.now()
oneWeekAgo = today - datetime.timedelta(days = 7)

while date < today:
    dir = os.path.join('data', date.strftime('%Y'), date.strftime('%m'))
    filename = os.path.join(dir, date.strftime('%d') + '.json')

    if not date > oneWeekAgo and os.path.exists(filename):
        date += datetime.timedelta(days = 1)
        continue

    if not os.path.exists(dir):
        os.makedirs(dir)

    print(filename)

    response = get('/user/storyline/daily/{date}?trackPoints=true', date = date.strftime('%Y%m%d'))

    if response.status_code != 200:
        print('Bad response, stopping')
        print(response.text)
        sys.exit(0)

    if int(response.headers['x-ratelimit-minuteremaining']) < 1:
        print('Rate limited, waiting one minute before continuing')
        time.sleep(60)

    if int(response.headers['x-ratelimit-hourremaining']) < 1:
        print('Rate limited, wait one hour and try again')
        sys.exit(0)

    with codecs.open(filename, 'w', 'utf-8') as fout:
        fout.write(response.text)

    date += datetime.timedelta(days = 1)
