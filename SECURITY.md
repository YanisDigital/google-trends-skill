# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub: **Security** tab > **Report a vulnerability** (private vulnerability reporting). Do not open a public issue for a vulnerability.

Include what you found, how to reproduce it, and the version (`plugin.json`). You will get an answer as soon as possible; fixes are released as a new version and noted in the commit history.

## Scope

In scope: the scripts in `skills/google-trends/scripts/`, the skill instructions, and the CI configuration. Examples: a way to make a report execute script or leak data, a path that writes outside the output folder, a formula-injection route in CSV or XLSX, unsafe XML or JSON handling, a secret committed to the repository.

Out of scope: Google's own services, behaviour of third-party packages (report those upstream), and rate limiting or blocking by Google.

## Design guarantees

- Network access only to `trends.google.com`; no telemetry. The scripts never read, store or send credentials or cookies. In browser mode the user's own Chrome sends its usual Google session to Google, as when browsing by hand; the documentation says so.
- Data from Trends is treated as untrusted: escaped in HTML and Markdown, neutralised in spreadsheets, never executed.
- Generated files stay in the user's chosen output folder; a folder the tool creates gets a `.gitignore` with `*`. Snapshot files are validated strictly, and every write is checked against the output folder.
- If you believe a release violates any of the above, please report it.

## Supported versions

Only the latest release on the default branch is supported.
