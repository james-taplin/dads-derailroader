"""Print a compact summary of a Railroader Definitions.json (one line per field / component)."""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
width = int(sys.argv[2]) if len(sys.argv) > 2 else 300
for o in d["objects"]:
    df = o["definition"]
    print("=====", o["identifier"], df.get("kind"), df.get("modelIdentifier"))
    for k, v in df.items():
        if k == "components":
            print("  components:", len(v or []))
            for c in v or []:
                print("    ", json.dumps(c)[:width])
        else:
            print("  ", k, ":", json.dumps(v)[:width])

