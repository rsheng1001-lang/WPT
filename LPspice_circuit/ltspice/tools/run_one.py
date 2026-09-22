"""Run real LTspice batch mode with a bounded wait; never launch a visible helper."""
from pathlib import Path
import subprocess, sys, time, json
root = Path(__file__).resolve().parent.parent   # ltspice/
exe = Path('D:/Program Files/LTspice/LTspice.exe')
target = Path(sys.argv[1])
timeout = float(sys.argv[2]) if len(sys.argv)>2 else 120
start=time.time()
p=subprocess.run([str(exe), '-b', str(target)], cwd=root, timeout=timeout,
                 creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
print(json.dumps({'target':str(target),'exit_code':p.returncode,'seconds':time.time()-start}))
log=(root/target).with_suffix('.log')
if log.exists():
    data=log.read_bytes()
    text=data.decode('utf-16') if data.startswith(b'\xff\xfe') else data.decode('utf-8',errors='replace')
    print(text[-18000:])
else:
    print('NO LOG',p.stdout,p.stderr)
