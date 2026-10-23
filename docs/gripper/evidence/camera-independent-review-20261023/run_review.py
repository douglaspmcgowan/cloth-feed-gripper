"""Own only this review's server; preserve other processes and exact evidence bytes."""
from pathlib import Path
import datetime, json, os, subprocess, sys, time, urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PWSH = r'C:/Program Files/PowerShell/7/pwsh.exe'
GATE = r'C:/Users/dougl/.agents/tools/Invoke-HeavyTestAdmission.ps1'
proof = ('python cad/gripper/tests/test_viewer_fit_framing.py --url http://127.0.0.1:4200/cad/gripper/viewer.html '
         '--dependency-dir C:/Users/dougl/Projects/product-design-system/gripper-ui-fixture/package '
         '--cached-module C:/Users/dougl/Projects/product-design-system/gripper-ui-runtime/cdn-three.module.min.js '
         '--playwright-module C:/Users/dougl/Worktrees/product-design-system/pds-ux-linked-selection-20261022/studio/web/node_modules/@playwright/test/index.js '
         '--browser-channel chrome --output docs/gripper/evidence/camera-independent-review-20261023/browser')
receipt = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'commands': [], 'cleanup': {}}
server = None
try:
    with (OUT/'server.log').open('w',encoding='utf8') as log:
        server = subprocess.Popen([sys.executable,'-m','http.server','4200','--bind','127.0.0.1','--directory',str(ROOT)], cwd=ROOT,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        receipt['server_pid'] = server.pid
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError('Owned server exited; do not use a collided server')
            try:
                with urllib.request.urlopen('http://127.0.0.1:4200/cad/gripper/viewer.html',timeout=1) as r:
                    if r.status == 200: break
            except Exception: time.sleep(.2)
        else: raise RuntimeError('Owned server never became reachable')
        for name, command, timeout in [('focused-browser', proof, 660), ('independent-browser', 'node docs/gripper/evidence/camera-independent-review-20261023/independent.cjs', 420)]:
            started = time.monotonic()
            result = subprocess.run([PWSH,'-NoProfile','-NonInteractive','-File',GATE,'-Command',command,'-Run'],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
            (OUT/(name+'.stdout.txt')).write_text(result.stdout,encoding='utf8')
            (OUT/(name+'.stderr.txt')).write_text(result.stderr,encoding='utf8')
            receipt['commands'].append({'name':name,'command':command,'admission':GATE,'exit':result.returncode,'elapsed_seconds':round(time.monotonic()-started,3)})
            print(name, result.returncode, result.stdout[-1000:], result.stderr[-1500:],flush=True)
except Exception as e:
    receipt['error'] = repr(e)
    print(repr(e),flush=True)
finally:
    if server is not None:
        if server.poll() is None: server.terminate()
        try: server.wait(timeout=10)
        except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
        receipt['cleanup'] = {'owned_server_pid':server.pid,'owned_server_exited':server.poll() is not None,'server_exit':server.returncode,'other_processes_touched':False}
    receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT/'execution.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
