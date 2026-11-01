import importlib.util, os, pathlib, tempfile, unittest
from unittest.mock import patch
os.environ['CLOUDMATE_TOKEN']='test-token'
os.environ['CLOUDMATE_DATA']=tempfile.mkdtemp()
spec=importlib.util.spec_from_file_location('cloudmate_server',pathlib.Path(__file__).resolve().parents[1]/'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class DeployTests(unittest.TestCase):
    def job(self):
        return dict(id='abcdef123456',repo='https://github.com/example/app',branch='main',runtime='auto',port=3000,hostPort=8080,status='Queued',logs='')
    def test_success_clones_builds_and_runs(self):
        j=self.job(); commands=[]
        def fake(job,args,cwd=None,timeout=600):
            commands.append(args)
            if 'clone' in args:
                p=pathlib.Path(args[-1]);p.mkdir(exist_ok=True);(p/'Dockerfile').write_text('FROM scratch')
            if args[:2]==['docker','inspect']:return 'true'
            if args[:2]==['docker','run']:return 'container-id'
            return ''
        with patch.object(s,'run',side_effect=fake),patch.object(s.time,'sleep'):
            s.deploy(j)
        self.assertEqual(j['status'],'Running');self.assertEqual(j['container'],'container-id')
        self.assertTrue(any(c[:2]==['docker','build'] for c in commands))
        c=next(c for c in commands if c[:2]==['docker','run']);self.assertIn('8080:3000',c)
    def test_clone_failure_does_not_start_container(self):
        j=self.job()
        with patch.object(s,'run',side_effect=RuntimeError('clone failed')) as run:s.deploy(j)
        self.assertEqual(j['status'],'Failed');self.assertIn('clone failed',j['logs']);self.assertEqual(run.call_count,1)
    def test_exited_container_is_failure(self):
        j=self.job();j['id']='111111111111';j['runtime']='docker'
        def fake(job,args,**kw):return 'false' if args[:2]==['docker','inspect'] else 'id'
        with patch.object(s,'run',side_effect=fake),patch.object(s.time,'sleep'):s.deploy(j)
        self.assertEqual(j['status'],'Failed');self.assertIn('Container exited',j['logs'])
if __name__=='__main__':unittest.main()
