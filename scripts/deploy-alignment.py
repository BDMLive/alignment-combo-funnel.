"""Explicit FTPS deployment. Defaults to a read-only root verification."""
import argparse
import errno
import ftplib
import hashlib
import ipaddress
import os
import socket
import ssl
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DOCUMENT_ROOT = "/home/biblbugn/alignment.bibledavids.org"
ROOT_MARKER = ".alignment-deploy-root"
PUBLIC_URL = "https://alignment.bibledavids.org/"
STATIC_EXTENSIONS = {
    ".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg",
    ".webp", ".avif", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".otf",
}
TLS_SETTINGS = """set cmd:fail-exit yes
set cmd:trace no
set ftp:ssl-allow yes
set ftp:ssl-auth TLS
set ftp:ssl-force yes
set ftp:ssl-protect-data yes
set ftp:ssl-protect-list yes
set ftp:ssl-use-ccc no
set ssl:verify-certificate yes
set ssl:check-hostname yes
set ssl:ca-file /etc/ssl/certs/ca-certificates.crt
set ftp:passive-mode yes
set net:timeout 20
set net:max-retries 1
set net:reconnect-interval-base 5
set cache:enable no
"""


class DeploymentError(Exception):
    pass


# Official ranges checked against https://www.cloudflare.com/ips/ on 2026-10-29.
# Matching an edge address is evidence of Cloudflare routing, not proof of proxy settings.
CLOUDFLARE_NETWORKS = tuple(ipaddress.ip_network(value) for value in """
173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22
141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20
197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13
104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 2400:cb00::/32
2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32
2a06:98c0::/29 2c0f:f248::/32
""".split())
DIAGNOSTIC_REMEDIES = {
    "CONFIGURATION_MISSING": "Check the three GitHub Actions secret names; do not print their values.",
    "HOSTNAME_INVALID": "Use the provider-verified FTPS hostname, without protocol, port or path.",
    "DNS_FAILED": "Ask the DNS owner to correct the FTPS hostname record and allow DNS propagation.",
    "TCP_21_TIMEOUT": "Ask hosting support to allow inbound port 21 from the Actions runner; check DNS-only FTP routing and firewall rules.",
    "TCP_21_REFUSED": "Ask hosting support to enable explicit FTPS on port 21 and check the control-port firewall.",
    "TCP_21_UNREACHABLE": "Ask hosting support to check the FTPS address, routing and control-port firewall.",
    "FTP_GREETING_FAILED": "Ask hosting support to check the FTP service on port 21 and connection limits.",
    "AUTH_TLS_UNAVAILABLE": "Ask hosting support to enable AUTH TLS for explicit FTPS on port 21.",
    "CERTIFICATE_HOSTNAME_MISMATCH": "Obtain the hosting provider's verified FTPS hostname and update FTP_SERVER, or have the provider install a matching FTPS certificate. Do not bypass certificate checks.",
    "CERTIFICATE_INVALID": "Ask hosting support to repair the FTPS certificate chain, validity or trusted issuer.",
    "TLS_NEGOTIATION_FAILED": "Ask hosting support to check explicit FTPS TLS settings and supported secure protocols.",
    "AUTHENTICATION_REJECTED": "Ask hosting support to inspect the account login rejection and account policy. Account policy and credential validity have not been established.",
    "AUTHENTICATION_FAILED": "Ask hosting support to inspect the encrypted login stage and connection policy.",
    "PASSIVE_PROTECTION_FAILED": "Ask hosting support to enable encrypted passive data connections (PBSZ/PROT P).",
    "PASSIVE_DATA_TIMEOUT": "Ask hosting support to open and NAT the configured passive port range and advertise the correct public passive address.",
    "PASSIVE_DATA_CONNECTION_FAILED": "Ask hosting support to check passive port firewall/NAT, the advertised address and FTP data connection limits.",
    "PASSIVE_LIST_DENIED": "Ask hosting support to check read/list permissions for the dedicated FTP account root.",
    "PASSIVE_TLS_FAILED": "Ask hosting support to check passive data-channel TLS certificates and session reuse settings; keep encryption enabled.",
    "PASSIVE_LIST_FAILED": "Ask hosting support to inspect encrypted passive LIST handling; no listing contents are logged.",
    "DIAGNOSTIC_FAILED": "A local diagnostic failure occurred; review the offline safeguards without enabling protocol debug logs.",
}


class DiagnosticError(DeploymentError):
    def __init__(self, category):
        # Only fixed categories and fixed remedies reach logs, never exception text.
        self.category = category
        super().__init__(category + ": " + DIAGNOSTIC_REMEDIES[category])


