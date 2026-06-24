"""
find_malaria_uids.py — Tìm Program UID, Stage UID, và DE UID cho Malaria Register
Usage:
    python find_malaria_uids.py --url https://hmis.gov.la/hmis --user U --password P
"""
import argparse, json, sys
import requests

def get(base, path, auth):
    r = requests.get(f"{base}/api/{path}", auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url",      required=True)
    p.add_argument("--user",     required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--search",   default="malaria", help="keyword to filter program names")
    args = p.parse_args()

    base = args.url.rstrip("/")
    auth = (args.user, args.password)

    # 1. Find programs matching keyword
    data = get(base, "programs.json?fields=id,name,programType&paging=false", auth)
    progs = [p for p in data["programs"]
             if args.search.lower() in p["name"].lower()]

    if not progs:
        print(f"No programs found matching '{args.search}'")
        sys.exit(1)

    print(f"\n=== Programs matching '{args.search}' ===")
    for prog in progs:
        print(f"  [{prog['programType']}] {prog['name']}")
        print(f"    Program UID: {prog['id']}")

        # 2. Get stages for this program
        stg_data = get(base, f"programStages.json?program={prog['id']}&fields=id,name&paging=false", auth)
        for stg in stg_data.get("programStages", []):
            print(f"    Stage: {stg['name']}")
            print(f"      Stage UID: {stg['id']}")

            # 3. Get DEs in this stage, filter by keyword
            de_data = get(base,
                f"programStageDataElements.json?programStage={stg['id']}"
                f"&fields=dataElement[id,name,valueType,optionSet[id,name,options[code,name]]]"
                f"&paging=false", auth)
            for psde in de_data.get("programStageDataElements", []):
                de = psde["dataElement"]
                # Show DEs with optionSet (tracker_option type) or matching keyword
                if de.get("optionSet") or "result" in de["name"].lower() or "test" in de["name"].lower() or "diag" in de["name"].lower():
                    print(f"      DE: {de['name']}")
                    print(f"        DE UID: {de['id']}  valueType: {de.get('valueType')}")
                    if de.get("optionSet"):
                        opts = de["optionSet"].get("options", [])
                        codes = [f"{o['code']}={o['name']}" for o in opts[:10]]
                        print(f"        Options ({len(opts)}): {', '.join(codes)}")
        print()

if __name__ == "__main__":
    main()
