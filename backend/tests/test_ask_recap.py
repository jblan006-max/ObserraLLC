import asyncio
import sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import scheduled

# Stub the real email send so the recap logic runs against the LIVE DB without spamming inboxes.
sent = []


async def _fake_send(email, subject, html):
    sent.append((email, subject, len(html)))


scheduled.notifications.send_email = _fake_send


async def main():
    await scheduled._run_ask_recap_digest()
    print("emails that WOULD be sent:", len(sent))
    for e in sent[:5]:
        print("  ->", e[0], "|", e[1])
    # also prove the HTML builder works
    html = scheduled._ask_recap_html(3, {"slack": 2, "teams": 1},
                                     [("What are the top risks?", 2)], [("cfo", 2)],
                                     [("top risks", "28 open Critical SoD conflicts...")])
    print("html_builder_ok:", "Weekly Ask-the-Digest Recap" in html and len(html) > 200)


asyncio.run(main())
