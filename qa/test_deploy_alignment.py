"""Offline tests: no credentials or network connections are used."""
import contextlib
import io
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "deploy_alignment", Path(__file__).resolve().parent.parent / "scripts/deploy-alignment.py"
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class DeploymentSafeguards(unittest.TestCase):
    def test_exact_login_root(self):
        reply = f'257 "{deploy.DOCUMENT_ROOT}" is current directory'
        with self.assertRaises(deploy.DeploymentError):
            deploy.verified_root(reply)
        self.assertEqual(deploy.verified_root(reply, deploy.DOCUMENT_ROOT), deploy.DOCUMENT_ROOT)

    def test_jailed_root_requires_cpanel_marker(self):
        with self.assertRaises(deploy.DeploymentError):
            deploy.verified_root('257 "/" is current directory')
        self.assertEqual(deploy.verified_root('257 "/"', deploy.DOCUMENT_ROOT + '\n'), '/')

    def test_uncertain_or_main_site_directories_are_rejected(self):
        for path in ['/public_html', '/home/biblbugn', '/home/biblbugn/public_html', '/alignment.bibledavids.org', '/']:
            with self.subTest(path=path), self.assertRaises(deploy.DeploymentError):
                deploy.verified_root(f'257 "{path}"', 'wrong marker')
        with self.assertRaises(deploy.DeploymentError):
            deploy.verified_root('Not a PWD response')
        with self.assertRaises(deploy.DeploymentError):
            deploy.verified_root('257 "/"\n257 "/public_html"', deploy.DOCUMENT_ROOT)

    def test_static_allowlist_excludes_development_and_environment_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ['index.html', 'cover.png', 'README.txt', '.env', '.env.production', '.git/config',
                     '.github/workflows/deploy.yml', 'qa/test.js', 'scripts/build.cjs',
                     'assets/site.css', 'assets/site.js', 'assets/.env.json', 'assets/site.js.map',
                     'assets/node_modules/dev.js', 'locales/en.json']
            for name in names:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture')
            self.assertEqual([p.as_posix() for p in deploy.production_files(root)],
                             ['assets/site.css', 'assets/site.js', 'cover.png', 'index.html', 'locales/en.json'])
            (root / 'assets/linked.js').symlink_to(root / 'index.html')
            with self.assertRaises(deploy.DeploymentError):
                deploy.production_files(root)

    def test_tls_and_non_deleting_mirror(self):
        for setting in ['ftp:ssl-auth TLS', 'ftp:ssl-force yes', 'ftp:ssl-protect-data yes',
                        'ftp:ssl-protect-list yes', 'ssl:verify-certificate yes', 'ssl:check-hostname yes']:
            self.assertIn(setting, deploy.TLS_SETTINGS)
        command = deploy.mirror_command(Path('/tmp/staged-site'))
        self.assertIn('--reverse', command)
        self.assertIn('--overwrite', command)
        self.assertNotIn('--delete', command)
        self.assertNotIn('--no-overwrite', command)

    def test_no_upload_without_approval(self):
        with patch.dict(os.environ, {'DEPLOY_MODE': 'deploy', 'UPLOADS_ENABLED': 'true', 'DEPLOY_APPROVED': ''}, clear=True), patch.object(deploy, 'connect') as connection:
            with self.assertRaises(deploy.DeploymentError):
                deploy.main()
            connection.assert_not_called()

    def test_workflow_upload_lock_overrides_repository_approval(self):
        with patch.dict(os.environ, {'DEPLOY_MODE': 'deploy', 'UPLOADS_ENABLED': 'false', 'DEPLOY_APPROVED': 'true'}, clear=True), patch.object(deploy, 'connect') as connection:
            with self.assertRaises(deploy.DeploymentError):
                deploy.main()
            connection.assert_not_called()

    def test_verify_is_read_only(self):
        environment = {'DEPLOY_MODE': 'verify', 'FTP_SERVER': 'ftp.example.com', 'FTP_USERNAME': 'fixture', 'FTP_PASSWORD': 'fixture'}
        def read_only(server, username, password, command, work):
            if command.startswith('quote PWD'):
                return f'257 "{deploy.DOCUMENT_ROOT}"'
            self.assertTrue(command.startswith('get .alignment-deploy-root -o '))
            (work / 'root-marker').write_text(deploy.DOCUMENT_ROOT)
            return ''
        with patch.dict(os.environ, environment, clear=True), patch.object(deploy, 'connect', side_effect=read_only) as connection:
            with contextlib.redirect_stdout(io.StringIO()):
                deploy.main()
            self.assertEqual(connection.call_count, 2)
            self.assertEqual(connection.call_args_list[0].args[3], 'quote PWD\ncls -1 > /dev/null')

    def test_mismatch_never_reaches_mirror(self):
        environment = {'DEPLOY_MODE': 'deploy', 'UPLOADS_ENABLED': 'true', 'DEPLOY_APPROVED': 'true', 'FTP_SERVER': 'ftp.example.com', 'FTP_USERNAME': 'fixture', 'FTP_PASSWORD': 'fixture'}
        with patch.dict(os.environ, environment, clear=True), patch.object(deploy, 'connect', return_value='257 "/public_html"') as connection:
            with self.assertRaises(deploy.DeploymentError):
                deploy.main()
            self.assertEqual(connection.call_count, 1)

    def test_approved_upload_uses_staging_and_verified_root(self):
        environment = {'DEPLOY_MODE': 'deploy', 'UPLOADS_ENABLED': 'true', 'DEPLOY_APPROVED': 'true', 'FTP_SERVER': 'ftp.example.com', 'FTP_USERNAME': 'fixture', 'FTP_PASSWORD': 'fixture'}
        commands = []
        def connection(server, username, password, command, work):
            commands.append(command)
            if command.startswith('quote PWD\n'):
                return f'257 "{deploy.DOCUMENT_ROOT}"'
            if command.startswith('get .alignment-deploy-root'):
                (work / 'root-marker').write_text(deploy.DOCUMENT_ROOT)
                return ''
            stage = work / 'site'
            self.assertTrue((stage / 'index.html').is_file())
            self.assertTrue((stage / 'assets/i18n.js').is_file())
            self.assertTrue((stage / 'locales/en.json').is_file())
            self.assertFalse((stage / '.github').exists())
            self.assertFalse((stage / 'scripts').exists())
            self.assertFalse((stage / 'qa').exists())
            return ''
        with patch.dict(os.environ, environment, clear=True), patch.object(deploy, 'connect', side_effect=connection), patch.object(deploy, 'verify_published_site') as published, contextlib.redirect_stdout(io.StringIO()):
            deploy.main()
            published.assert_called_once()
        self.assertEqual(len(commands), 3)
        self.assertTrue(commands[2].startswith(f'cd "{deploy.DOCUMENT_ROOT}"\nmirror --reverse'))
        self.assertNotIn('--delete', commands[2])

    def test_credentials_not_in_process_arguments_or_output(self):
        completed = type('Completed', (), {'returncode': 1, 'stdout': 'fixture-secret', 'stderr': 'fixture-secret'})()
        with tempfile.TemporaryDirectory() as temporary, patch.object(deploy.subprocess, 'run', return_value=completed) as run:
            with self.assertRaises(deploy.DeploymentError) as error:
                deploy.connect('ftp.example.com', 'user; injected', 'fixture-secret', 'quote PWD', Path(temporary))
            args, kwargs = run.call_args
            self.assertNotIn('fixture-secret', str(args))
            self.assertNotIn('fixture-secret', str(error.exception))
            self.assertEqual(kwargs['env']['LFTP_PASSWORD'], 'fixture-secret')
            script = (Path(temporary) / 'session.lftp').read_text()
            self.assertIn('ftp://user%3B%20injected@ftp.example.com:21', script)
            self.assertIn('--env-password', script)
            self.assertNotIn('fixture-secret', script)


