# ALIGNMENT manual cPanel deployment

Repository: `Supernatural-Nation/alignment-web` (local remote `dev`, not `origin`).
Production branch: `dev`. Review branch: `zeals` (read-only `verify`/`diagnose` operations only).
Physical document root: `/home/biblbugn/alignment.bibledavids.org`.
Entry point: repository-root `index.html`.

The workflow is `.github/workflows/deploy-alignment.yml`. It uses `actions/checkout@v4`, system CA certificates and lftp explicit FTPS on port 21. There is no push trigger. `verify` is the default manual operation; `diagnose` is a separate read-only operation. The `deploy` option is prepared but blocked by the literal `UPLOADS_ENABLED: 'false'` until a separately approved workflow change enables the first upload. Even after that change, deployment remains manual and requires the confirmation `DEPLOY ALIGNMENT`.

## Hostname prerequisite — still pending

The earlier public diagnostic reached TCP port 21 and the FTP greeting for the configured hostname, but TLS failed with `CERTIFICATE_HOSTNAME_MISMATCH`. The resolved addresses did not match the checked Cloudflare edge ranges. Authentication and passive listing were not attempted after the certificate failure; incorrect credentials have not been established.

The earlier `bdm-theme-two` staging workflow was not found among available local projects, so its actual FTPS hostname could not be recovered. GitHub secrets cannot be read back. Do not invent a hostname or use an IP address to evade hostname validation.

Obtain the **certificate-valid FTPS server hostname** from the hosting provider or cPanel → FTP Accounts → Configure FTP Client. Confirm that the provider identifies it as the server for this hosting account, then update the existing `FTP_SERVER` secret to that hostname, without scheme, port or path. Leave `FTP_USERNAME` and `FTP_PASSWORD` unchanged. No hostname secret has been modified by this implementation.

If the provider wants to retain the current hostname, it must install a certificate valid for that hostname on the FTP service. A certificate installed only for the website is not proof that the FTP service uses it. Certificate chain and hostname checks remain enabled; there is no plaintext/insecure fallback.

## Existing secrets

- `FTP_SERVER`: hosting-provider-verified, certificate-matching hostname.
- `FTP_USERNAME`: existing dedicated account `alignmentdeploy@bibledavids.org`.
- `FTP_PASSWORD`: existing account password; never place it in the repository or logs.

The password is passed through `LFTP_PASSWORD`, not a command-line argument or the generated lftp command file. Raw lftp output, banners and listing contents are suppressed. Do not enable shell tracing or protocol debugging.

## cPanel directory verification

Before running a verification, use cPanel **Domains** to confirm the ALIGNMENT domain document root is `/home/biblbugn/alignment.bibledavids.org`, and **FTP Accounts** to confirm the dedicated FTP account is restricted to exactly that directory. Do not use an account restricted to the main website, Deliverance website, `/home/biblbugn` or `public_html`.

The script reads the server's actual `PWD` reply and performs an encrypted passive directory listing, with entries discarded. Only the exact expected root or jailed `/` is accepted as a candidate. Every candidate must then supply the existing matching `.alignment-deploy-root` marker before verification or upload passes. Any other non-root path fails before the marker is read. It never guesses a directory or navigates into a sibling site.

PWD may report `/` for a jailed account, which alone does not establish the physical root. After verifying the account mapping in cPanel, confirm this existing file through cPanel File Manager (enable Show Hidden Files); create it only if missing:

- Filename: `.alignment-deploy-root`
- Exact location: `/home/biblbugn/alignment.bibledavids.org/.alignment-deploy-root`
- Contents, one line:

  ```text
  /home/biblbugn/alignment.bibledavids.org
  ```

Both an exact absolute root and a jailed `/` require this matching marker. The script never creates or uploads the marker. A marker confirms the owner-supplied physical mapping; PWD alone cannot prove cPanel jail restrictions, so the FTP Accounts check is required. Missing/wrong markers stop the run.

## Read-only testing

The workflow must be registered on GitHub's default branch (`dev`) before its manual Run workflow control is available. If Actions has no Deploy ALIGNMENT workflow or Run workflow button, request approval to merge these deployment files to `dev` with uploads still locked; pushing only `zeals` may not register a new workflow. No merge to `dev` is performed by this review push. Publishing/merging these configuration files is separate from running them; there is no automatic push deployment.

1. Open Actions → Deploy ALIGNMENT → Run workflow.
2. Select branch `zeals` to test the reviewed changes (or `dev` after they are approved and merged), select mode `diagnose`, and leave confirmation blank.
3. Diagnostics check DNS, Cloudflare edge-range membership, port 21, FTP greeting, explicit TLS certificate/hostname verification, encrypted login and encrypted passive listing. Only sanitized stage categories and fixed remedies are logged. A certificate failure stops before any credentials are sent.
4. Once diagnostics pass, run mode `verify`, again with confirmation blank.
5. `verify` uses lftp to authenticate securely, obtain PWD, test passive listing and always read the existing marker. It makes no remote changes.

