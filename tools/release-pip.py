import urllib.request, ssl, json, tempfile, os, sys, re, subprocess

if len(sys.argv) < 2:
    print("Usage: [release_tag]")
    exit(1)

if os.getenv('TWINE_USERNAME') is None or os.getenv('TWINE_PASSWORD') is None:
    print("Can't find TWINE_USERNAME or TWINE_PASSWORD in env ")
    exit(-1)

release_name = sys.argv[1]
release_rev = None

request = urllib.request.Request("https://api.github.com/repos/duckdb/duckdb/git/refs/tags/")
with urllib.request.urlopen(request, context=ssl._create_unverified_context()) as url:
    data = json.loads(url.read().decode())

    for ref in data:
        ref_name = ref['ref'].replace('refs/tags/', '')
        if ref_name == release_name:
            release_rev = ref['object']['sha']

if release_rev is None:
    print(f"Could not find hash for tag {sys.argv[1]}")
    exit(-2)

print(f"Using sha {release_rev} for release {release_name}")

binurl = f"http://download.duckdb.org/rev/{release_rev}/python/"
# assemble python files for release

fdir = tempfile.mkdtemp()
print(fdir)

upload_files = []
request = urllib.request.Request(binurl)
with urllib.request.urlopen(request, context=ssl._create_unverified_context()) as url:
    data = url.read().decode()
    f_matches = re.findall(r'href="([^"]+\.(whl|tar\.gz))"', data)
    for m in f_matches:
        if '.dev' in m[0]:
            continue
        print(f"Downloading {m[0]}")
        url = f'{binurl}/{m[0]}'
        local_file = f'{fdir}/{m[0]}'
        urllib.request.urlretrieve(url, local_file)
        upload_files.append(local_file)

if not upload_files:
    print("Could not find any binaries")
    exit(-3)

subprocess.run(['twine', 'upload', '--skip-existing'] + upload_files)
