#!/usr/bin/env python

import github
import os

# Load a list of repos we don't want to download / update
ignored = set()
if os.path.exists('ignore.txt'):
    with open('ignore.txt', 'r') as fin:
        for line in fin:
            ignored.add(line.strip())

# Connect to github (if you have MFA, your password must be a token)
gh = github.Github(os.environ['GITHUB_USERNAME'], os.environ['GITHUB_PASSWORD'])

# Loop over repos for the specified user, this will include their organization's repos as well
for repo in gh.get_user().get_repos():

    remote_path = repo.ssh_url
    size = repo.size
    owner = repo.owner.login
    name = repo.name
    name_with_owner = '{owner}/{name}'.format(owner = owner, name = name)
    print(name_with_owner)

    # Check if the repo is in the ignore list
    if owner in ignored or name in ignored or name_with_owner in ignored:
        print('... skipping')
        continue

    # Build up a list of commands that will be run for the given repo
    local_path = os.path.join('repos', owner, name)
    cmds = ['mkdir -p repos/{owner}; cd repos/{owner}'.format(owner = owner)]

    # Already exists, update it
    if os.path.exists(local_path):
        print('... updating')
        cmds += [
            'cd {name}'.format(name = name),
            'git fetch --all',
            'git reset --hard origin/master',
            'git pull origin master',
            #'git pull --rebase --prune',                 # Update to the most recent master
            #'git submodule update --init --recursive',   # Update submodules
            #'git clean-branches',                        # Remove branches that have been deleted remotely
        ]
    # Doesn't exist yet, clone it
    else:
        print('... cloning')
        cmds += [
            'git clone {url}'.format(url = remote_path), # Download a new clean copy using repo name as directory
            'cd {name}'.format(name = name),
            #'git submodule update --init --recursive',   # Download and update submodules
        ]

    # Run each command specified above, bailing out if any failed (&&)
    cmds = ' && '.join(cmds)
    os.system(cmds)
    print()