def cloudflare_edge_match(addresses):
    return any(any(ipaddress.ip_address(address) in network for network in CLOUDFLARE_NETWORKS)
               for address in addresses)


def validate_hostname(server):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", server):
        raise DiagnosticError("HOSTNAME_INVALID")


class DiagnosticFTP(ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        # cPanel servers may require data connections to reuse the control TLS session.
        # Use the same validating context, hostname and session, never an insecure fallback.
        connection, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            try:
                connection = self.context.wrap_socket(
                    connection, server_hostname=self.host, session=self.sock.session
                )
            except Exception:
                connection.close()
                raise
        return connection, size


def certificate_category(error):
    return "CERTIFICATE_HOSTNAME_MISMATCH" if error.verify_code in (62, 64) else "CERTIFICATE_INVALID"


def diagnose(server, username, password):
    """Read-only staged probe. Stop before authentication unless TLS validates."""
    validate_hostname(server)
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(server, 21, type=socket.SOCK_STREAM)}
        if not addresses:
            raise OSError()
    except OSError:
        raise DiagnosticError("DNS_FAILED") from None
    print("FTPS DNS_OK")
    print("FTPS DNS_CLOUDFLARE_EDGE_MATCH" if cloudflare_edge_match(addresses) else "FTPS DNS_NO_CLOUDFLARE_EDGE_MATCH")
    if cloudflare_edge_match(addresses):
        print("FTPS DNS_REMEDY: confirm DNS-only FTP routing or provider-supported TCP proxy; standard HTTP proxying is unsuitable.")
    try:
        with socket.create_connection((server, 21), timeout=15):
            pass
    except (TimeoutError, socket.timeout):
        raise DiagnosticError("TCP_21_TIMEOUT") from None
    except OSError as error:
        category = "TCP_21_REFUSED" if error.errno == errno.ECONNREFUSED else "TCP_21_UNREACHABLE"
        raise DiagnosticError(category) from None
    print("FTPS TCP_21_OK")
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.keylog_filename = None
    ftp = DiagnosticFTP(context=context, timeout=15)
    ftp.set_debuglevel(0)
    ftp.trust_server_pasv_ipv4_address = False
    try:
        try:
            ftp.connect(server, 21)
        except (OSError, EOFError, ftplib.Error):
            raise DiagnosticError("FTP_GREETING_FAILED") from None
        print("FTPS FTP_GREETING_OK")
        try:
            ftp.auth()
        except ssl.SSLCertVerificationError as error:
            raise DiagnosticError(certificate_category(error)) from None
        except ftplib.error_perm:
            raise DiagnosticError("AUTH_TLS_UNAVAILABLE") from None
        except (OSError, EOFError, ftplib.Error):
            raise DiagnosticError("TLS_NEGOTIATION_FAILED") from None
        print("FTPS TLS_NEGOTIATION_OK")
        print("FTPS CERTIFICATE_CHAIN_OK")
        print("FTPS CERTIFICATE_HOSTNAME_OK")
        if not username or not password:
            raise DiagnosticError("CONFIGURATION_MISSING")
        try:
            ftp.login(username, password)
        except ftplib.error_perm:
            raise DiagnosticError("AUTHENTICATION_REJECTED") from None
        except (OSError, EOFError, ftplib.Error):
            raise DiagnosticError("AUTHENTICATION_FAILED") from None
        print("FTPS AUTHENTICATION_OK")
        try:
            ftp.prot_p()
            ftp.set_pasv(True)
        except (OSError, EOFError, ftplib.Error):
            raise DiagnosticError("PASSIVE_PROTECTION_FAILED") from None
        try:
            # Discard every entry. Never print/store directory names or server responses.
            ftp.retrlines("LIST", callback=lambda line: None)
        except (TimeoutError, socket.timeout):
            raise DiagnosticError("PASSIVE_DATA_TIMEOUT") from None
        except ssl.SSLError:
            raise DiagnosticError("PASSIVE_TLS_FAILED") from None
        except ftplib.error_perm as error:
            category = "PASSIVE_TLS_FAILED" if str(error)[:3] == "522" else "PASSIVE_LIST_DENIED"
            raise DiagnosticError(category) from None
        except ftplib.error_temp as error:
            category = "PASSIVE_DATA_CONNECTION_FAILED" if str(error)[:3] in {"425", "426"} else "PASSIVE_LIST_FAILED"
            raise DiagnosticError(category) from None
        except (ConnectionError, OSError):
            raise DiagnosticError("PASSIVE_DATA_CONNECTION_FAILED") from None
        except (EOFError, ftplib.Error):
            raise DiagnosticError("PASSIVE_LIST_FAILED") from None
        print("FTPS PASSIVE_LIST_OK")
        print("FTPS DIAGNOSTIC_OK: read-only; run normal verify separately to validate the dedicated root/marker.")
    finally:
        # Close locally; no file writes, deletes or directory changes are issued.
        ftp.close()


