#!/usr/bin/env python3
"""CloudMate P2C server. Run on the Linux Docker host: python3 server.py."""
import concurrent.futures, http.server, json, os, pathlib, re, secrets, subprocess, threading, time, urllib.parse, uuid
ROOT = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get('CLOUDMATE_DATA', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get('CLOUDMATE_TOKEN')
if not TOKEN:
    raise SystemExit('Set CLOUDMATE_TOKEN to a long random secret before starting.')
ORIGIN = os.environ.get('CLOUDMATE_ORIGIN', '')
LOCK = threading.Lock()
JOBS = {}
POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def run(job, args, cwd=None, timeout=600):
    with LOCK: job['logs'] += '$ ' + ' '.join(args) + '\n'
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    with LOCK: job['logs'] = (job['logs'] + result.stdout)[-100000:]
    if result.returncode: raise RuntimeError('Command failed (exit %s)' % result.returncode)
    return result.stdout.strip()

def deploy(job):
    work = DATA / job['id']
    try:
        with LOCK: job['status'] = 'Cloning'
        run(job, ['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--depth', '1', '--branch', job['branch'], '--', job['repo'] + '.git', str(work)], timeout=120)
        kind = job['runtime']
        if kind == 'auto':
            kind = 'docker' if (work/'Dockerfile').is_file() else 'node' if (work/'package.json').is_file() else 'python' if (work/'requirements.txt').is_file() else ''
        if not kind: raise RuntimeError('Runtime not detected. Add a Dockerfile or select a runtime.')
        job['detectedRuntime'] = kind
        dockerfile = 'Dockerfile'
        if kind == 'node':
            if not (work/'package-lock.json').is_file(): raise RuntimeError('Node deployment requires package-lock.json, or provide a Dockerfile.')
            content = 'FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\nCOPY . .\nRUN npm run build --if-present\nENV NODE_ENV=production\nENV HOSTNAME=0.0.0.0\nENV PORT=%s\nEXPOSE %s\nCMD ["npm", "start"]\n' % (job['port'], job['port'])
        elif kind == 'python':
            content = 'FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt ./\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nEXPOSE %s\nCMD ["python", "app.py"]\n' % job['port']
        else: content = None
        if content:
            dockerfile = 'Dockerfile.cloudmate'
            target = work/dockerfile
            if target.is_symlink(): raise RuntimeError('Generated Dockerfile path is a symlink.')
            target.write_text(content)
        with LOCK: job['status'] = 'Building'
        image = 'cloudmate:' + job['id']
        run(job, ['docker', 'build', '-f', dockerfile, '-t', image, '.'], cwd=work)
        with LOCK: job['status'] = 'Starting'
        name = 'cloudmate-' + job['id']
        cid = run(job, ['docker', 'run', '-d', '--name', name, '--label', 'cloudmate.managed=true', '--restart', 'unless-stopped', '--memory', '512m', '--cpus', '1', '--security-opt', 'no-new-privileges', '-p', '%s:%s' % (job['hostPort'],job['port']), image], timeout=45)
        with LOCK: job['container'] = cid
        time.sleep(2)
        state = run(job, ['docker', 'inspect', '--format', '{{.State.Running}}', cid], timeout=15)
        run(job, ['docker', 'logs', '--tail', '100', cid], timeout=15)
        if state != 'true': raise RuntimeError('Container exited. See application logs.')
        with LOCK: job['status'] = 'Running'
    except Exception as e:
        with LOCK:
            job['status'] = 'Failed'
            job['logs'] += '\n' + str(e) + '\n'

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'dist'),**kw)
    def end_headers(self):
        origin = self.headers.get('Origin','')
        if ORIGIN and origin == ORIGIN:
            self.send_header('Access-Control-Allow-Origin', ORIGIN)
            self.send_header('Vary','Origin')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def reply(self, value, status=200):
        data=json.dumps(value).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def auth(self):
        if not secrets.compare_digest(self.headers.get('Authorization',''), 'Bearer '+TOKEN):
            self.reply({'error':'Invalid server token'},401); return False
        origin=self.headers.get('Origin','')
        own=urllib.parse.urlparse(origin).netloc == self.headers.get('Host')
        if origin and not own and origin != ORIGIN:
            self.reply({'error':'Origin not allowed'},403); return False
        return True
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type'); self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS'); self.end_headers()
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path
        if not path.startswith('/api/'):
            if path not in ['/', '/index.html', '/app.js', '/style.css', '/cloudmate-p2c-server.zip']: self.send_error(404); return
            return super().do_GET()
        if not self.auth(): return
        if path == '/api/health':
            try:
                result=subprocess.run(['docker','info','--format','{{.ServerVersion}}'],capture_output=True,text=True,timeout=10)
                self.reply({'docker':result.returncode==0,'version':result.stdout.strip()})
            except (OSError,subprocess.TimeoutExpired): self.reply({'docker':False,'version':''})
        elif path == '/api/projects':
            with LOCK: value=json.loads(json.dumps(list(JOBS.values())))
            self.reply(value)
        elif re.fullmatch(r'/api/projects/[a-f0-9]{12}/logs',path):
            job=JOBS.get(path.split('/')[3])
            if not job: return self.reply({'error':'Not found'},404)
            live=''
            if job.get('container'):
                try: live=subprocess.run(['docker','logs','--tail','150',job['container']],capture_output=True,text=True,timeout=10).stdout
                except (OSError,subprocess.TimeoutExpired): pass
            self.reply({'logs':job['logs']+'\n'+live})
        else: self.reply({'error':'Not found'},404)
    def do_POST(self):
        if not self.auth(): return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<1 or length>8192: return self.reply({'error':'Invalid request size'},400)
            body=json.loads(self.rfile.read(length))
            path=urllib.parse.urlparse(self.path).path
            if path=='/api/projects':
                repo=str(body.get('repo','')).rstrip('/').removesuffix('.git')
                branch=str(body.get('branch','main')); runtime=body.get('runtime','auto')
                port=int(body.get('port',3000)); hostport=int(body.get('hostPort',3000))
                if not re.fullmatch(r'https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',repo): raise ValueError('Use a public github.com repository URL')
                if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]{0,150}',branch) or '..' in branch: raise ValueError('Invalid branch')
                if runtime not in ['auto','node','python','docker']: raise ValueError('Invalid runtime')
                if not (1<=port<=65535 and 1024<=hostport<=65535): raise ValueError('Invalid ports; host port must be 1024 or higher')
                with LOCK:
                    if len(JOBS)>=100: return self.reply({'error':'Project limit reached; restart to clear history'},409)
                    if any(j['hostPort']==hostport and j['status'] not in ['Failed','Stopped'] for j in JOBS.values()): return self.reply({'error':'Host port already assigned'},409)
                    job={'id':uuid.uuid4().hex[:12],'name':repo.split('/')[-1],'repo':repo,'branch':branch,'runtime':runtime,'port':port,'hostPort':hostport,'status':'Queued','logs':'','created':time.time()}
                    JOBS[job['id']]=job
                POOL.submit(deploy,job); self.reply(job,202)
            elif re.fullmatch(r'/api/projects/[a-f0-9]{12}/stop',path):
                job=JOBS.get(path.split('/')[3])
                if not job or not job.get('container'): return self.reply({'error':'No container to stop'},404)
                run(job,['docker','stop',job['container']],timeout=30)
                with LOCK: job['status']='Stopped'
                self.reply({'ok':True})
            else: self.reply({'error':'Not found'},404)
        except (ValueError,TypeError,json.JSONDecodeError) as e: self.reply({'error':str(e)},400)
        except Exception as e: self.reply({'error':str(e)},500)

if __name__=='__main__':
    print('CloudMate P2C: http://%s:%s' % (os.environ.get('CLOUDMATE_BIND','127.0.0.1'),os.environ.get('PORT','8787')),flush=True)
    http.server.ThreadingHTTPServer((os.environ.get('CLOUDMATE_BIND','127.0.0.1'),int(os.environ.get('PORT','8787'))),Handler).serve_forever()
