#!/usr/bin/env node
'use strict';
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const BASE=process.env.JARVIS_YOUTUBE_BASE||'/opt/jarvis/youtube';
const P={
 base:BASE, ready:path.join(BASE,'ready'), state:path.join(BASE,'state'),
 ledger:path.join(BASE,'state','publish-ledger.json'), status:path.join(BASE,'state','status.json'),
 claims:path.join(BASE,'state','claims'), receipts:path.join(BASE,'state','receipts'),
 quarantine:path.join(BASE,'state','quarantine'), events:path.join(BASE,'state','events','publisher.jsonl'),
 config:path.join(BASE,'config.json'), archive:path.join(BASE,'archive'), channelLock:path.join(BASE,'state','channel-upload.lock.json')
};
for(const d of [P.ready,P.state,P.claims,P.receipts,P.quarantine,path.dirname(P.events),P.archive]) fs.mkdirSync(d,{recursive:true});
function load(p,d={}){try{return JSON.parse(fs.readFileSync(p,'utf8'));}catch{return d;}}
function atomicJson(p,o){fs.mkdirSync(path.dirname(p),{recursive:true});const t=p+'.tmp.'+process.pid+'.'+Date.now();const fd=fs.openSync(t,'w',0o640);try{fs.writeFileSync(fd,JSON.stringify(o,null,2)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(t,p);}
function now(){return new Date().toISOString();}
function safe(s){return String(s||'').replace(/[^A-Za-z0-9._-]/g,'_').slice(0,180);}
function sha256(p){const h=crypto.createHash('sha256');const fd=fs.openSync(p,'r');try{const b=Buffer.allocUnsafe(1024*1024);let n;while((n=fs.readSync(fd,b,0,b.length,null))>0)h.update(b.subarray(0,n));}finally{fs.closeSync(fd);}return h.digest('hex');}
function event(type,data={}){const row={ts:now(),type,...data};fs.appendFileSync(P.events,JSON.stringify(row)+'\n');}
function claimPath(job){return path.join(P.claims,safe(job)+'.json');}
function receiptPath(job){return path.join(P.receipts,safe(job)+'.json');}
function createClaim(c){const p=claimPath(c.job_id);const fd=fs.openSync(p,'wx',0o640);try{fs.writeFileSync(fd,JSON.stringify(c,null,2)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}return p;}
function updateClaim(job,patch){const p=claimPath(job);const c=load(p,null);if(!c) throw new Error('CLAIM_NOT_FOUND:'+job);const n={...c,...patch,updated_at:now()};atomicJson(p,n);return n;}
module.exports={fs,path,P,load,atomicJson,now,safe,sha256,event,claimPath,receiptPath,createClaim,updateClaim};
