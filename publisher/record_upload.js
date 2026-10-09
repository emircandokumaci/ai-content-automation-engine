#!/usr/bin/env node
'use strict';
const S=require('./state');
const manifest=String(process.argv[2]||'').trim(); const youtubeId=String(process.argv[3]||'').trim();
function die(msg,code=2){console.error(msg);process.exit(code);}
if(!manifest||!youtubeId) die('usage: record_upload.js MANIFEST_PATH YOUTUBE_VIDEO_ID');
if(!/^[A-Za-z0-9_-]{11}$/.test(youtubeId)) die('YOUTUBE_ID_INVALID',3);
if(!S.fs.existsSync(manifest)) die('MANIFEST_NOT_FOUND:'+manifest,3);
try{
 const m=S.load(manifest,{}); const job=String(m.job_id||m.id||S.path.basename(manifest,'.json')).trim(); if(!job) die('JOB_ID_MISSING',3);
 const vf0=String(m.video_file||'').trim(); const vf=S.path.isAbsolute(vf0)?vf0:S.path.join(S.path.dirname(manifest),vf0); if(!S.fs.existsSync(vf)) die('VIDEO_NOT_FOUND:'+vf,3);
 const dg=S.sha256(vf); const cp=S.claimPath(job); const c=S.load(cp,null); if(!c) die('CLAIM_NOT_FOUND:'+job,4); if(c.video_sha256!==dg) die('CLAIM_SHA_MISMATCH',5);
 const rp=S.receiptPath(job); const existing=S.load(rp,null);
 if(existing){
   if(existing.youtube_video_id===youtubeId&&existing.video_sha256===dg){console.log(JSON.stringify({status:'UPLOAD_ALREADY_RECORDED',job_id:job,youtube_video_id:youtubeId,video_sha256:dg}));process.exit(0);}
   die('UPLOAD_RECEIPT_CONFLICT',6);
 }
 const syntheticExpected=m.contains_synthetic_media===true;
 const receipt={status:'UPLOADED',job_id:job,youtube_video_id:youtubeId,video_sha256:dg,manifest_path:manifest,video_path:vf,title:m.title||'',publish_at:m.publish_at||null,contains_synthetic_media_expected:syntheticExpected,uploaded_at:S.now()};
 S.atomicJson(rp,receipt); S.event('UPLOAD_RECEIPT_WRITTEN',{job_id:job,youtube_video_id:youtubeId,video_sha256:dg});
 const ledger=S.load(S.P.ledger,{jobs:{},hashes:{}}); ledger.jobs=ledger.jobs||{}; ledger.hashes=ledger.hashes||{};
 const prior=ledger.jobs[job]; if(prior&&prior.youtube_video_id&&prior.youtube_video_id!==youtubeId) die('LEDGER_JOB_CONFLICT',7);
 const hprior=ledger.hashes[dg]; const hpid=typeof hprior==='string'?hprior:(hprior&&hprior.youtube_video_id); if(hpid&&hpid!==youtubeId) die('LEDGER_HASH_CONFLICT',7);
 ledger.jobs[job]={state:'UPLOADED',youtube_video_id:youtubeId,video_sha256:dg,recorded_at:S.now(),title:m.title||'',publish_at:m.publish_at||null,contains_synthetic_media_expected:syntheticExpected};
 ledger.hashes[dg]={job_id:job,youtube_video_id:youtubeId,recorded_at:S.now()}; S.atomicJson(S.P.ledger,ledger);
 S.updateClaim(job,{status:'UPLOADED',youtube_video_id:youtubeId,uploaded_at:S.now()});
 const lock=S.load(S.P.channelLock,null); if(lock&&lock.job_id===job){try{S.fs.unlinkSync(S.P.channelLock);S.event('CHANNEL_LOCK_RELEASED',{job_id:job,reason:'upload_recorded'});}catch{}}
 const d=new Date(); const stamp=d.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z'); const dest=S.path.join(S.P.archive,stamp+'-'+S.safe(job)); S.fs.mkdirSync(dest,{recursive:true});
 S.atomicJson(S.path.join(dest,S.path.basename(manifest)),{...m,job_id:job,youtube_id:youtubeId,video_sha256:dg,upload_recorded_at:S.now()});
 try{S.fs.copyFileSync(vf,S.path.join(dest,S.path.basename(vf)));}catch{}
 try{S.fs.unlinkSync(manifest);}catch{}
 const out={ts:S.now(),status:'UPLOADED_RECORDED',job_id:job,youtube_id:youtubeId,video_sha256:dg,archive_dir:dest}; S.atomicJson(S.P.status,out); console.log(JSON.stringify(out));
}catch(e){S.event('RECORD_UPLOAD_ERROR',{manifest,youtube_video_id:youtubeId,error:String(e&&e.stack||e)});console.error(String(e&&e.stack||e));process.exit(10);}
