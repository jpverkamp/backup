#!/usr/bin/env python3

import bs4
import datetime
import dateutil.parser
import json
import math
import os
import re
import requests
import sys
import time

os.system('mkdir -p shelves')

key = os.environ['GOODREADS_API_KEY']
secret = os.environ['GOODREADS_API_SECRET']
user_id = os.environ['GOODREADS_USER_ID']

per_page = 50

def api(method, endpoint, **kwargs):
    '''
    Wrap the goodreads api

    @param method The type of HTTP method (GET/POST/etc)
    @param endpoint The endpoint to call, example: /shelf/list.xml
    @param **kwargs Any parameters to pass to the api
    '''

    url = 'https://www.goodreads.com' + endpoint
    f = getattr(requests, method.lower())

    for i in range(3):
        try:
            return f(url, params = kwargs)
        except:
            sys.stderr.write('{} failed, waiting {} seconds\n'.format(endpoint, i ** 2))
            time.sleep(i ** 2)

def safe_get(soup, tag, convert = lambda x : x):
    '''
    Get the given tag from the given soup; optionally applying the given conversion function

    @param soup The beautiful soup to look in
    @param tag The tag to look for (only finds the first)
    @param convert The conversion function to apply to the value (if it exists) (default: none)'''

    try:
        return convert(soup.find(tag).text.strip())
    except:
        pass

    try:
        return convert(None)
    except:
        return None

# Start by getting a list of the user's shelves
response = api('GET', '/shelf/list.xml', key = key, user_id = user_id)
soup = bs4.BeautifulSoup(response.text, 'xml')

for shelf in soup.find_all('user_shelf'):
    shelf_data = {
        'id': int(shelf.find('id').text),
        'name': shelf.find('name').text,
        'count': int(shelf.find('book_count').text),
        'books': []
    }
    print(shelf_data['name'])

    # Go through all of the pages of the user's books
    last_page = math.ceil(shelf_data['count'] / per_page)
    for page in range(1, 1 + last_page):
        print('- [{}/{}]'.format(page, 1 + last_page))

        response = api('GET', '/review/list.xml?v=2',
            key = key,
            id = user_id,
            shelf = shelf_data['name'],
            sort = 'date_updated',
            order = 'd',
            page = page,
            per_page = per_page
        )
        shelf_soup = bs4.BeautifulSoup(response.text, 'xml')

        # Pull out every review on this page (even non-'reviewed' books have a review element)
        for review in shelf_soup.find_all('review'):
            book_data = {
                'shelf': shelf_data['name'],
                'id': safe_get(review, 'id', int),
                'title': safe_get(review, 'title'),
                'description': safe_get(review, 'description'),
                'average_rating': safe_get(review, 'average_rating', float),
                'my_rating': safe_get(review, 'rating', float),
                'authors': [
                    safe_get(author, 'name')
                    for author in review.find_all('author')
                ],
                'started': safe_get(review, 'started_at', dateutil.parser.parse),
                'finished': safe_get(review, 'read_at', dateutil.parser.parse),
                'review': safe_get(review, 'body'),
            }

            shelf_data['books'].append(book_data)

    # Write out the data for that shelf
    filename = shelf_data['name'] + '.json'
    with open(os.path.join('shelves', filename), 'w') as fout:
        json.dump(shelf_data, fout, indent = True, default = str)
