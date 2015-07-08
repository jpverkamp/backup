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

# --- Fetch any new messages ---

username = os.environ['GMAIL_USERNAME']
password = os.environ['GMAIL_PASSWORD']
imap_host = os.environ['GMAIL_HOST']
imap_port = int(os.environ['GMAIL_PORT'])
mailbox = os.environ['GMAIL_MAILBOX']

output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
safe_chars =''.join(chr(c) if chr(c).isupper() or chr(c).islower() or chr(c).isdigit() else '_' for c in range(256))

collapse = re.compile(r'_+')

id_filename = 'ids.txt'

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

if os.path.exists(os.path.join(output_dir, id_filename)):
    with open(os.path.join(output_dir, id_filename), 'r') as f:
        read_ids = set(f.read().split('\n'))
else:
    read_ids = set()

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
    read_ids.add(id)

id_file.close()

# --- Create monthly tarballs for any content more than three months ago ---

now = datetime.datetime.now()
year = now.year
month = now.month - 3
if month <= 0:
    year -= 1
    month += 12

target = '%04d%02d' % (year, month)

for year in os.listdir(output_dir):
    if not os.path.isdir(os.path.join(output_dir, year)):
        continue

    for month in os.listdir(os.path.join(output_dir, year)):
        if not os.path.isdir(os.path.join(output_dir, year, month)):
            continue

        index = year + month
        if index >= target:
            continue

        tgz_root = os.path.join(output_dir, year)
        tgz_dir = month
        tgz_file = month + '.tgz'

        if os.path.exists(os.path.join(tgz_root, tgz_file)):
            cmd = 'cd %s; tar xf %s' % (tgz_root, tgz_file)
            print(cmd)
            os.system(cmd)

        cmd = 'cd %s; tar czf %s %s; rm -rf %s' % (tgz_root, tgz_file, tgz_dir, tgz_dir)
        print(cmd)
        os.system(cmd)