def marker_format(content):
    """Mirror the production comparison exactly; report a format, never contents."""
    try:
        text = content.decode("utf-8")
    except UnicodeError:
        return False, "INVALID_UTF8"
    trimmed = text.strip()
    if trimmed == DOCUMENT_ROOT:
        return True, "ACCEPTED"
    if text.startswith("\ufeff"):
        return False, "UTF8_BOM"
    if trimmed == DOCUMENT_ROOT + "/":
        return False, "TRAILING_SLASH"
    if trimmed in {'"' + DOCUMENT_ROOT + '"', "'" + DOCUMENT_ROOT + "'"}:
        return False, "QUOTED_PATH"
    return False, "WRONG_VALUE"


def inspect_root(server, username, password):
    """Inspect only PWD and the named marker. Never list directories or write remotely."""
    validate_hostname(server)
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.keylog_filename = None
    ftp = DiagnosticFTP(context=context, timeout=15)
    ftp.set_debuglevel(0)
    ftp.trust_server_pasv_ipv4_address = False
    stage = "FTP_GREETING_FAILED"
    try:
        ftp.connect(server, 21)
        stage = "TLS_NEGOTIATION_FAILED"
        ftp.auth()
        stage = "AUTHENTICATION_FAILED"
        ftp.login(username, password)
        stage = "PASSIVE_PROTECTION_FAILED"
        ftp.prot_p()
        ftp.set_pasv(True)
        stage = "ROOT_PWD_FAILED"
        path = ftp.pwd().rstrip("/") or "/"
        # Never expose an unrelated actual directory, banner or credential-bearing response.
        safe_path = path if path in {"/", DOCUMENT_ROOT} else "unexpected"
        print("FTP_ROOT: " + safe_path)
        if safe_path == "unexpected":
            print("MARKER_EXISTS: unknown")
            print("MARKER_CONTENT_MATCH: unknown")
            print("ROOT_VALIDATION: failed")
            print("ROOT_REASON: LOGIN_DIRECTORY_MISMATCH")
            print("JAIL_MAPPING: cpanel_confirmation_required")
            return False
        exists = None
        stage = "ROOT_MARKER_STAT_FAILED"
        try:
            ftp.voidcmd("TYPE I")
            if ftp.size(ROOT_MARKER) is not None:
                exists = True
        except ftplib.error_perm:
            # SIZE is optional; a rejection does not prove that a file is absent.
            pass
        content = bytearray()
        def collect(chunk):
            if len(content) + len(chunk) > 4096:
                raise ValueError("marker too large")
            content.extend(chunk)
        reason = None
        stage = "ROOT_MARKER_READ_FAILED"
        try:
            ftp.retrbinary("RETR " + ROOT_MARKER, collect, blocksize=4096)
            exists = True
        except ftplib.error_perm as error:
            # Inspect only to classify, never log the server's reply.
            if exists is None and re.search(r"no such file|not found|does not exist", str(error), re.IGNORECASE):
                exists = False
                reason = "MARKER_NOT_FOUND"
            else:
                reason = "MARKER_ACCESS_DENIED_OR_UNAVAILABLE"
        except (TimeoutError, socket.timeout):
            reason = "MARKER_READ_TIMEOUT"
        except ssl.SSLError:
            reason = "MARKER_DATA_TLS_FAILED"
        except ValueError:
            exists = True
            reason = "MARKER_TOO_LARGE"
        except (OSError, EOFError, ftplib.Error):
            reason = "MARKER_READ_FAILED"
        print("MARKER_EXISTS: " + ("unknown" if exists is None else str(exists).lower()))
        if reason:
            print("MARKER_CONTENT_MATCH: unknown")
            print("ROOT_VALIDATION: failed")
            print("ROOT_REASON: " + reason)
            print("JAIL_MAPPING: cpanel_confirmation_required")
            return False
        matches, formatting = marker_format(bytes(content))
        print("MARKER_CONTENT_MATCH: " + str(matches).lower())
        print("MARKER_FORMAT: " + formatting)
        print("ROOT_VALIDATION: " + ("passed" if matches else "failed"))
        print("JAIL_MAPPING: cpanel_confirmation_required")
        return matches
    except ssl.SSLCertVerificationError as error:
        raise DiagnosticError(certificate_category(error)) from None
    except (OSError, EOFError, ftplib.Error):
        if stage in DIAGNOSTIC_REMEDIES:
            raise DiagnosticError(stage) from None
        raise DeploymentError("ROOT_INSPECTION_FAILED: " + stage) from None
    finally:
        ftp.close()


