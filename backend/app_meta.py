"""Single backend source for the release version + changelog surfaced in board digests.

Keep this in sync with frontend/src/version.js when cutting a release: bump APP_VERSION
and add the new version's highlights to APP_CHANGELOG.
"""

APP_VERSION = "1.0.0"
APP_VERSION_LABEL = f"v{APP_VERSION}"

APP_CHANGELOG = {
    "1.0.0": [
        "Continuous Control Effectiveness & Assurance dashboards — Mission Control through Defensibility",
        "Weekly Assurance Recap & Monthly Assurance Digest with auto-send, cadence and branded sealed-PDF board copies",
        "Auditor access portal, reviewer timeline and engagement analytics",
        "Control-owner readiness nudges and drift tracking",
        "AI Grounding monitor — hallucination checks on every AI answer",
        "Toggleable Demo Mode with a guided prospect walkthrough",
    ],
}


def current_changelog():
    return APP_CHANGELOG.get(APP_VERSION, [])