class ReadOnlyDiagnostics(unittest.TestCase):
    def probe(self, failure_stage=None, failure=None):
        from unittest.mock import MagicMock
        import socket
        ftp = MagicMock()
        if failure_stage in {'connect', 'auth', 'login', 'prot_p', 'retrlines'}:
            getattr(ftp, failure_stage).side_effect = failure
        elif failure_stage is None:
            ftp.retrlines.side_effect = lambda command, callback: callback('PRIVATE_DIRECTORY fixture-secret')
        captured = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(deploy.socket, 'getaddrinfo', side_effect=failure if failure_stage == 'dns' else None,
                                            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.10', 21))]))
            stack.enter_context(patch.object(deploy.socket, 'create_connection', side_effect=failure if failure_stage == 'tcp' else None))
            factory = stack.enter_context(patch.object(deploy, 'DiagnosticFTP', return_value=ftp))
            stack.enter_context(contextlib.redirect_stdout(captured))
            try:
                deploy.diagnose('ftp.example.com', 'fixture-account', 'fixture-secret')
            except deploy.DiagnosticError as error:
                captured.write(str(error))
                result = error.category
            else:
                result = 'OK'
        output = captured.getvalue()
        for private in ['PRIVATE_DIRECTORY', 'fixture-secret', 'fixture-account', '192.0.2.10', 'private server response']:
            self.assertNotIn(private, output)
        return result, ftp, factory, output

    def test_full_read_only_success_discards_listing(self):
        result, ftp, factory, output = self.probe()
        self.assertEqual(result, 'OK')
        self.assertIn('PASSIVE_LIST_OK', output)
        ftp.prot_p.assert_called_once()
        ftp.set_pasv.assert_called_once_with(True)
        self.assertEqual(ftp.retrlines.call_args.args, ('LIST',))
        ftp.storbinary.assert_not_called()
        ftp.delete.assert_not_called()
        ftp.cwd.assert_not_called()
        ftp.set_debuglevel.assert_called_once_with(0)
        context = factory.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, deploy.ssl.CERT_REQUIRED)
        self.assertIsNone(context.keylog_filename)

    def test_dns_failure(self):
        result, ftp, _, _ = self.probe('dns', deploy.socket.gaierror('private server response'))
        self.assertEqual(result, 'DNS_FAILED')
        ftp.login.assert_not_called()

    def test_control_port_failures(self):
        for error, expected in [(TimeoutError('private server response'), 'TCP_21_TIMEOUT'),
                                (ConnectionRefusedError(deploy.errno.ECONNREFUSED, 'private server response'), 'TCP_21_REFUSED')]:
            with self.subTest(expected=expected):
                result, ftp, _, _ = self.probe('tcp', error)
                self.assertEqual(result, expected)
                ftp.auth.assert_not_called()

    def test_greeting_failure(self):
        self.assertEqual(self.probe('connect', EOFError('private server response'))[0], 'FTP_GREETING_FAILED')

    def test_certificate_mismatch_stops_before_credentials(self):
        error = deploy.ssl.SSLCertVerificationError(1, 'private server response')
        error.verify_code = 62
        result, ftp, _, _ = self.probe('auth', error)
        self.assertEqual(result, 'CERTIFICATE_HOSTNAME_MISMATCH')
        ftp.login.assert_not_called()
        ftp.retrlines.assert_not_called()
        ftp.close.assert_called_once()

    def test_chain_failure(self):
        error = deploy.ssl.SSLCertVerificationError(1, 'private server response')
        error.verify_code = 20
        self.assertEqual(self.probe('auth', error)[0], 'CERTIFICATE_INVALID')

    def test_tls_negotiation_failures(self):
        self.assertEqual(self.probe('auth', deploy.ftplib.error_perm('500 private server response'))[0], 'AUTH_TLS_UNAVAILABLE')
        self.assertEqual(self.probe('auth', deploy.ssl.SSLError('private server response'))[0], 'TLS_NEGOTIATION_FAILED')

    def test_login_rejection_is_not_reported_as_bad_password(self):
        result, ftp, _, output = self.probe('login', deploy.ftplib.error_perm('530 private server response'))
        self.assertEqual(result, 'AUTHENTICATION_REJECTED')
        self.assertNotIn('incorrect password', output)
        ftp.retrlines.assert_not_called()

    def test_passive_stage_failures(self):
        failures = [
            (TimeoutError('private server response'), 'PASSIVE_DATA_TIMEOUT'),
            (deploy.ssl.SSLError('private server response'), 'PASSIVE_TLS_FAILED'),
            (deploy.ftplib.error_perm('550 private server response'), 'PASSIVE_LIST_DENIED'),
            (deploy.ftplib.error_perm('522 private server response'), 'PASSIVE_TLS_FAILED'),
            (deploy.ftplib.error_temp('425 private server response'), 'PASSIVE_DATA_CONNECTION_FAILED'),
            (deploy.ftplib.error_proto('private server response'), 'PASSIVE_LIST_FAILED'),
        ]
        for error, expected in failures:
            with self.subTest(expected=expected):
                self.assertEqual(self.probe('retrlines', error)[0], expected)
        self.assertEqual(self.probe('prot_p', deploy.ftplib.error_perm('private server response'))[0], 'PASSIVE_PROTECTION_FAILED')

    def test_cloudflare_classification_does_not_expose_addresses(self):
        self.assertTrue(deploy.cloudflare_edge_match({'104.16.0.1'}))
        self.assertTrue(deploy.cloudflare_edge_match({'2606:4700::1'}))
        self.assertFalse(deploy.cloudflare_edge_match({'192.0.2.10'}))

    def test_diagnostic_mode_never_stages_or_uses_upload_client(self):
        environment = {'DEPLOY_MODE': 'verify', 'UPLOADS_ENABLED': 'false', 'FTP_SERVER': 'ftp.example.com',
                       'FTP_USERNAME': 'fixture', 'FTP_PASSWORD': 'fixture'}
        with patch.dict(os.environ, environment, clear=True), patch.object(deploy, 'diagnose') as probe, patch.object(deploy, 'production_files') as stage, patch.object(deploy, 'connect') as transfer:
            deploy.main(diagnostic=True)
            probe.assert_called_once()
            stage.assert_not_called()
            transfer.assert_not_called()

    def test_data_tls_reuses_validating_context_and_session(self):
        from unittest.mock import MagicMock
        ftp = deploy.DiagnosticFTP(context=deploy.ssl.create_default_context())
        ftp.host = 'ftp.example.com'
        ftp.sock = MagicMock()
        ftp._prot_p = True
        raw = MagicMock()
        with patch.object(deploy.ftplib.FTP, 'ntransfercmd', return_value=(raw, None)), patch.object(ftp.context, 'wrap_socket') as wrap:
            ftp.ntransfercmd('LIST')
            wrap.assert_called_once_with(raw, server_hostname='ftp.example.com', session=ftp.sock.session)
        self.assertTrue(ftp.context.check_hostname)
        self.assertEqual(ftp.context.verify_mode, deploy.ssl.CERT_REQUIRED)

    def test_workflow_is_read_only_and_diagnostics_are_separate(self):
        workflow = (deploy.ROOT / '.github/workflows/deploy-alignment.yml').read_text()
        self.assertIn("UPLOADS_ENABLED: 'false'", workflow)
        self.assertIn("inputs.mode == 'deploy' && 'deploy' || 'verify'", workflow)
        self.assertIn('options: [verify, diagnose, inspect-root, deploy]', workflow)
        self.assertNotIn('\n  push:', workflow)
        self.assertIn("github.ref == 'refs/heads/dev'", workflow)
        self.assertIn("inputs.confirmation == 'DEPLOY ALIGNMENT'", workflow)
        self.assertIn('default: verify', workflow)
        self.assertIn('scripts/deploy-alignment.py --diagnose', workflow)
        self.assertNotIn('vars.ALIGNMENT_DEPLOY_APPROVED', workflow)
        self.assertIn("github.ref == 'refs/heads/zeals'", workflow)
        import textwrap
        import subprocess
        body = textwrap.dedent(workflow.rsplit('        run: |\n', 1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / 'python3'
            executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            executable.chmod(0o700)
            environment = {'PATH': temporary, 'FTPS_DIAGNOSTIC': 'true', 'DEPLOY_MODE': 'verify', 'UPLOADS_ENABLED': 'false'}
            result = subprocess.run(['/bin/bash', '-e', '-c', body], env=environment, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ['-B', 'scripts/deploy-alignment.py', '--diagnose'])
            environment['FTPS_DIAGNOSTIC'] = 'false'
            environment['FTPS_ROOT_INSPECTION'] = 'true'
            result = subprocess.run(['/bin/bash', '-e', '-c', body], env=environment, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ['-B', 'scripts/deploy-alignment.py', '--inspect-root'])




class PublishedSiteVerification(unittest.TestCase):
    def test_root_index_and_public_https_must_match(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / 'index.html'
            remote = Path(directory) / 'downloaded-index.html'
            local.write_bytes(b'<html>ALIGNMENT</html>')
            remote.write_bytes(local.read_bytes())
            response = MagicMock()
            response.status = 200
            response.geturl.return_value = deploy.PUBLIC_URL
            response.read.return_value = local.read_bytes()
            context = MagicMock()
            context.__enter__.return_value = response
            with patch.object(deploy, 'urlopen', return_value=context), contextlib.redirect_stdout(io.StringIO()):
                deploy.verify_published_site(local, remote)
            remote.write_bytes(b'wrong index')
            with self.assertRaises(deploy.DeploymentError), patch.object(deploy, 'urlopen') as request:
                deploy.verify_published_site(local, remote)
            request.assert_not_called()
            remote.write_bytes(local.read_bytes())
            response.read.return_value = b'stale cached page'
            with patch.object(deploy, 'urlopen', return_value=context), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(deploy.DeploymentError):
                deploy.verify_published_site(local, remote)


class MarkerInspection(unittest.TestCase):
    def test_marker_newlines_are_already_accepted(self):
        for suffix in ['', '\n', '\r\n', '\n\n', ' \t\r\n']:
            self.assertEqual(deploy.marker_format((deploy.DOCUMENT_ROOT + suffix).encode()), (True, 'ACCEPTED'))
            self.assertEqual(deploy.verified_root('257 "/"', deploy.DOCUMENT_ROOT + suffix), '/')

    def test_marker_formats_are_diagnosed_without_relaxing_comparison(self):
        for value, expected in [(b'\xef\xbb\xbf' + deploy.DOCUMENT_ROOT.encode(), 'UTF8_BOM'),
                                ((deploy.DOCUMENT_ROOT + '/').encode(), 'TRAILING_SLASH'),
                                (('"' + deploy.DOCUMENT_ROOT + '"').encode(), 'QUOTED_PATH'),
                                (b'PRIVATE_WRONG_DIRECTORY', 'WRONG_VALUE'), (b'\xff', 'INVALID_UTF8')]:
            self.assertEqual(deploy.marker_format(value), (False, expected))

    def inspection(self, contents=None, error=None, size=None, root='/'):
        from unittest.mock import MagicMock
        ftp = MagicMock()
        ftp.pwd.return_value = root
        ftp.size.return_value = size
        if error:
            ftp.retrbinary.side_effect = error
        else:
            ftp.retrbinary.side_effect = lambda command, callback, **kwargs: callback(contents or b'')
        output = io.StringIO()
        with patch.object(deploy, 'DiagnosticFTP', return_value=ftp), contextlib.redirect_stdout(output):
            result = deploy.inspect_root('ftp.example.com', 'PRIVATE_ACCOUNT', 'PRIVATE_PASSWORD')
        for secret in ['PRIVATE_ACCOUNT', 'PRIVATE_PASSWORD', 'PRIVATE_WRONG_DIRECTORY', 'PRIVATE_SERVER_REPLY']:
            self.assertNotIn(secret, output.getvalue())
        for method in ['storbinary', 'delete', 'mkd', 'cwd', 'dir', 'nlst']:
            getattr(ftp, method).assert_not_called()
        ftp.close.assert_called_once()
        return result, output.getvalue(), ftp

    def test_inspection_reads_named_marker_only(self):
        result, output, ftp = self.inspection((deploy.DOCUMENT_ROOT + '\r\n').encode())
        self.assertTrue(result)
        self.assertIn('FTP_ROOT: /', output)
        self.assertIn('MARKER_EXISTS: true', output)
        self.assertIn('MARKER_CONTENT_MATCH: true', output)
        self.assertIn('ROOT_VALIDATION: passed', output)
        self.assertIn('JAIL_MAPPING: cpanel_confirmation_required', output)
        self.assertEqual(ftp.retrbinary.call_args.args[0], 'RETR .alignment-deploy-root')

    def test_missing_denied_and_transfer_failures_are_distinct(self):
        for error, size, expected in [
            (deploy.ftplib.error_perm('550 No such file PRIVATE_SERVER_REPLY'), None, 'MARKER_NOT_FOUND'),
            (deploy.ftplib.error_perm('550 denied PRIVATE_SERVER_REPLY'), 10, 'MARKER_ACCESS_DENIED_OR_UNAVAILABLE'),
            (deploy.ssl.SSLError('PRIVATE_SERVER_REPLY'), 10, 'MARKER_DATA_TLS_FAILED'),
            (TimeoutError('PRIVATE_SERVER_REPLY'), 10, 'MARKER_READ_TIMEOUT'),
        ]:
            with self.subTest(expected=expected):
                result, output, _ = self.inspection(error=error, size=size)
                self.assertFalse(result)
                self.assertIn('ROOT_REASON: ' + expected, output)
                self.assertIn('MARKER_CONTENT_MATCH: unknown', output)

    def test_inspection_rejects_unrelated_root_without_reading_marker(self):
        result, output, ftp = self.inspection(root='/PRIVATE_WRONG_DIRECTORY')
        self.assertFalse(result)
        self.assertIn('FTP_ROOT: unexpected', output)
        ftp.retrbinary.assert_not_called()

    def test_root_inspection_does_not_stage_or_call_upload_client(self):
        environment = {'DEPLOY_MODE': 'verify', 'UPLOADS_ENABLED': 'false', 'FTP_SERVER': 'ftp.example.com',
                       'FTP_USERNAME': 'fixture', 'FTP_PASSWORD': 'fixture'}
        with patch.dict(os.environ, environment, clear=True), patch.object(deploy, 'inspect_root', return_value=True) as inspect, patch.object(deploy, 'production_files') as stage, patch.object(deploy, 'connect') as transfer:
            self.assertTrue(deploy.main(root_inspection=True))
            inspect.assert_called_once()
            stage.assert_not_called()
            transfer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
