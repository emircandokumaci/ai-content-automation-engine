#!/usr/bin/env python3
import json,time,subprocess,os
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(os.environ.get('JARVIS_YOUTUBE_BASE','./runtime/youtube')).resolve(); CFG=BASE/'config.json'; LEDGER=BASE/'state'/'publish-ledger.json'; LOG=BASE/'logs'/'reconciler.log'; ATT=BASE/'state'/'compliance-attempts.json'
def load(p,d):
    try:return json.loads(p.read_text())
    except:return d
def atomic(p,o):
    p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+f'.tmp.{os.getpid()}');t.write_text(json.dumps(o,indent=2)+'\n');os.replace(t,p)
def log(msg):
    line=f'{datetime.now(timezone.utc).isoformat()} {msg}'; print(line,flush=True); LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open('a') as f:f.write(line+'\n')
def due(rec):
    state=str(rec.get('state') or '')
    if state not in ('UPLOADED','VERIFIED','VERIFIED_PRIVATE','SCHEDULED'):return False
    nv=rec.get('next_verify_at')
    if not nv:return True
    try:return datetime.now(timezone.utc)>=datetime.fromisoformat(str(nv).replace('Z','+00:00'))
    except:return True
def post(url,body):
    payload=json.dumps(body,separators=(',',':'))
    r=subprocess.run(['curl','-fsS','--max-time','10','-H','Content-Type: application/json','-X','POST','--data-binary',payload,url],capture_output=True,text=True)
    return r.returncode,(r.stdout+r.stderr).strip()[-800:]
def once():
    cfg=load(CFG,{}); verify=str(cfg.get('verifier_webhook') or ''); compliance=str(cfg.get('compliance_webhook') or '')
    if not verify.startswith('http://127.0.0.1:') or not compliance.startswith('http://127.0.0.1:'):
        log('CONFIG_BLOCK internal_webhooks_must_be_loopback');return
    ledger=load(LEDGER,{'jobs':{}}); jobs=ledger.get('jobs') or {}; attempts=load(ATT,{})
    retry=max(900,int(cfg.get('synthetic_compliance_retry_seconds',3600))); max_attempts=max(1,int(cfg.get('max_compliance_attempts',3))); now=time.time()
    for job,rec in sorted(jobs.items()):
        vid=str(rec.get('youtube_video_id') or '')
        if len(vid)!=11:continue
        expected=rec.get('contains_synthetic_media_expected') is True; actual=rec.get('contains_synthetic_media_actual')
        if expected and actual is not True and str(rec.get('state') or '')!='YOUTUBE_FAILED':
            a=attempts.get(job) or {}; last=float(a.get('ts',0) or 0); count=int(a.get('count',0) or 0)
            if count>=max_attempts:
                log(f'COMPLIANCE_BLOCKED_MAX_ATTEMPTS {job} {vid} count={count}')
                continue
            if now-last>=retry:
                rc,out=post(compliance,{'job_id':job,'video_id':vid,'contains_synthetic_media':True})
                if rc==0:
                    attempts[job]={'ts':now,'video_id':vid,'count':count+1}; atomic(ATT,attempts);log(f'COMPLIANCE_DISPATCHED {job} {vid} attempt={count+1} {out}')
                else:log(f'COMPLIANCE_DISPATCH_ERROR {job} {vid} rc={rc} {out}')
            continue
        if not due(rec):continue
        rc,out=post(verify,{'job_id':job,'video_id':vid})
        if rc==0:log(f'VERIFY_DISPATCHED {job} {vid} {out}')
        else:log(f'VERIFY_DISPATCH_ERROR {job} {vid} rc={rc} {out}')
        time.sleep(1)
def main():
    interval=max(60,int(load(CFG,{}).get('verification_interval_seconds',300)));log(f'RECONCILER_START interval={interval}')
    while True:
        try:once()
        except Exception as e:log('RECONCILER_ERROR '+repr(e))
        time.sleep(interval)
if __name__=='__main__':main()
