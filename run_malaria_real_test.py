"""Fetch real Malaria fixture + run bar real-data test."""
import sys, subprocess, json
sys.path.insert(0, r'd:\Projects CHAI\1. Laos\Auto report')
from config.credentials import load_password

pw   = load_password('https://hmis.gov.la/hmis', 'truong@chai')
url  = 'https://hmis.gov.la/hmis'
user = 'truong@chai'

PROG  = 'yAKTrPUMAuU'
STAGE = 'h86ikuTvjuP'
DE    = 'qf5LcIDIXSJ'
OPTS  = 'PF,PV,PO,PM,PK,Mixed'
FIX   = f'C:/Temp/test_fixture_{PROG}.json'

print('=== Step 1: Fetch fixture ===')
r1 = subprocess.run([
    'python', 'fetch_test_fixture.py',
    '--url', url, '--user', user, '--password', pw,
    '--program', PROG, '--stage', STAGE, '--de', DE,
    '--out', FIX,
], capture_output=True, text=True, cwd=r'd:\Projects CHAI\1. Laos\Auto report')
print(r1.stdout)
if r1.returncode != 0:
    print('ERROR:', r1.stderr[:400])
    sys.exit(1)

print('\n=== Step 2: Run real-data checklist ===')
r2 = subprocess.run([
    'python', 'test_bar_real.py',
    '--fixture', FIX,
    '--program', PROG, '--stage', STAGE, '--de', DE,
    '--options', OPTS,
    '--out', r'C:/Temp',
], capture_output=True, text=True, cwd=r'd:\Projects CHAI\1. Laos\Auto report')
print(r2.stdout)
if r2.returncode != 0:
    print('ERROR:', r2.stderr[:800])
    sys.exit(1)

print('\nDone. Images in C:/Temp/bar_real_checks/')
