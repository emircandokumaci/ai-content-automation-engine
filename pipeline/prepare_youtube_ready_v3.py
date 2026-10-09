#!/usr/bin/env python3
import json,sys,os,hashlib
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
if len(sys.argv)!=3: raise SystemExit('usage: prepare_youtube_ready_v3.py manifest.json final_video.mp4')
manifest=Path(sys.argv[1]); video=Path(sys.argv[2])
if not manifest.is_file(): raise SystemExit('MANIFEST_MISSING')
if not video.is_file(): raise SystemExit('VIDEO_MISSING')
def load(p,d=None):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return {} if d is None else d
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def atomic(p,o):
    t=p.with_name(p.name+f'.tmp.{os.getpid()}'); t.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(t,p)
m=load(manifest,{}); cfg=load(Path('/opt/jarvis/youtube/config.json'),{})
job=str(m.get('id') or m.get('job_id') or manifest.stem).strip()
if not job or len(job)>180: raise SystemExit('JOB_ID_INVALID')
yt=m.get('youtube') or {}
def pick(k,default=None): return yt.get(k,m.get(k,default))
title=str(pick('title') or '').strip()
if not title:
    scenes=m.get('scenes') or []; title=str((scenes[0].get('caption') if scenes else '') or job).strip()
if not title: raise SystemExit('TITLE_MISSING')
description=str(pick('description') or m.get('voice_text') or '').strip()
tags=pick('tags',[])
if isinstance(tags,str): tags=[x.strip() for x in tags.split(',') if x.strip()]
if not isinstance(tags,list): tags=[]
tags=[str(x).strip() for x in tags if str(x).strip()][:50]
tz=ZoneInfo(str(cfg.get('timezone') or 'Europe/Istanbul')); now=datetime.now(tz); lead=int(cfg.get('late_publish_min_lead_minutes',45))
publish_at=pick('publish_at')
if publish_at:
    try:candidate=datetime.fromisoformat(str(publish_at).replace('Z','+00:00')).astimezone(tz)
    except Exception: raise SystemExit('PUBLISH_AT_INVALID')
else:candidate=now.replace(hour=16,minute=0,second=0,microsecond=0)
if candidate <= now+timedelta(minutes=lead):
    candidate=(now+timedelta(days=1)).replace(hour=16,minute=0,second=0,microsecond=0)
publish_at=candidate.isoformat(); dg=sha(video)
ready_dir=Path('/opt/jarvis/youtube/ready'); ready_dir.mkdir(parents=True,exist_ok=True); out=ready_dir/f'{job}.json'
meta={'schema_version':2,'id':job,'job_id':job,'title':title[:100],'video_file':str(video),'video_sha256':dg,'description':description[:5000],'tags':tags,'privacy_status':'private','publish_at':publish_at,'category_id':str(pick('category_id','28')),'region_code':str(pick('region_code','US')),'made_for_kids':bool(pick('made_for_kids',False)),'contains_synthetic_media':bool(pick('contains_synthetic_media',True)),'qc_passed':True,'prepared_at':datetime.now(tz).isoformat()}
if out.exists():
    old=load(out,{})
    if old.get('job_id')==job and old.get('video_sha256')==dg:
        print(json.dumps({'status':'READY_ALREADY_EXISTS','job_id':job,'manifest_path':str(out),'video_path':str(video),'publish_at':old.get('publish_at')},ensure_ascii=False)); raise SystemExit(0)
    raise SystemExit('READY_CONFLICT_SAME_JOB_DIFFERENT_CONTENT')
atomic(out,meta)
print(json.dumps({'status':'READY','job_id':job,'manifest_path':str(out),'video_path':str(video),'video_sha256':dg,'publish_at':publish_at},ensure_ascii=False))
