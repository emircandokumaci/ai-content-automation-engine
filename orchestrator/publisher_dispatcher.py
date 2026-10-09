#!/usr/bin/env python3
import json,time,subprocess,os
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
BASE=Path(os.environ.get('JARVIS_YOUTUBE_BASE','/opt/jarvis/youtube'))
READY=BASE/'ready';STATE=BASE/'state';CLAIMS=STATE/'claims';RECEIPTS=STATE/'receipts';QUAR=STATE/'quarantine';LOG=BASE/'logs'/'publisher-dispatcher.log';CFG=BASE/'config.json';RETRIES=STATE/'preupload-retries.json';DISPATCH=STATE/'dispatch-state.json'
for p in (READY,CLAIMS,RECEIPTS,QUAR,LOG.parent):p.mkdir(parents=True,exist_ok=True)
def now():return datetime.now(timezone.utc).isoformat()
def load(p,d):
    try:return json.loads(p.read_text())
    except Exception:return d
def atomic(p,o):
    t=p.with_name(p.name+f'.tmp.{os.getpid()}');t.write_text(json.dumps(o,indent=2)+'\n');os.replace(t,p)
def log(msg):
    line=f'{now()} {msg}';print(line,flush=True)
    with LOG.open('a') as f:f.write(line+'\n')
def safe(s):return ''.join(c if c.isalnum() or c in '._-' else '_' for c in str(s))[:180]
def job_of(m,p):return str(m.get('job_id') or m.get('id') or p.stem).strip()
def seconds_since(ts):
    try:return max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(str(ts).replace('Z','+00:00'))).total_seconds())
    except:return 10**9
def uploads_today(tz):
    z=ZoneInfo(tz);today=datetime.now(z).date();n=0
    for rp in RECEIPTS.glob('*.json'):
        r=load(rp,{})
        try:
            dt=datetime.fromisoformat(str(r.get('uploaded_at')).replace('Z','+00:00')).astimezone(z)
            if dt.date()==today:n+=1
        except:pass
    return n
def trigger(url):
    r=subprocess.run(['curl','-fsS','--max-time','10','-X','POST',url],text=True,capture_output=True)
    return r.returncode,(r.stdout+r.stderr).strip()[-1000:]
def scan_once():
    cfg=load(CFG,{})
    if cfg.get('publishing_enabled') is not True:return
    url=str(cfg.get('publisher_webhook') or '').strip()
    if not url.startswith('http://127.0.0.1:'):log('CONFIG_BLOCK publisher_webhook_must_be_loopback');return
    tz=str(cfg.get('timezone') or 'Europe/Istanbul');max_daily=max(1,int(cfg.get('max_uploads_per_day',1)))
    if uploads_today(tz)>=max_daily:return
    retry_state=load(RETRIES,{});dispatch_state=load(DISPATCH,{})
    max_retries=int(cfg.get('max_preupload_retries',3));safe_retry=int(cfg.get('safe_claim_retry_seconds',900));unknown_timeout=int(cfg.get('reconciliation_timeout_seconds',1800));cooldown=max(60,int(cfg.get('dispatch_cooldown_seconds',300)))
    for mp in sorted(READY.glob('*.json'),key=lambda p:p.stat().st_mtime):
        m=load(mp,{});job=job_of(m,mp)
        if not job:continue
        rp=RECEIPTS/(safe(job)+'.json');cp=CLAIMS/(safe(job)+'.json')
        if rp.exists():continue
        if cp.exists():
            c=load(cp,{});st=str(c.get('status','CLAIMED'));age=seconds_since(c.get('updated_at') or c.get('claimed_at') or '')
            if st=='CLAIMED' and age>=safe_retry:
                n=int(retry_state.get(job,0))+1;retry_state[job]=n;atomic(RETRIES,retry_state)
                if n>max_retries:
                    c['status']='PREUPLOAD_FAILED_PERMANENT';c['updated_at']=now();atomic(cp,c);log(f'BLOCK {job} max_preupload_retries={n-1}');continue
                q=QUAR/f'{safe(job)}-claim-safe-retry-{int(time.time())}.json';os.replace(cp,q)
                lock=STATE/'channel-upload.lock.json';l=load(lock,{})
                if l.get('job_id')==job:lock.unlink(missing_ok=True)
                log(f'SAFE_RETRY_RELEASE {job} attempt={n}');continue
            if st=='UPLOAD_STARTED' and age>=unknown_timeout:
                c['status']='RECONCILIATION_REQUIRED';c['updated_at']=now();atomic(cp,c);log(f'RECONCILIATION_REQUIRED {job} age={int(age)}s')
            continue
        last=float((dispatch_state.get(job) or {}).get('ts',0) or 0)
        if time.time()-last<cooldown:continue
        dispatch_state[job]={'ts':time.time(),'manifest':str(mp)};atomic(DISPATCH,dispatch_state)
        rc,out=trigger(url)
        if rc==0:log(f'DISPATCHED {job} {out}')
        else:log(f'DISPATCH_ERROR {job} rc={rc} {out}')
        time.sleep(2)
def main():
    log('DISPATCHER_START')
    while True:
        try:scan_once()
        except Exception as e:log('SCAN_ERROR '+repr(e))
        time.sleep(15)
if __name__=='__main__':main()
