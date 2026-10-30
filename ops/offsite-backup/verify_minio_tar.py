import hashlib
import json
import sys
import tarfile

path = sys.argv[1]
ok = bad = skipped = 0
total = 0
with tarfile.open(path, "r:gz") as tar:
    manifest = json.load(tar.extractfile("manifest.json"))
    members = {m.name: m for m in tar.getmembers() if m.name.startswith("objects/")}
    print("manifest objects:", manifest["count"], "| tar members:", len(members))
    for item in manifest["objects"]:
        m = members.get("objects/" + item["key"])
        if m is None or m.size != item["size"]:
            bad += 1
            print("MISSING/SIZE MISMATCH:", item["key"])
            continue
        total += m.size
        etag = item["etag"].strip('"')
        if "-" in etag:  # multipart etag is not a plain md5
            skipped += 1
            continue
        md5 = hashlib.md5(tar.extractfile(m).read()).hexdigest()
        if md5 == etag:
            ok += 1
        else:
            bad += 1
            print("MD5 MISMATCH:", item["key"])
print(f"md5 matches MinIO etag: {ok}, mismatches/missing: {bad}, multipart (not md5-comparable): {skipped}, bytes: {total}")
sys.exit(1 if bad else 0)
