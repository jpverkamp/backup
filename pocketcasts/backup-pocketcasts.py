import bs4
import datetime
import gzip
import json
import os
import requests
import urllib.parse

os.system('mkdir -p data')

username = os.environ['POCKETCASTS_USERNAME']
password = os.environ['POCKETCASTS_PASSWORD']

session = requests.session()

# Login, we need a valid CSRF token from the login form so

response = session.get('https://play.pocketcasts.com/users/sign_in')
soup = bs4.BeautifulSoup(response.text, 'lxml')

params = {}
for field in soup.find_all('input'):
    try:
        params[field['name']] = field['value']
    except Exception as ex:
        pass

params['user[email]'] = username
params['user[password]'] = password

response = session.post('https://play.pocketcasts.com/users/sign_in', data = params)
if not response:
    raise Exception('Could not login')

# Fetch a summary of all podcasts

print('Fetching summary...')

response = session.post(
    'https://play.pocketcasts.com/web/podcasts/all.json',
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'X-XSRF-TOKEN': urllib.parse.unquote(response.cookies['XSRF-TOKEN']),
    },
    json = {}
)
if not response:
    raise Exception('Could not fetch all.json')

podcasts = response.json()['podcasts']

# For each podcast, go through and list currently unplayed episodes

print('Collecting unplayed episodes...')

for podcast in podcasts:
    print('-', podcast['title'])

    response = session.post(
        'https://play.pocketcasts.com/web/episodes/find_by_podcast.json',
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'X-XSRF-TOKEN': urllib.parse.unquote(response.cookies['XSRF-TOKEN']),
        },
        json = {
            'uuid': podcast['uuid'],
            'page': 1,
            'sort': 3, # By date, newest to oldest
        }
    )
    if not response:
        print('Could not podcast page for {}, continuing'.format(podcast['title']))

    unplayed_episodes = []

    for episode in response.json()['result']['episodes']:
        if episode['playing_status'] == 3: # played
            break

        unplayed_episodes.append(episode)

    podcast['unplayed_episodes'] = unplayed_episodes

# Write to a single gzipped json file per day

filename = '{}.json.gz'.format(datetime.date.today())

with gzip.open(os.path.join('data', filename), 'w') as fout:
    fout.write(json.dumps(podcasts, indent = 4, sort_keys = True).encode('utf-8'))