For `CERTIFICATE_HOSTNAME_MISMATCH`, ask hosting for its verified FTPS hostname and update only `FTP_SERVER`. For TCP failures, hosting must check the port-21 listener, routing and firewall. For passive-data failures, hosting must check its configured passive port range, NAT/public passive address and TLS data-channel configuration. Authentication rejection requires hosting account-policy/log investigation; it does not by itself establish a wrong password. Do not bypass certificate checks to reach later stages.

Neither a live authenticated directory verification nor a first deployment has been completed by this implementation. A successful read-only run does not establish write permissions.

## Read-only marker inspection

For `ROOT_MARKER_INVALID`, select manual mode `inspect-root` on the reviewed branch (`zeals`) and leave confirmation blank. This executes `--inspect-root` under `DEPLOY_MODE=verify`, independent of staging/mirroring. It obtains PWD, optionally queries SIZE for the named marker, then retrieves only `.alignment-deploy-root` over validated explicit FTPS. It does not print or request a complete directory listing, write/delete files, create directories, change directories, or modify the marker.

Output contains only sanitized fields: `FTP_ROOT`, `MARKER_EXISTS`, `MARKER_CONTENT_MATCH`, `MARKER_FORMAT`, `ROOT_VALIDATION`, optional `ROOT_REASON`, and `JAIL_MAPPING`. A missing/inaccessible file or a TLS/timeout error is not mislabeled as a content mismatch; unknown properties remain `unknown`. An unexpected directory is reported as `unexpected`, without exposing the actual path. Normal verification still fails closed and retains its existing strict comparison.

The production comparison is `marker.strip() == DOCUMENT_ROOT`. LF/CRLF trailing newlines and leading/trailing whitespace are already accepted. A UTF-8 byte-order mark, quotes around the path, a trailing slash, incorrect path, extra non-whitespace text or invalid UTF-8 does not pass. Inspection reports the relevant format/category without printing the actual content. Make only the correction established by the inspection; never rewrite a marker blindly.

A reported `/` plus a matching marker establishes the location assertion used by the verifier. FTP alone does not independently establish the physical cPanel jail mapping: confirm FTP Accounts restricts this account to the exact ALIGNMENT root. The inspection therefore always reports `JAIL_MAPPING: cpanel_confirmation_required` rather than claiming that it inspected cPanel settings.

This environment has no local FTP password, GitHub API token or authenticated browser session. An inspection implemented or unit-tested locally is not evidence of live remote marker state; obtain the actual sanitized output from an Actions run using the existing secrets. Do not paste passwords/tokens into chat.

## Approved first manual deployment — not authorized yet

Do not proceed until the hostname is valid, the cPanel restriction is confirmed, `diagnose` and `verify` have passed, and the owner explicitly approves the first upload and target.

1. Keep a cPanel backup of the dedicated ALIGNMENT directory.
2. Only after that approval, make a separate reviewed change setting the workflow's `UPLOADS_ENABLED` to `'true'`.
3. Run the workflow on `dev`, choose `deploy`, and type `DEPLOY ALIGNMENT` in confirmation.
4. The script repeats read-only connection/directory verification in this same run before invoking the mirror. No prior-run flag can bypass root checks.
5. It stages repository-root `index.html`, root image/font assets, static HTML/CSS/JS/JSON/image/font files under `assets/`, and `locales/*.json`. It uploads that staged directory into the verified FTP root using lftp reverse mirror. `index.html` is not nested inside an extra `site` or repository-name directory.
6. `.git`, `.github`, dotfiles/`.env*`, deployment scripts, QA files, documentation, source maps and development directories are outside the positive allowlist. Symlinks are rejected. Cloudinary URLs stay external; no video is downloaded into the repository.
7. `mirror --reverse --overwrite` uses no delete option. Matching website files are updated; existing remote-only files and the marker stay in place. No sibling/main/Deliverance directory is targeted.
8. After upload, the script downloads `index.html` directly from the verified root and compares its SHA-256 to the local staged index. It then requests `https://alignment.bibledavids.org/` over validated HTTPS and confirms the exact uploaded index is served with HTTP 200, without redirection to another URL.
9. Success is reported only after `REMOTE_INDEX_OK` and `PUBLIC_PAGE_OK`. If caching/domain routing prevents the current index being served, the job reports that the upload happened but public verification failed. Purge hosting/CDN caches or correct domain routing before retrying verification. No automatic rollback or deletion is performed.
10. Review video/poster, translations, images, navigation, FAQ and CTA links manually. The byte comparison does not test all browser interactions.

This is a non-atomic static-site upload. Automatic deployment remains absent even after a successful manual run; adding a push trigger requires a separate approval after first-upload verification. Never enable it merely because a connection test passed.

## Local validation

```sh
python3 -B -m unittest discover -s qa -p 'test_deploy_alignment.py'
node scripts/build-locales.cjs
git diff --check
```

Offline tests use fake connections/credentials and fake HTTPS responses. They do not authenticate, list, upload or delete on the hosting server. Live results must not be inferred from unit-test success.

References: [lftp manual](https://lftp.yar.ru/lftp-man.html), [GitHub manual triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow), [Python FTPS](https://docs.python.org/3/library/ftplib.html), [Cloudflare IPv4](https://www.cloudflare.com/ips-v4/) and [IPv6 ranges](https://www.cloudflare.com/ips-v6/).
