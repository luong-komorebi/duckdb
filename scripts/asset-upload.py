import json
import os
import sys
import glob
import mimetypes
import urllib.request

api_url = 'https://api.github.com/repos/duckdb/duckdb/'

if len(sys.argv) < 2:
    print("Usage: [filename1] [filename2] ... ")
    exit(1)

# this essentially should run on release tag builds to fill up release assets and main

pr = os.getenv("TRAVIS_PULL_REQUEST", "")
if pr != "false":
    print("Not running on PRs. Exiting.")
    exit(0)

tag = os.getenv("TRAVIS_TAG", '')  # this env var is always present just not always used
if tag == '':
    tag = 'main-builds'
print(f"Running on tag {tag}")

if tag == "main-builds" and os.getenv("TRAVIS_BRANCH", "") != "main":
    print(f"Only running on main branch for {tag} tag. Exiting.")
    exit(0)


token = os.getenv("GH_TOKEN", "")
if token == "":
    raise ValueError('need a GitHub token in GH_TOKEN')


def gh_api(suburl, filename='', method='GET'):
    url = api_url + suburl
    headers = {
        "Content-Type": "application/json",
        'Authorization': f'token {token}',
    }

    body_data = b''

    if len(filename) > 0:
        method = 'POST'
        body_data = open(filename, 'rb')

        mime_type = mimetypes.guess_type(local_filename)[0]
        if mime_type is None:
            mime_type = "application/octet-stream"
        headers["Content-Type"] = mime_type
        headers["Content-Length"] = os.path.getsize(local_filename)

        url = suburl  # cough

    req = urllib.request.Request(url, body_data, headers)
    req.get_method = lambda: method
    try:
        raw_resp = urllib.request.urlopen(req).read().decode()
    except urllib.error.HTTPError as e:
        raw_resp = e.read().decode()  # gah

    return json.loads(raw_resp) if method != 'DELETE' else {}


# check if tag exists
resp = gh_api(f'git/ref/tags/{tag}')
if 'object' not in resp or 'sha' not in resp['object']:  # or resp['object']['sha'] != sha
    raise ValueError(f'tag {tag} not found')

resp = gh_api(f'releases/tags/{tag}')
if 'id' not in resp or 'upload_url' not in resp:
    raise ValueError('release does not exist for tag ' % tag)

# double-check that release exists and has correct sha
# disabled to not spam people watching releases
# if 'id' not in resp or 'upload_url' not in resp or 'target_commitish' not in resp or resp['target_commitish'] != sha:
# 	raise ValueError('release does not point to requested commit %s' % sha)

# TODO this could be a paged response!
assets = gh_api(f"releases/{resp['id']}/assets")

upload_url = resp['upload_url'].split('{')[0]  # gah
files = sys.argv[1:]
for filename in files:
    if '=' in filename:
        parts = filename.split("=")
        asset_filename = parts[0]
        paths = glob.glob(parts[1])
        if len(paths) != 1:
            raise ValueError(f"Could not find file for pattern {local_filename}")
        local_filename = paths[0]
    else:
        asset_filename = os.path.basename(filename)
        local_filename = filename

    # delete if present
    for asset in assets:
        if asset['name'] == asset_filename:
            gh_api(f"releases/assets/{asset['id']}", method='DELETE')

    resp = gh_api(f'{upload_url}?name={asset_filename}', filename=local_filename)
    if 'id' not in resp:
        raise ValueError(f'upload failed :/ {str(resp)}')
    print(f"{local_filename} -> {resp['browser_download_url']}")
