#!/usr/bin/env python3
import sys,json,hashlib,shutil,re,os
from pathlib import Path
from PIL import Image
MAX_BYTES=25*1024*1024; MAX_PIXELS=40_000_000
if len(sys.argv)!=4: raise SystemExit('usage: drive_ingest_v3.py downloaded_file job_id scene_id')
src=Path(sys.argv[1]);job=sys.argv[2];scene=sys.argv[3]
if not src.is_file():raise SystemExit('SOURCE_MISSING')
if not re.fullmatch(r'[A-Za-z0-9._-]{1,180}',job):raise SystemExit('BAD_JOB_ID')
if not re.fullmatch(r'scene_\d{2}',scene):raise SystemExit('BAD_SCENE_ID')
ext=src.suffix.lower()
if ext not in {'.png','.jpg','.jpeg','.webp'}:raise SystemExit('BAD_EXTENSION')
size=src.stat().st_size
if size<20_000 or size>MAX_BYTES:raise SystemExit('BAD_FILE_SIZE')
try:
    Image.MAX_IMAGE_PIXELS=MAX_PIXELS
    with Image.open(src) as im:
        fmt=(im.format or '').upper();w,h=im.size;im.verify()
    if fmt not in {'PNG','JPEG','WEBP'}:raise SystemExit('BAD_IMAGE_FORMAT')
    if w<720 or h<1280 or w*h>MAX_PIXELS:raise SystemExit('BAD_IMAGE_DIMENSIONS')
except SystemExit:raise
except Exception:raise SystemExit('IMAGE_DECODE_FAILED')
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
source_sha=digest(src)
dest=Path('/opt/jarvis/v3/artifacts')/job/'assets'/(scene+ext);dest.parent.mkdir(parents=True,exist_ok=True)
if dest.exists():
    old_sha=digest(dest)
    if old_sha!=source_sha:raise SystemExit('SCENE_ASSET_CONFLICT')
else:
    tmp=dest.with_name(dest.name+f'.tmp.{os.getpid()}');shutil.copy2(src,tmp);os.replace(tmp,dest)
receipt={'status':'INGESTED','job_id':job,'scene_id':scene,'asset_path':str(dest),'sha256':source_sha,'bytes':size,'width':w,'height':h,'format':fmt}
rp=Path('/opt/jarvis/v3/drive-receipts')/(job+'__'+scene+'.json');rp.parent.mkdir(parents=True,exist_ok=True);tmp=rp.with_name(rp.name+f'.tmp.{os.getpid()}');tmp.write_text(json.dumps(receipt,indent=2)+'\n');os.replace(tmp,rp)
print(json.dumps(receipt))
