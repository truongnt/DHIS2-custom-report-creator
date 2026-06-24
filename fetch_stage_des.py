"""Fetch DEs from Malaria Register stage and print relevant ones."""
import sys, json
sys.path.insert(0, r'd:\Projects CHAI\1. Laos\Auto report')
from config.credentials import load_password
import requests

pw = load_password('https://hmis.gov.la/hmis', 'truong@chai')
auth = ('truong@chai', pw)
base = 'https://hmis.gov.la/hmis'

r = requests.get(
    f'{base}/api/programStages/h86ikuTvjuP.json'
    '?fields=id,name,programStageDataElements[dataElement[id,name,valueType,optionSet[id,name,options[code,name]]]]',
    auth=auth, timeout=60
)
r.raise_for_status()
data = r.json()
psdes = data.get('programStageDataElements', [])
print(f'Stage: {data["name"]}  — {len(psdes)} DEs\n')

keywords = ['test','result','diag','confirm','malaria','rdt','microscop','species','parasit','type']
for psde in psdes:
    de = psde['dataElement']
    has_opts = bool(de.get('optionSet'))
    is_relevant = any(kw in de['name'].lower() for kw in keywords)
    if has_opts or is_relevant:
        opts = de.get('optionSet', {}).get('options', [])
        codes = [o['code'] for o in opts[:10]]
        print(f"  {de['name']}")
        print(f"    DE UID: {de['id']}  valueType: {de['valueType']}")
        if opts:
            print(f"    Options ({len(opts)}): {', '.join(codes)}")

print('\n--- All DEs with OptionSet ---')
for psde in psdes:
    de = psde['dataElement']
    if de.get('optionSet'):
        opts = de['optionSet'].get('options', [])
        codes = [o['code'] for o in opts]
        print(f"  [{de['id']}] {de['name']}  -> {', '.join(codes)}")
