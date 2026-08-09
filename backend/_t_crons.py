import asyncio
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")


async def main():
    from db import db
    import sap_uac  # noqa: F401  (import first to resolve the sap_uac<->sap_analytics load order)
    from sap_analytics import run_sap_board_pack, run_sap_owner_digest
    org = await db.organizations.find_one({})
    org_id = str(org["_id"])

    # --- Board Pack ---
    cfg = await db.sap_digest_config.find_one({"org_id": org_id}) or {}
    orig_recips = cfg.get("recipients", [])
    orig_bp = cfg.get("board_pack", False)
    await db.sap_digest_config.update_one(
        {"org_id": org_id},
        {"$set": {"org_id": org_id, "board_pack": True, "recipients": (orig_recips or ["exec@obserrallc.com"])}},
        upsert=True)
    await db.sap_board_pack_log.delete_many({"org_id": org_id})
    await run_sap_board_pack()
    log = await db.sap_board_pack_log.find_one({"org_id": org_id})
    print("BOARD PACK: log created =", bool(log), "| recipients =", (log or {}).get("recipients"))

    # --- Owner Digest ---
    await db.sap_watchlist.update_one(
        {"org_id": org_id, "user": "_test_owner", "area": "Finance"},
        {"$set": {"org_id": org_id, "user": "_test_owner", "area": "Finance", "owner": "owner@obserrallc.com"}},
        upsert=True)
    await run_sap_owner_digest()
    print("OWNER DIGEST: ran without exception (owner@obserrallc.com had Finance assigned)")

    # --- cleanup / restore ---
    await db.sap_watchlist.delete_many({"org_id": org_id, "user": "_test_owner"})
    await db.sap_board_pack_log.delete_many({"org_id": org_id})
    await db.sap_digest_config.update_one(
        {"org_id": org_id}, {"$set": {"board_pack": orig_bp, "recipients": orig_recips}})
    print("CLEANUP: restored board_pack =", orig_bp, "| recipients count =", len(orig_recips))


asyncio.run(main())
