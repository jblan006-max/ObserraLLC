// Single source of truth for the app version.
// Bump APP_VERSION here on any release/patch and every "v1.0.0" label + the
// "What's new" note update automatically.
export const APP_VERSION = "1.0.0";
export const APP_VERSION_LABEL = `v${APP_VERSION}`;

// Per-version changelog map — each release keeps its own "What's new" notes.
// Add a new key (e.g. "1.1.0") when you cut a release and bump APP_VERSION.
export const APP_CHANGELOG = {
  "1.0.0": [
    "Continuous Control Effectiveness & Assurance dashboards — Mission Control through Defensibility",
    "Weekly Assurance Recap & Monthly Assurance Digest with auto-send, cadence and branded sealed-PDF board copies",
    "Auditor access portal, reviewer timeline and engagement analytics",
    "Control-owner readiness nudges and drift tracking",
    "AI Grounding monitor — hallucination checks on every AI answer",
    "Toggleable Demo Mode with a guided prospect walkthrough",
    "Cyber Crisis Commander — executive incident command: Mission Control, Decision Room, Business Impact, Containment & Recovery, Timeline evidence and a board-ready crisis brief",
  ],
};

// Notes for the currently-running version (surfaced by the header "What's new" popover).
export const CURRENT_CHANGELOG = APP_CHANGELOG[APP_VERSION] || [];
