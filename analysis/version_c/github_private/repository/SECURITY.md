# Private repository security policy

This repository is intended for private, controlled review. Keep repository visibility private until licensing, privacy, and source-permission reviews are complete.

- Require multifactor authentication for maintainers.
- Use least-privilege access and review membership periodically.
- Protect the default branch and require reviewed changes.
- Never commit credentials, raw/person-level data, or local source datasets.
- Treat detected credentials as compromised: revoke and replace them; do not preserve values in audit output.
- Verify the SHA-256 manifest before accepting package changes.
- Security controls support detection and risk reduction; they do not guarantee immunity from compromise.
