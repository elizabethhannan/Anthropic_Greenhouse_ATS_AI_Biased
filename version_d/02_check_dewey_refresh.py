"""Read-only authenticated source metadata check; never download bulk datasets."""
from pathlib import Path
import os, sys, json, hashlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dewey_catalog import DeweyCatalog

OUT = ROOT / 'version_d' / 'outputs' / 'dewey_refresh_20261008'
OUT.mkdir(exist_ok=True)
for line in (ROOT / 'r2.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))

def unpack(result):
    if result.get('structuredContent'):
        return result['structuredContent']
    for item in result.get('content', []):
        if item.get('type') == 'text':
            try:
                return json.loads(item['text'])
            except ValueError:
                pass
    return result

def save(name, data):
    (OUT / (name + '.json')).write_text(json.dumps(data, indent=2))

catalog = DeweyCatalog()
try:
    baseline = json.loads((ROOT / 'dewey_person_catalog_metadata.json').read_text())
    for slug in ['person', 'experience']:
        data = unpack(catalog.call('get_dataset_details', {'slug': slug, 'projectId': 34978, 'includeTeamAccess': True}))
        save(slug + '_details', data)
        keys = ['id','externalId','name','doiVersionString','doi','versionTimestamp','lastRefreshAt','refreshDescription','rowsCount','sizeBytes','permissions','access','teamAccess']
        old = baseline['get_dataset_details_' + slug]['dataset']
        print(json.dumps({'dataset':slug,'frozen_metadata':{k:old.get(k) for k in keys},'current_metadata':{k:data.get('dataset',{}).get(k) for k in keys},'response_keys':list(data)},indent=2),flush=True)
        info = unpack(catalog.call('get_download_info', {'slug': slug}))
        save(slug + '_download_info', info)
        print(json.dumps({'dataset':slug,'download_info':info},indent=2),flush=True)
finally:
    catalog.close()
