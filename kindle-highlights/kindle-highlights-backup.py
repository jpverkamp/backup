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
MAX_TRIES = 5

# Set up session; Amazon wasn't giving me cookies without a valid user agent
# Modify it so that any requests to Kindle automatically retry
session = requests.Session()
session.headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.8,zh-TW;q=0.6,zh;q=0.4',
    'Cache-Control': 'no-cache',
    'Origin': 'https://www.amazon.com',
    'Pragma': 'no-cache',
    'Referer': 'https://www.amazon.com/ap/signin',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.78 Safari/537.36',

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
def try_login(response, attempt = 1):
    global soup, captcha, image, last_response, passed_response


    with open('passed.htm', 'w') as fout:
        fout.write(response.text)

    print('Attempt {}'.format(attempt))
    time.sleep(1)
    soup = bs4.BeautifulSoup(response.text)

    signin_data = {}
    for field in soup.find_all('input'):
        try:
            signin_data[field['name']] = field['value']
        except:
            pass

    signin_data['email'] = USERNAME
    signin_data['password'] = PASSWORD
    signin_data['x'] = 105
    signin_data['y'] = 4

    # You have to have a valid referer (sic) or Amazon will ignore you
    try:
        session.headers['Referer'] = response.history[-1].url
    except:
        session.headers['Referer'] = 'https://www.amazon.com/ap/signin'

    session.headers['Referer'] = response.request.url

    # Load all images in the page, I think they're looking at that
    for ns_img in soup.find_all('img'):
        ns_src = ns_img['src']
        if ns_src.startswith('//'):
            ns_src = 'https:' + ns_src
        session.get(ns_src).content

    # Check if they're looking for a captcha
    captcha = soup.find('div', {'id': 'ap_captcha_img'})
    if captcha:
        print('> Found captcha, attempting to solve...')
        image = captcha.find('img')
        captcha_response = session.get(image['src'])

        with open('captcha-{0}.jpg'.format(attempt), 'wb') as fout:
            fout.write(captcha_response.content)

        os.system('tesseract captcha-{0}.jpg captcha-{0}'.format(attempt))
        with open('captcha-{0}.txt'.format(attempt), 'r') as fin:
            captcha_text = fin.read().strip().replace(' ', '')

        if not captcha_text or captcha_text == 'Empty page!!':
            print('Failed to decode captcha, too complicated')
            sys.exit(0)

        print('> Captcha decoded: {}'.format(captcha_text))
        signin_data['guess'] = captcha_text

    response = session.post('https://www.amazon.com/ap/signin', headers = {'Host': 'www.amazon.com'}, data = signin_data)
    soup = bs4.BeautifulSoup(response.text)
    last_response = response
    with open('last.htm', 'w') as fout:
        fout.write(response.text)

    if response.status_code != 200:
        print('Failed to login: {0} {1}'.format(response.status_code, response.reason))
        sys.exit(0)

    error = soup.find('div', {'id': 'message_error'})
    if error:
        if 'characters' in error.text and attempt < MAX_TRIES:
            try_login(response, attempt + 1)

        print('Failed to login: {0}'.format(error.text))
        sys.exit(0)

    warning = soup.find('div', {'id': 'message_warning'})
    if warning:
        if 'the characters' in warning.text and attempt < MAX_TRIES:
            try_login(response, attempt + 1)

        print('Failed to login: {0}'.format(warning.text))
        sys.exit(0)

# Try to login, might be recursive if we need to solve a captcha
print('Logging in...')
response = session.get('https://kindle.amazon.com/login')
try_login(response)

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