def production_files(root):
    """Allowlist public static files; never mirror the repository itself."""
    if not (root / "index.html").is_file():
        raise DeploymentError("Production index.html is missing from repository root.")
    candidates = [root / "index.html"]
    candidates += [p for p in root.iterdir() if p.suffix.lower() in STATIC_EXTENSIONS - {".html", ".js", ".css", ".json"}]
    for folder in ("assets", "locales"):
        directory = root / folder
        if directory.is_symlink():
            raise DeploymentError("Production directories must not be symlinks.")
        for current, directories, files in os.walk(directory, followlinks=False):
            if any((Path(current) / name).is_symlink() for name in directories):
                raise DeploymentError("Symlinked asset directories are not allowed.")
            directories[:] = [name for name in directories if not name.startswith(".") and name not in {"node_modules", "__pycache__"}]
            candidates += [Path(current) / name for name in files]
    selected = []
    for source in candidates:
        relative = source.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if source.suffix.lower() not in STATIC_EXTENSIONS:
            continue
        if relative.parts[0] == "locales" and source.suffix.lower() != ".json":
            continue
        if source.is_symlink():
            raise DeploymentError("Symlinked production files are not allowed.")
        if source.is_file():
            selected.append(relative)
    return sorted(set(selected))


def login_root(reply):
    """Accept only the dedicated absolute root or an explicitly marked jail."""
    matches = re.findall(r'^257\s+"((?:[^"\r\n]|"")*)"', reply, re.MULTILINE)
    if len(matches) != 1:
        raise DeploymentError("Cannot verify the FTP login directory from the server PWD reply.")
    path = matches[0].replace('""', '"').rstrip("/") or "/"
    if path not in {DOCUMENT_ROOT, "/"}:
        raise DeploymentError("FTP login directory does not match the dedicated ALIGNMENT root. No upload is permitted.")
    return path


def verified_root(reply, marker=None):
    path = login_root(reply)
    # Always require the cPanel-placed marker, including for an absolute PWD match.
    if marker is None or marker.strip() != DOCUMENT_ROOT:
        raise DeploymentError("ROOT_MARKER_INVALID: verify the cPanel account mapping and existing .alignment-deploy-root marker. No files were uploaded.")
    return path


def mirror_command(stage):
    # No --delete, --delete-excluded or --no-overwrite. Existing remote-only files stay.
    return (
        "mirror --reverse --overwrite --transfer-all --no-perms --no-symlinks "
        f'--parallel=2 --max-errors=1 "{stage.as_posix()}" .'
    )


