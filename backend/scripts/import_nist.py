"""Import NIST SP 800-53 (Rev.5) controls into db.nist_controls.

Usage:
  python import_nist.py --file /path/to/controls.json
  python import_nist.py --url https://example.com/nist_rev5.json

The script normalizes controls to {id,title,family,description,keywords} and upserts into the nist_controls collection.
"""
import argparse
import json
import os
import sys

from pymongo import MongoClient


def load_data_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data_from_url(url):
    import httpx
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def normalize_and_upsert(data, db):
    docs = []
    for c in data:
        ctrl = {
            "id": str(c.get("id") or c.get("controlId") or c.get("number") or c.get("identifier") or ""),
            "title": c.get("title") or c.get("name") or "",
            "family": c.get("family") or c.get("class") or "",
            "description": c.get("description") or c.get("text") or "",
            "keywords": c.get("keywords") or c.get("tags") or [],
        }
        if not ctrl["id"]:
            continue
        docs.append(ctrl)
        db.nist_controls.update_one({"id": ctrl["id"]}, {"$set": ctrl}, upsert=True)
    return len(docs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Local JSON file path with controls")
    p.add_argument("--url", help="Remote URL with controls JSON")
    p.add_argument("--mongo", default=os.environ.get("MONGO_URL", "mongodb://localhost:27017/"))
    p.add_argument("--db", default=os.environ.get("DB_NAME", "obserra"))
    args = p.parse_args()
    if not args.file and not args.url:
        print("Provide --file or --url")
        sys.exit(2)
    if args.file and not os.path.exists(args.file):
        print("File not found:", args.file)
        sys.exit(2)
    if args.file:
        data = load_data_from_file(args.file)
    else:
        data = load_data_from_url(args.url)

    client = MongoClient(args.mongo)
    db = client[args.db]
    n = normalize_and_upsert(data, db)
    print(f"Imported/updated {n} controls into {args.db}.nist_controls")


if __name__ == "__main__":
    main()
