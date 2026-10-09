#!/usr/bin/env node
'use strict';
const S=require('./state');
function emit(o,code=0){const out={ts:S.now(),...o};S.atomicJson(S.P.status,out);console.log(JSON.stringify(out));process.exitCode=code;return out;}
function pickManifest(){
 const arg=process.argv[2]; if(arg) return arg;
 const files=S.fs.readdirSync(S.P.ready).filter(f=>f.endsWith('.json')).map(f=>S.path.join(S.P.ready,f)).sort((a,b)=>S.fs.statSync(a).mtimeMs-S.fs.statSync(b).mtimeMs);
 return files[0]||null;
}
function dateKey(ts,tz){
 const d=new Date(ts); const parts=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
 const o={}; for(const p of parts) if(p.type!=='literal') o[p.type]=p.value; return `${o.year}-${o.month}-${o.day}`;
}
function uploadsToday(tz){
 const today=dateKey(Date.now(),tz); let n=0;
 for(const f of S.fs.readdirSync(S.P.receipts).filter(x=>x.endsWith('.json'))){const r=S.load(S.path.join(S.P.receipts,f),{});if(r.uploaded_at&&dateKey(r.uploaded_at,tz)===today)n++;}
 return n;
}
function acquireChannelLock(job,dg,cfg){
 const p=S.P.channelLock; const stale=Math.max(300,Number(cfg.channel_lock_stale_seconds||900));
 if(S.fs.existsSync(p)){
   const l=S.load(p,{}); const age=(Date.now()-Date.parse(l.acquired_at||0))/1000;
   const claim=l.job_id?S.claimPath(l.job_id):null; const receipt=l.job_id?S.receiptPath(l.job_id):null;
   if(Number.isFinite(age)&&age>stale&&(!claim||!S.fs.existsSync(claim))&&(!receipt||!S.fs.existsSync(receipt))){
     try{S.fs.unlinkSync(p);S.event('CHANNEL_LOCK_STALE_RECOVERED',{job_id:l.job_id||null,age_seconds:Math.round(age)});}catch{}
   }
 }
 try{
   const fd=S.fs.openSync(p,'wx',0o660); try{S.fs.writeFileSync(fd,JSON.stringify({job_id:job,video_sha256:dg,acquired_at:S.now(),pid:process.pid},null,2)+'\n');S.fs.fsyncSync(fd);}finally{S.fs.closeSync(fd);} return true;
 }catch(e){if(e&&e.code==='EEXIST')return false;throw e;}
}
function releaseChannelLockIfOwned(job){const p=S.P.channelLock;if(!S.fs.existsSync(p))return;const l=S.load(p,{});if(l.job_id===job){try{S.fs.unlinkSync(p);}catch{}}}
function main(){
 const cfg=S.load(S.P.config,{}); const tz=String(cfg.timezone||'Europe/Istanbul');
 if(cfg.publishing_enabled!==true) return emit({status:'PUBLISHING_PAUSED',reason:'config_publishing_enabled_is_not_true'});
 const manifest=pickManifest(); if(!manifest||!S.fs.existsSync(manifest)) return emit({status:'WAITING_CONTENT'});
 const m=S.load(manifest,{}); const job=String(m.job_id||m.id||S.path.basename(manifest,'.json')).trim(); const title=String(m.title||'').trim();
 const vf0=String(m.video_file||'').trim(); const vf=S.path.isAbsolute(vf0)?vf0:S.path.join(S.path.dirname(manifest),vf0);
 if(!job||!title||!vf0||!S.fs.existsSync(vf)) return emit({status:'INVALID_READY',job_id:job||null,reason:'missing_job_title_or_video'},2);
 if(m.qc_passed!==true) return emit({status:'QC_BLOCKED',job_id:job,reason:'qc_passed_not_true'},2);
 const dg=S.sha256(vf); const ledger=S.load(S.P.ledger,{jobs:{},hashes:{}}); ledger.jobs=ledger.jobs||{}; ledger.hashes=ledger.hashes||{};
 const oldJob=ledger.jobs[job]; const oldHash=ledger.hashes[dg];
 if(oldJob&&oldJob.youtube_video_id) return emit({status:'DUPLICATE_BLOCKED',reason:'job_id_already_uploaded',job_id:job,youtube_video_id:oldJob.youtube_video_id,video_sha256:dg});
 if(oldHash) return emit({status:'DUPLICATE_BLOCKED',reason:'video_hash_already_uploaded',job_id:job,youtube_video_id:typeof oldHash==='string'?oldHash:oldHash.youtube_video_id,video_sha256:dg});
 const rp=S.receiptPath(job); if(S.fs.existsSync(rp)){const r=S.load(rp,{});return emit({status:'DUPLICATE_BLOCKED',reason:'upload_receipt_exists',job_id:job,youtube_video_id:r.youtube_video_id||null,video_sha256:dg});}
 const cp=S.claimPath(job);
 if(S.fs.existsSync(cp)){
   const c=S.load(cp,{}); const st=String(c.status||'CLAIMED');
   if(c.video_sha256&&c.video_sha256!==dg) return emit({status:'CONFLICT_BLOCKED',reason:'job_id_reused_with_different_video',job_id:job,existing_sha256:c.video_sha256,video_sha256:dg},3);
   if(['UPLOAD_STARTED','UNKNOWN','RECONCILIATION_REQUIRED'].includes(st)) return emit({status:'RECONCILIATION_REQUIRED',reason:'prior_upload_may_have_started',job_id:job,video_sha256:dg,claim_status:st},4);
   return emit({status:'INFLIGHT_BLOCKED',reason:'existing_claim',job_id:job,video_sha256:dg,claim_status:st});
 }
 const maxDaily=Math.max(1,Number(cfg.max_uploads_per_day||1)); const todayCount=uploadsToday(tz);
 if(todayCount>=maxDaily) return emit({status:'DAILY_UPLOAD_LIMIT',reason:'channel_daily_upload_circuit_breaker',job_id:job,uploads_today:todayCount,max_uploads_per_day:maxDaily},5);
 if(cfg.channel_mutex_enabled!==false&&!acquireChannelLock(job,dg,cfg)) return emit({status:'CHANNEL_BUSY',reason:'global_upload_mutex_held',job_id:job},6);
 const claim={status:'CLAIMED',job_id:job,video_sha256:dg,manifest_path:manifest,video_path:vf,claimed_at:S.now(),updated_at:S.now(),attempt:1};
 try{S.createClaim(claim);}catch(e){releaseChannelLockIfOwned(job);if(e&&e.code==='EEXIST')return emit({status:'INFLIGHT_BLOCKED',reason:'claim_race_lost',job_id:job,video_sha256:dg});throw e;}
 S.event('CLAIMED',{job_id:job,video_sha256:dg,manifest_path:manifest});
 const tags=Array.isArray(m.tags)?m.tags.map(v=>String(v).trim()).filter(Boolean).join(','):String(m.tags||'');
 return emit({status:'READY',job_id:job,manifest_path:manifest,video_path:vf,video_sha256:dg,title:title.slice(0,100),description:String(m.description||'').slice(0,5000),tags_csv:tags,privacy_status:'private',category_id:String(m.category_id||cfg.category_id||'28'),region_code:String(m.region_code||cfg.region_code||'US'),made_for_kids:!!m.made_for_kids,contains_synthetic_media:m.contains_synthetic_media!==false,publish_at:m.publish_at||null,qc_passed:true});
}
try{main();}catch(e){S.event('GUARD_ERROR',{error:String(e&&e.stack||e)});emit({status:'GUARD_ERROR',reason:String(e&&e.message||e)},10);}
