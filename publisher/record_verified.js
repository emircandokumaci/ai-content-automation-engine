#!/usr/bin/env node
'use strict';
const S=require('./state');
const [job0,videoId0,privacy0,publishAt0,uploadStatus0,synthetic0]=process.argv.slice(2);
const job=String(job0||'').trim(), videoId=String(videoId0||'').trim(), privacy=String(privacy0||'').trim(), publishAt=String(publishAt0||'').trim(), uploadStatus=String(uploadStatus0||'').trim();
function die(m,c=2){console.error(m);process.exit(c);}
if(!job||!/^[A-Za-z0-9_-]{11}$/.test(videoId)) die('INVALID_JOB_OR_VIDEO_ID');
try{
 const ledger=S.load(S.P.ledger,{jobs:{},hashes:{}}); ledger.jobs=ledger.jobs||{}; const rec=ledger.jobs[job]; if(!rec) die('LEDGER_JOB_NOT_FOUND',3); if(rec.youtube_video_id!==videoId) die('VIDEO_ID_MISMATCH',4);
 let state='VERIFIED'; if(['failed','rejected'].includes(uploadStatus)) state='YOUTUBE_FAILED'; else if(privacy==='public') state='PUBLISHED'; else if(privacy==='private'&&publishAt) state='SCHEDULED'; else if(privacy==='private') state='VERIFIED_PRIVATE';
 let nextVerifyAt=null; if(state==='SCHEDULED'){const t=Date.parse(publishAt); if(Number.isFinite(t)) nextVerifyAt=new Date(t+120000).toISOString();} else if(state==='VERIFIED_PRIVATE') nextVerifyAt=new Date(Date.now()+3600000).toISOString();
 const syntheticActual=synthetic0==='true'?true:synthetic0==='false'?false:null;
 ledger.jobs[job]={...rec,state,verified_at:S.now(),privacy_status:privacy||null,publish_at_actual:publishAt||null,upload_status:uploadStatus||null,contains_synthetic_media_actual:syntheticActual,next_verify_at:nextVerifyAt}; S.atomicJson(S.P.ledger,ledger);
 const rp=S.receiptPath(job); const rr=S.load(rp,null); if(rr) S.atomicJson(rp,{...rr,state,verified_at:S.now(),privacy_status:privacy||null,publish_at_actual:publishAt||null,upload_status:uploadStatus||null,contains_synthetic_media_actual:syntheticActual,next_verify_at:nextVerifyAt});
 const cp=S.claimPath(job); if(S.fs.existsSync(cp)) S.updateClaim(job,{status:state,verified_at:S.now(),privacy_status:privacy||null,publish_at_actual:publishAt||null});
 S.event('VIDEO_VERIFIED',{job_id:job,youtube_video_id:videoId,state,privacy_status:privacy,publish_at:publishAt,upload_status:uploadStatus,contains_synthetic_media_actual:syntheticActual,next_verify_at:nextVerifyAt});
 console.log(JSON.stringify({status:'VERIFIED_RECORDED',job_id:job,youtube_video_id:videoId,state,privacy_status:privacy,publish_at:publishAt,upload_status:uploadStatus,contains_synthetic_media_actual:syntheticActual}));
}catch(e){S.event('VERIFY_RECORD_ERROR',{job_id:job,youtube_video_id:videoId,error:String(e&&e.stack||e)});console.error(String(e&&e.stack||e));process.exit(10);}
