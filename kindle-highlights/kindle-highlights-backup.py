import require_python_3

import bs4
import json
import os
import pprint
import re
import requests
import sys
import time

USERNAME = os.environ['AMAZON_USERNAME']
PASSWORD = os.environ['AMAZON_PASSWORD']

# Set up session; Amazon wasn't giving me cookies without a valid user agent
# Modify it so that any requests to Kindle automatically retry
session = requests.Session()
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.61 Safari/537.36'
}
session.mount('https://kindle.amazon.com/', requests.adapters.HTTPAdapter(max_retries = 5))

# Wrap session.get to automatically retry up to three times on error
def session_get_retry(*args, **kwargs):
    for i in range(3):
        try:
            response = session.get(*args, **kwargs)
            if response.status_code == 200:
                return response
            else:
                print('** failed: {0} {1}, retrying'.format(response.status_code, response.reason))

        except Exception as ex:
            print('** failed: {0}, retrying'.format(ex))
            time.sleep(0.5)

session.get_retry = session_get_retry

# Get a function to unescape html entites
try:
    import html
    html_unescape = html.unescape
except:
    try:
        import html.parser
        html_unescape = html.parser.HTMLParser().unescape
    except:
        import HTMLParser
        html_unescape = HTMLParser.HTMLParser().unescape

# Make sure the output directory exists
try:
    os.makedirs('Kindle Highlights')
except:
    pass

# Log in to Amazon, we have to get the real login page to bypass CSRF
print('Logging in...')
response = session.get('https://kindle.amazon.com/login')
soup = bs4.BeautifulSoup(response.text)

signin_data = {}
signin_form = soup.find('form', {'name': 'signIn'})
for field in signin_form.find_all('input'):
    try:
        signin_data[field['name']] = field['value']
    except:
        pass

signin_data[u'email'] = USERNAME
signin_data[u'password'] = PASSWORD

# You have to have a valid referer (sic) or Amazon will ignore you
session.headers['Referer'] = response.history[-1].url
response = session.post('https://www.amazon.com/ap/signin', data = signin_data)
soup = bs4.BeautifulSoup(response.text)

if response.status_code != 200:
    print('Failed to login: {0} {1}'.format(response.status_code, response.reason))
    sys.exit(0)

warning = soup.find('div', {'id': 'message_warning'})
if warning:
    print('Failed to login: {0}'.format(warning.text))
    sys.exit(0)

# Iterate through pages of books, 25 at a time
# Note: The last three parts of the URL are:
#   - mode (all, read, reading)
#   - starting index / page (increments in 25)
#   - all books (0) versus kindle only (1)
print('Getting books...')
book_page = 0
while True:
    time.sleep(0.5) # Half a second between pages

    response = session.get_retry('https://kindle.amazon.com/your_reading/0/{book_page}/0'.format(book_page = book_page))
    soup = bs4.BeautifulSoup(response.text)
    found_book = False

    # For each page of books, find all of the individual book links
    # The last part of each URL is Amazon's internal ID for that book
    for el in soup.findAll('td', {'class': 'titleAndAuthor'}, recursive = True):
        time.sleep(0.1) # 1/10 of a second between books

        found_book = True

        book_id = el.find('a')['href'].split('/')[-1]
        title = el.find('a').text
        sys.stdout.write(title + ' ... ')

        highlights = []
        cursor = 0

        # Ask the Amazon API for highlights one page of 10 at a time until we have them all
        while True:
            response = session.get_retry('https://kindle.amazon.com/kcw/highlights?asin={book_id}&cursor={cursor}&count=10'.format(
                book_id = book_id,
                cursor = cursor,
            ))
            js = response.json()

            found_highlight = False
            for item in js['items']:
                found_highlight = True
                item['highlight'] = html_unescape(item['highlight'])
                highlights.append(item)

            if found_highlight:
                cursor +=1
            else:
                break

        # If we have any highlights, write them to disk
        # Use book title as filename, but strip out 'dangerous' characters
        print('{count} highlights found'.format(count = len(highlights)))
        if highlights:
            filename = re.sub(r'[\/:*?"<>|"\']', '', title).strip() + '.json'
            path = os.path.join('Kindle Highlights', filename)

            with open(path, 'w', encoding = 'utf8') as fout:
                fout.write(json.dumps(highlights, fout, indent = 4, sort_keys = True, ensure_ascii = False))

    if found_book:
        book_page += 25
    else:
        break

