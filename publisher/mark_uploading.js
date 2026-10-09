#!/usr/bin/env node
'use strict';
const S=require('./state');
const job=String(process.argv[2]||'').trim();
if(!job){console.error('usage: mark_uploading.js JOB_ID');process.exit(2);}
try{
 const c=S.updateClaim(job,{status:'UPLOAD_STARTED',upload_started_at:S.now()});
 S.event('UPLOAD_STARTED',{job_id:job,video_sha256:c.video_sha256});
 console.log(JSON.stringify({status:'UPLOAD_STARTED',job_id:job,video_sha256:c.video_sha256,manifest_path:c.manifest_path,video_path:c.video_path}));
}catch(e){console.error(String(e&&e.stack||e));process.exit(3);}