def connect(server, username, password, commands, work):
    validate_hostname(server)
    # Percent encoding prevents lftp command injection from the account name.
    address = f"ftp://{quote(username, safe='')}@{server}:21"
    script = work / "session.lftp"
    script.write_text(TLS_SETTINGS + f'open --env-password "{address}"\n' + commands + "\nbye\n")
    script.chmod(0o600)
    environment = os.environ.copy()
    environment["LFTP_PASSWORD"] = password
    # Neither credentials nor raw protocol output are printed, even on failure.
    try:
        result = subprocess.run(
            ["lftp", "--norc", "-f", str(script)], env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        raise DeploymentError("FTPS client unavailable or connection timed out.") from None
    if result.returncode:
        raise DeploymentError(
            "FTPS_VERIFY_FAILED: run the read-only diagnose operation to identify the failing stage. "
            "TLS validation remains enabled; raw output is suppressed."
        )
    return result.stdout


def verify_published_site(local_index, remote_index):
    """After an approved upload, verify root placement and the HTTPS page."""
    expected = hashlib.sha256(local_index.read_bytes()).digest()
    if not remote_index.is_file() or hashlib.sha256(remote_index.read_bytes()).digest() != expected:
        raise DeploymentError("REMOTE_INDEX_MISMATCH: upload occurred, but index.html at the verified root did not match. No rollback or deletion was attempted.")
    print("REMOTE_INDEX_OK: index.html is directly inside the verified ALIGNMENT document root.")
    try:
        request = Request(PUBLIC_URL, headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity"})
        with urlopen(request, context=ssl.create_default_context(), timeout=20) as response:
            # Stop redirects from being mistaken for a verified ALIGNMENT publication.
            if response.status != 200 or response.geturl() != PUBLIC_URL:
                raise DeploymentError("PUBLIC_PAGE_NOT_VERIFIED: upload occurred; check domain routing and HTTPS. No rollback or deletion was attempted.")
            body = response.read(2 * 1024 * 1024)
    except (OSError, ValueError):
        raise DeploymentError("PUBLIC_PAGE_UNREACHABLE: upload occurred; check HTTPS/domain routing. No rollback or deletion was attempted.") from None
    if hashlib.sha256(body).digest() != expected:
        raise DeploymentError("PUBLIC_PAGE_NOT_CURRENT: upload occurred, but HTTPS did not serve the uploaded index.html. Check document-root routing and purge hosting/CDN caches before claiming success.")
    print("PUBLIC_PAGE_OK: HTTPS served the uploaded ALIGNMENT index.html.")


def main(diagnostic=False, root_inspection=False):
    mode = os.environ.get("DEPLOY_MODE", "verify")
    if mode not in {"verify", "deploy"}:
        raise DeploymentError("DEPLOY_MODE must be verify or deploy.")
    if mode == "deploy" and os.environ.get("UPLOADS_ENABLED") != "true":
        raise DeploymentError("Uploads are explicitly locked in the workflow. A separately approved workflow change is required.")
    if mode == "deploy" and os.environ.get("DEPLOY_APPROVED") != "true":
        raise DeploymentError("Upload disabled: explicit manual confirmation is required after hostname and target verification.")
    credentials = [os.environ.get(key, "") for key in ("FTP_SERVER", "FTP_USERNAME", "FTP_PASSWORD")]
    if not all(credentials):
        raise DeploymentError("FTP_SERVER, FTP_USERNAME and FTP_PASSWORD secrets are required.")
    if root_inspection:
        if mode != "verify":
            raise DeploymentError("Root inspection requires DEPLOY_MODE=verify.")
        return inspect_root(*credentials)
    if diagnostic:
        if mode != "verify":
            raise DeploymentError("Diagnostics require DEPLOY_MODE=verify.")
        diagnose(*credentials)
        return
    files = production_files(ROOT)
    with tempfile.TemporaryDirectory(prefix="alignment-ftps-") as temporary:
        work = Path(temporary)
        reply = connect(*credentials, "quote PWD\ncls -1 > /dev/null", work)
        # Reject unexpected locations before reading even the verification marker.
        login_root(reply)
        marker_path = work / "root-marker"
        try:
            connect(*credentials, f'get {ROOT_MARKER} -o "{marker_path.as_posix()}"', work)
            marker = marker_path.read_text()
        except (DeploymentError, OSError, UnicodeError):
            marker = None
        remote_root = verified_root(reply, marker)
        print(f"Verified ALIGNMENT target: {DOCUMENT_ROOT}")
        print(f"Production allowlist: {len(files)} static files. Explicit FTPS port 21; TLS certificate validation enabled.")
        if mode == "verify":
            print("Read-only verification complete. No remote files were created, overwritten or deleted.")
            return
        stage = work / "site"
        stage.mkdir()
        for relative in files:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        # Re-select only the root verified above; never create/guess a deployment directory.
        remote_index = work / "published-index.html"
        commands = (
            f'cd "{remote_root}"\n' + mirror_command(stage)
            + f'\nget index.html -o "{remote_index.as_posix()}"'
        )
        connect(*credentials, commands, work)
        verify_published_site(stage / "index.html", remote_index)
        print("Upload complete. Existing remote-only files were retained; no remote deletion was requested.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read-only FTPS verification and diagnostics; uploads remain locked.")
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("--diagnose", action="store_true", help="Run sanitized, read-only staged FTPS diagnostics")
    operations.add_argument("--inspect-root", action="store_true", help="Inspect only the login directory and existing marker; never write remotely")
    arguments = parser.parse_args()
    try:
        result = main(diagnostic=arguments.diagnose, root_inspection=arguments.inspect_root)
        if arguments.inspect_root and result is False:
            sys.exit(1)
    except DeploymentError as error:
        print(f"Deployment stopped: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Never expose an unexpected traceback containing protocol data or credentials.
        print("Deployment stopped: DIAGNOSTIC_FAILED" if arguments.diagnose else "Deployment stopped: VERIFICATION_FAILED", file=sys.stderr)
        sys.exit(1)
