#!/usr/bin/env python3
import json,sys,math,re
from pathlib import Path
TRANSITION=.22
if len(sys.argv)!=2:raise SystemExit('usage: validate_manifest_v3.py manifest.json')
p=Path(sys.argv[1])
try:m=json.loads(p.read_text(encoding='utf-8'))
except Exception:print(json.dumps({'status':'FAIL','errors':['invalid_json']}));raise SystemExit(43)
errors=[];scenes=m.get('scenes') or [];job=str(m.get('id') or m.get('job_id') or '').strip()
if not re.fullmatch(r'[A-Za-z0-9._-]{1,180}',job):errors.append('invalid_job_id')
if not 10<=len(scenes)<=14:errors.append('scene_count_must_be_10_14')
seen=set();total=0.0;asset_root=(Path('/opt/jarvis/v3/artifacts')/job/'assets').resolve() if job else None
for i,s in enumerate(scenes,1):
    sid=s.get('scene_id') or f'scene_{i:02d}'
    for key in ('asset','prompt','caption','duration'):
        if s.get(key) in (None,''):errors.append(f'{sid}:missing_{key}')
    if sid in seen:errors.append(f'{sid}:duplicate_scene_id')
    seen.add(sid)
    if not re.fullmatch(r'scene_\d{2}',str(sid)):errors.append(f'{sid}:invalid_scene_id')
    try:
        d=float(s.get('duration'));total+=d
        if not math.isfinite(d) or not .7<=d<=6:errors.append(f'{sid}:duration_out_of_range')
    except:errors.append(f'{sid}:duration_invalid')
    cap=' '.join(str(s.get('caption') or '').split())
    if len(cap)>180:errors.append(f'{sid}:caption_too_long')
    prompt=' '.join(str(s.get('prompt') or '').split())
    if len(prompt)<20:errors.append(f'{sid}:prompt_too_short')
    try:
        ap=Path(str(s.get('asset') or '')).resolve()
        if not asset_root or ap.parent!=asset_root:errors.append(f'{sid}:asset_outside_job_artifact_root')
    except:errors.append(f'{sid}:asset_path_invalid')
effective=total-TRANSITION*max(0,len(scenes)-1)
if scenes and not 30<=effective<=45:errors.append(f'effective_duration_outside_30_45:{round(effective,2)}')
voice=str(m.get('voice_text') or '').strip()
if not voice:errors.append('missing_voice_text')
if len(voice)>1800:errors.append('voice_text_too_long')
try:
    sp=float(m.get('voice_speed',1.08))
    if not .85<=sp<=1.25:errors.append('voice_speed_out_of_range')
except:errors.append('voice_speed_invalid')
plats=m.get('platforms') or []
if plats and plats!=['youtube_shorts']:errors.append('platforms_must_be_youtube_shorts_only')
out={'status':'PASS' if not errors else 'FAIL','errors':errors,'job_id':job or None,'scene_count':len(scenes),'raw_scene_duration':round(total,3),'effective_duration':round(effective,3)}
print(json.dumps(out,indent=2));raise SystemExit(0 if not errors else 43)
