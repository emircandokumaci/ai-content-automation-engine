#!/usr/bin/env python3
import json,os,subprocess,tempfile,pathlib
BIN=(pathlib.Path(__file__).resolve().parents[1]/'publisher')
def run(base,script,*args):
    e=os.environ.copy();e['JARVIS_YOUTUBE_BASE']=str(base)
    r=subprocess.run(['node',str(BIN/script),*map(str,args)],env=e,text=True,capture_output=True)
    line=(r.stdout.strip().splitlines() or ['{}'])[-1]
    try:o=json.loads(line)
    except:o={'raw':line,'err':r.stderr,'rc':r.returncode}
    return r.returncode,o
def setcfg(base,**kw):
    p=base/'config.json';d=json.loads(p.read_text());d.update(kw);p.write_text(json.dumps(d))
def manifest(base,job,video):
    p=base/'ready'/f'{job}.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'id':job,'job_id':job,'title':'Test','video_file':str(video),'description':'x','tags':['a'],'privacy_status':'private','publish_at':'2099-01-01T16:00:00+03:00','category_id':'28','region_code':'US','made_for_kids':False,'contains_synthetic_media':True,'qc_passed':True}))
    return p
def init(base):
    for d in ('state','state/claims','state/receipts','state/quarantine','state/events','ready','archive'): (base/d).mkdir(parents=True,exist_ok=True)
    (base/'config.json').write_text(json.dumps({'publishing_enabled':True,'category_id':'28','region_code':'US','timezone':'Europe/Istanbul','max_uploads_per_day':1,'channel_mutex_enabled':True,'channel_lock_stale_seconds':900}))
with tempfile.TemporaryDirectory() as td:
    b=pathlib.Path(td);init(b)
    v=b/'v.mp4';v.write_bytes(b'A'*250000);m=manifest(b,'job-1',v)
    rc,a=run(b,'publisher_guard.js');assert a['status']=='READY',a
    rc,a=run(b,'publisher_guard.js');assert a['status']=='INFLIGHT_BLOCKED',a
    # A distinct job cannot race while the channel-level mutex is held.
    v3=b/'v3.mp4';v3.write_bytes(b'C'*250000);manifest(b,'job-race',v3);rc,a=run(b,'publisher_guard.js',b/'ready'/'job-race.json');assert a['status']=='CHANNEL_BUSY',a
    rc,a=run(b,'mark_uploading.js','job-1');assert a['status']=='UPLOAD_STARTED',a
    rc,a=run(b,'publisher_guard.js');assert a['status']=='RECONCILIATION_REQUIRED',a
    rc,a=run(b,'record_upload.js',m,'YT_TEST_001');assert a['status']=='UPLOADED_RECORDED',a
    assert not (b/'state'/'channel-upload.lock.json').exists(),'channel lock not released after durable receipt'
    # Same binary under another job is blocked by content hash.
    m2=manifest(b,'job-2',v);rc,a=run(b,'publisher_guard.js',m2);assert a['status']=='DUPLICATE_BLOCKED' and a['reason']=='video_hash_already_uploaded',a
    # A different binary/job on same local day is blocked by daily circuit breaker.
    rc,a=run(b,'publisher_guard.js',b/'ready'/'job-race.json');assert a['status']=='DAILY_UPLOAD_LIMIT',a
    # Same job with different content is blocked by durable job identity.
    v2=b/'v2.mp4';v2.write_bytes(b'B'*250000);m3=manifest(b,'job-1',v2);rc,a=run(b,'publisher_guard.js',m3);assert a['status']=='DUPLICATE_BLOCKED' and a['reason']=='job_id_already_uploaded',a
    setcfg(b,publishing_enabled=False);rc,a=run(b,'publisher_guard.js');assert a['status']=='PUBLISHING_PAUSED',a
print('PASS idempotency, channel mutex, daily circuit breaker')
