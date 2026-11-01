import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

os.environ['CLOUDMATE_TOKEN'] = 'test-token'
os.environ['CLOUDMATE_DATA'] = tempfile.mkdtemp()
spec = importlib.util.spec_from_file_location('cloudmate_server', pathlib.Path(__file__).resolve().parents[1] / 'server.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_patch = patch.object(s, 'DATA', pathlib.Path(self.temp.name))
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)

    def config(self, **values):
        return s.deployment_config({'repo': 'https://github.com/example/tool', **values})

    def job(self, **values):
        return {**self.config(runtime='docker', **values), 'id': 'abcdef123456', 'status': 'Queued', 'logs': ''}

    def exercise(self, job, running=True, exit_code=0):
        commands = []
        def fake(job, args, cwd=None, timeout=600):
            commands.append(args)
            if 'clone' in args:
                work = pathlib.Path(args[-1])
                work.mkdir()
                (work / 'Dockerfile').write_text('FROM scratch')
            if args[:2] == ['docker', 'inspect']:
                return json.dumps({'Running': running, 'ExitCode': exit_code})
            if args[:2] == ['docker', 'run']:
                return 'container-id'
            return ''
        with patch.object(s, 'run', side_effect=fake), patch.object(s.time, 'sleep'):
            s.deploy(job)
        return commands

    def test_tool_is_default_without_ports(self):
        config = self.config()
        self.assertEqual(config['mode'], 'tool')
        self.assertIsNone(config['port'])
        self.assertIsNone(config['hostPort'])

    def test_tool_run_has_no_port_mapping_or_restart_loop(self):
        job = self.job(arguments=['--name', 'hello world', '$(touch /tmp/not-executed)'])
        commands = self.exercise(job)
        run = next(c for c in commands if c[:2] == ['docker', 'run'])
        self.assertNotIn('-p', run)
        self.assertEqual(run[run.index('--restart') + 1], 'no')
        self.assertEqual(run[-3:], job['arguments'])
        self.assertEqual(job['status'], 'Running')

    def test_dashboard_publishes_requested_port(self):
        job = self.job(mode='dashboard', port=9000, hostPort=8080)
        run = next(c for c in self.exercise(job) if c[:2] == ['docker', 'run'])
        self.assertIn('8080:9000', run)
        self.assertEqual(run[run.index('--restart') + 1], 'unless-stopped')
        self.assertEqual(job['status'], 'Running')

    def test_successful_one_shot_is_completed(self):
        job = self.job()
        self.exercise(job, running=False, exit_code=0)
        self.assertEqual(job['status'], 'Completed')
        self.assertEqual(job['exitCode'], 0)

    def test_nonzero_tool_exit_fails(self):
        job = self.job()
        self.exercise(job, running=False, exit_code=2)
        self.assertEqual(job['status'], 'Failed')
        self.assertEqual(job['exitCode'], 2)

    def test_exited_dashboard_is_not_successful_one_shot(self):
        job = self.job(mode='dashboard')
        self.exercise(job, running=False, exit_code=0)
        self.assertEqual(job['status'], 'Failed')

    def test_clone_failure_does_not_start_container(self):
        job = self.job()
        with patch.object(s, 'run', side_effect=RuntimeError('clone failed')) as run:
            s.deploy(job)
        self.assertEqual(job['status'], 'Failed')
        self.assertIn('clone failed', job['logs'])
        self.assertEqual(run.call_count, 1)

    def test_dashboard_ports_are_validated(self):
        for values in ({'port': 0}, {'hostPort': 80}, {'hostPort': True}, {'port': '3000'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.config(mode='dashboard', **values)

    def test_binary_path_is_required_and_relative(self):
        for path in ('', '../tool', '/bin/tool', 'bin/../tool', 'bin/*', 'bin/tool;id'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.config(runtime='binary', binaryPath=path)

    def test_arguments_must_be_strings_not_shell_input(self):
        for arguments in ('--help', [1], ['bad\x00value'], ['x'] * 65):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.config(arguments=arguments)

    def binary_work(self):
        work = s.DATA / 'source'
        (work / 'bin').mkdir(parents=True)
        (work / 'bin/tool').write_bytes(b'\x7fELFfixture')
        return work

    def test_binary_template_has_entrypoint_and_no_exposed_port(self):
        work = self.binary_work()
        job = self.config(runtime='binary', binaryPath='bin/tool')
        name = s.prepare_dockerfile(job, work)
        content = (work / name).read_text()
        self.assertIn('ENTRYPOINT ["/usr/local/bin/cloudmate-tool"]', content)
        self.assertIn('COPY ["bin/tool", "/usr/local/bin/cloudmate-tool"]', content)
        self.assertNotIn('EXPOSE', content)
        self.assertIn('USER 65532:65532', content)

    def test_binary_dashboard_template_exposes_port(self):
        work = self.binary_work()
        job = self.config(runtime='binary', binaryPath='bin/tool', mode='dashboard', port=9000)
        self.assertIn('EXPOSE 9000', (work / s.prepare_dockerfile(job, work)).read_text())

    def test_binary_file_must_exist_and_be_linux_elf(self):
        work = self.binary_work()
        job = self.config(runtime='binary', binaryPath='bin/missing')
        with self.assertRaisesRegex(RuntimeError, 'not found'):
            s.prepare_dockerfile(job, work)
        (work / 'bin/tool').write_bytes(b'MZwindows')
        job['binaryPath'] = 'bin/tool'
        with self.assertRaisesRegex(RuntimeError, 'Linux ELF'):
            s.prepare_dockerfile(job, work)

    def test_binary_symlink_is_rejected(self):
        work = self.binary_work()
        (work / 'bin/link').symlink_to('tool')
        with self.assertRaisesRegex(RuntimeError, 'symlinks'):
            s.prepare_dockerfile(self.config(runtime='binary', binaryPath='bin/link'), work)

    def test_explicit_binary_path_can_be_detected_automatically(self):
        work = self.binary_work()
        job = self.config(binaryPath='bin/tool')
        s.prepare_dockerfile(job, work)
        self.assertEqual(job['detectedRuntime'], 'binary')

    def test_running_tool_reconciles_completion_on_poll(self):
        job = self.job()
        job.update(status='Running', container='container-id')
        result = type('Result', (), {'returncode': 0, 'stdout': '{"Running": false, "ExitCode": 0}'})()
        with patch.object(s.subprocess, 'run', return_value=result):
            s.refresh_state(job)
        self.assertEqual(job['status'], 'Completed')

    def test_stop_is_preserved_during_state_reconciliation(self):
        job = self.job()
        job['status'] = 'Stopped'
        s.record_state(job, {'Running': False, 'ExitCode': 0})
        self.assertEqual(job['status'], 'Stopped')

    def test_invalid_mode_and_non_object_payload_are_rejected(self):
        with self.assertRaises(ValueError):
            self.config(mode='unknown')
        with self.assertRaises(ValueError):
            s.deployment_config([])


if __name__ == '__main__':
    unittest.main()
