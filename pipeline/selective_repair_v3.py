#!/usr/bin/env python3
import json,subprocess,sys
manifest=sys.argv[1]
p=subprocess.run(['/opt/jarvis/v3/bin/asset_gate_v3.py',manifest],capture_output=True,text=True)
r=json.loads(p.stdout)
if r['status']=='PASS':
    print(json.dumps({'status':'PASS','requests':[]}))
    raise SystemExit(0)
bad=[x['scene_id'] for x in r['scenes'] if x['qc_status']!='PASS']
ids=','.join(str(int(x.split('_')[-1])) for x in bad)
d=subprocess.run(['/opt/jarvis/video-engine/bin/scene_dispatcher.py',manifest,ids],capture_output=True,text=True)
if d.returncode:
    print(d.stdout+d.stderr,file=sys.stderr)
    raise SystemExit(d.returncode)
print(json.dumps({'status':'REPAIR_REQUIRED','bad_scenes':bad,'dispatcher':json.loads(d.stdout)}))
raise SystemExit(42)
