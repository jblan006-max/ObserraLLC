# Auth Testing Playbook (Emergent Google Auth)

Google login is layered on top of the existing JWT email/password auth. A Google-authenticated
user is matched by email to an EXISTING Obserra user (invited users only) and issued our normal
httpOnly JWT session (access_token/refresh_token). No separate session store.

- Backend: POST /api/auth/google/session with header `X-Session-ID: <sid>`. Backend calls
  Emergent `/auth/v1/env/oauth/session-data`, reads the email, finds the user, sets JWT cookies,
  returns the user. Unknown emails get 403 ("ask your admin to invite you").
- The full Google OAuth round-trip cannot be automated (needs a real Google login), so verify the
  live round-trip manually. Automated tests should assert: 400 without X-Session-ID, 401/403 with a
  bogus session id, and that existing email/password login is unaffected.

Test admin: jblan2026@gmail.com (Google email matches the seeded admin, so Google sign-in logs
straight into the admin account).
