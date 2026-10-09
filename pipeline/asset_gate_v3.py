#!/usr/bin/env python3
import sys,json,hashlib,math
from pathlib import Path
from PIL import Image,ImageStat,ImageFilter

def dhash(im,size=8):
    im=im.convert('L').resize((size+1,size))
    px=list(im.getdata()); bits=[]
    for y in range(size):
      row=px[y*(size+1):(y+1)*(size+1)]
      bits += [row[x]>row[x+1] for x in range(size)]
    return sum((1<<i) for i,b in enumerate(bits) if b)

def phashish(im,size=8):
    # dependency-free perceptual hash: blurred grayscale block mean
    x=im.convert('L').resize((size,size)).filter(ImageFilter.GaussianBlur(.5))
    vals=list(x.getdata()); mean=sum(vals)/len(vals)
    return sum((1<<i) for i,v in enumerate(vals) if v>mean)

def ham(a,b): return (a^b).bit_count()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()

def check(manifest):
 m=json.load(open(manifest)); scenes=m.get('scenes',[]); seen_sha={}; seen_d=[]; seen_p=[]; out=[]
 for i,s in enumerate(scenes,1):
  sid=s.get('scene_id') or f'scene_{i:02d}'; p=Path(s.get('asset') or s.get('asset_path') or '')
  reasons=[]; meta={'scene_id':sid,'asset_path':str(p)}
  if not p.is_file(): reasons.append('missing')
  else:
   try:
    if p.stat().st_size<20_000: reasons.append('too_small')
    sh=sha(p); meta['sha256']=sh
    if sh in seen_sha: reasons.append('exact_duplicate_of:'+seen_sha[sh])
    else: seen_sha[sh]=sid
    im=Image.open(p); im.load(); w,h=im.size; meta.update(width=w,height=h)
    ratio=w/h
    if h<=w: reasons.append('not_vertical')
    if abs(ratio-9/16)>0.08: reasons.append('aspect_not_9_16')
    if w<720 or h<1280: reasons.append('low_resolution')
    st=ImageStat.Stat(im.convert('L')); mean=st.mean[0]; std=st.stddev[0]
    if mean<4: reasons.append('near_black')
    if mean>251: reasons.append('near_white')
    if std<5: reasons.append('low_information')
    d=dhash(im); ph=phashish(im); meta['dhash']=f'{d:016x}'; meta['phash']=f'{ph:016x}'
    for od,osid in seen_d:
      if ham(d,od)<=4: reasons.append('near_duplicate_dhash_of:'+osid); break
    for op,osid in seen_p:
      if ham(ph,op)<=4: reasons.append('near_duplicate_phash_of:'+osid); break
    seen_d.append((d,sid)); seen_p.append((ph,sid))
   except Exception as e: reasons.append('decode_error:'+type(e).__name__)
  meta['qc_status']='PASS' if not reasons else 'FAIL'; meta['reasons']=reasons; out.append(meta)
 status='PASS' if len(out)==len(scenes) and all(x['qc_status']=='PASS' for x in out) else 'REPAIR_REQUIRED'
 return {'status':status,'expected':len(scenes),'valid':sum(x['qc_status']=='PASS' for x in out),'scenes':out}
if __name__=='__main__':
 r=check(sys.argv[1]); print(json.dumps(r,indent=2)); sys.exit(0 if r['status']=='PASS' else 42)
