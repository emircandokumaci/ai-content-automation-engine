#!/usr/bin/env python3
import os,sys,json,base64,urllib.request,urllib.error,time
req=json.load(open(sys.argv[1]))
allowed={'job_id','scene_id','asset_id','asset_path','generation_prompt','negative_constraints'}
r={k:req.get(k) for k in allowed}
for forbidden in ('full_script','full_manifest','other_scene_prompts','previous_response_id','conversation_id','storyboard'):
 if forbidden in req: raise SystemExit('FORBIDDEN_CONTEXT:'+forbidden)
key=os.environ.get('OPENAI_API_KEY')
if not key: raise SystemExit('OPENAI_API_KEY_MISSING')
prompt=(r['generation_prompt'] or '').strip()
neg=r.get('negative_constraints') or []
if neg: prompt += '\nConstraints: ' + '; '.join(map(str,neg))
body=json.dumps({'model':os.environ.get('JARVIS_IMAGE_MODEL','gpt-image-2.5-flare'),'prompt':prompt,'n':1,'size':'1024x1536'}).encode()
request=urllib.request.Request('https://api.openai.com/v1/images/generations',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
for attempt in range(4):
 try:
  with urllib.request.urlopen(request,timeout=180) as resp: data=json.load(resp)
  item=data['data'][0]; raw=base64.b64decode(item['b64_json']) if item.get('b64_json') else None
  if raw is None: raise RuntimeError('NO_IMAGE_BYTES')
  p=r['asset_path']; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(raw)
  print(json.dumps({'status':'GENERATED','scene_id':r['scene_id'],'asset_path':p})); raise SystemExit(0)
 except urllib.error.HTTPError as e:
  if e.code==429 or 500<=e.code<600:
   time.sleep(min(30,2**attempt)); continue
  raise
raise SystemExit('IMAGE_API_RETRY_EXHAUSTED')
