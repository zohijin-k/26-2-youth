# Application and officer access

All application versions require the per-application HttpOnly owner cookie for
reads, writes, previews, signatures and uploaded originals. New owner cookies use
the API-wide path; expire the former narrow cookie at creation. Missing legacy
credentials are denied. Unknown private identifiers use the same denial response
as an unrelated browser. Do not add a credential recovery endpoint.

The built-in blank assets, layouts, original forms and public program information
retain their explicit public exceptions. Application-frozen generic assets retain
their existing ownership boundary. Parse integer aliases consistently with the
router, and treat every preview value other than a recognized false spelling as
private.

Every officer endpoint is guarded centrally, including future routers. Passwords
and session signing configuration are runtime settings; no implicit development
bypass is allowed. Roles describe workflow scope after login. Officer sessions may
read inline originals but cannot authorize applicant mutations. An expired session
returns the screen to login and preserves its local officer return path. Explicit
mock mode must make no backend requests.

Applicant JSON is projected through positive field lists, including PATCH replies.
Stored signature paths become protected API URLs. Redact textual resident numbers
before persistence, and preserve image data only for recognized, decoded PNG
signature fields. Rendering-time redaction alone does not meet the storage rule.

Tests must run without local credentials. Authenticate existing officer fixtures
through the real login endpoint with synthetic environment settings. Direct DB
seeds used as applicants need explicit synthetic ownership credentials in test
setup. Keep independent no-session clients in security tests; never monkeypatch
the production authorization guard. Retire only authorized anonymous-success
expectations and record their exact names and before/after results.
