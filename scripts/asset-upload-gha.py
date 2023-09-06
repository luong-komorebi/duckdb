import json
import os
import sys
import glob
import time
import urllib.request

api_url = 'https://api.github.com/repos/duckdb/duckdb/'

if len(sys.argv) < 2:
    print("Usage: [filename1] [filename2] ... ")
    exit(1)

# this essentially should run on release tag builds to fill up release assets and master

repo = os.getenv("GITHUB_REPOSITORY", "")
if repo != "duckdb/duckdb":
    print("Not running on forks. Exiting.")
    exit(0)

ref = os.getenv("GITHUB_REF", '')  # this env var is always present just not always used
if ref == 'refs/heads/main':
    print("Not running on main branch. Exiting.")
    exit(0)
elif ref.startswith('refs/tags/'):
    tag = ref.replace('refs/tags/', '')
else:
    print("Not running on branches. Exiting.")
    exit(0)


print(f"Running on tag {tag}")


token = os.getenv("GH_TOKEN", "")
if token == "":
    raise ValueError('need a GitHub token in GH_TOKEN')


def internal_gh_api(suburl, filename='', method='GET'):
    url = api_url + suburl
    headers = {
        "Content-Type": "application/json",
        'Authorization': f'token {token}',
    }

    body_data = b''
    raw_resp = None
    if len(filename) > 0:
        method = 'POST'
        body_data = open(filename, 'rb')
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = os.path.getsize(local_filename)
        url = suburl  # cough

    req = urllib.request.Request(url, body_data, headers)
    req.get_method = lambda: method
    print(f'GH API URL: "{url}" Filename: "{filename}" Method: "{method}"')
    raw_resp = urllib.request.urlopen(req).read().decode()

    return json.loads(raw_resp) if method != 'DELETE' else {}


def gh_api(suburl, filename='', method='GET'):
    timeout = 1
    nretries = 10
    success = False
    for i in range(nretries + 1):
        try:
            response = internal_gh_api(suburl, filename, method)
            success = True
        except urllib.error.HTTPError as e:
            print(e.read().decode())  # gah
        except Exception as e:
            print(e)
        if success:
            break
        print(f"Failed upload, retrying in {timeout} seconds... ({i}/{nretries})")
        time.sleep(timeout)
        timeout = timeout * 2
    if not success:
        raise Exception(f"Failed to open URL {suburl}")
    return response


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
            raise ValueError(f"Could not find file for pattern {parts[1]}")
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
