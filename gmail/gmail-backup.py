#!/usr/bin/env python

from __future__ import print_function

import codecs
import datetime
import email
import email.utils
import imaplib
import os
import re
import sys
import time

from pprint import pprint

username = os.environ['GMAIL_USERNAME']
password = os.environ['GMAIL_PASSWORD']
imap_host = os.environ['GMAIL_HOST']
imap_port = int(os.environ['GMAIL_PORT'])
mailbox = os.environ['GMAIL_MAILBOX']

output_dir = os.path.dirname(os.path.abspath(__file__))
safe_chars =''.join(chr(c) if chr(c).isupper() or chr(c).islower() or chr(c).isdigit() else '_' for c in range(256))

collapse = re.compile(r'_+')

id_filename = 'ids.txt'

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

if os.path.exists(os.path.join(output_dir, id_filename)):
    with open(os.path.join(output_dir, id_filename), 'r') as f:
        read_ids = f.read().split('\n')
else:
    read_ids = []

print('Authenticating')
mail = imaplib.IMAP4_SSL(imap_host, imap_port)
mail.login(username, password)

print('Switching to %s' % mailbox)
(state, count) = mail.select(mailbox, readonly = True)
count = int(count[0])
print('%s messages to read' % count)

print('Fetching ids')
result, data = mail.uid('search', None, "ALL")
ids = data[0].split()

id_file = open(os.path.join(output_dir, id_filename), 'a')

for id in ids:
    if id in read_ids:
        continue

    try:
        result, data = mail.uid('fetch', id, '(RFC822)')
        data = data[0][1]
        msg = email.message_from_string(data)

        msg_from = msg['From']
        msg_subj = msg['Subject'] if msg['Subject'] else '(no subject)'
        msg_date = datetime.datetime.fromtimestamp(time.mktime(email.utils.parsedate(msg['Date'])))

        dir = os.path.join(output_dir, '%04d' % msg_date.year, '%02d' % msg_date.month)
        if not os.path.exists(dir):
            os.makedirs(dir)

        filename = '%04d%02d%02d-%02d%02d%02d-%s' % (msg_date.year, msg_date.month, msg_date.day, msg_date.hour, msg_date.minute, msg_date.second, collapse.sub('_', msg_subj.translate(safe_chars)).strip('_'))

        print('%s: %s' % (id, filename))

        with open(os.path.join(dir, filename), 'w') as f:
            f.write(data)

    except Exception, ex:
        print('%s: %s' % (id, ex))

    id_file.write('%s\n' % id)
    id_file.flush()
    read_ids.append(id)

id_file.close()
