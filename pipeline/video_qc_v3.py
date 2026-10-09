#!/usr/bin/env python3
import json,subprocess,sys,os,hashlib
from fractions import Fraction
if len(sys.argv)!=2: raise SystemExit('usage: video_qc_v3.py file.mp4')
p=sys.argv[1]; reasons=[]
def run(cmd): return subprocess.run(cmd,text=True,capture_output=True)
def fnum(v):
    try:return float(Fraction(str(v)))
    except:return 0.0
# Full decode test first: container metadata can look valid while media is corrupt.
decode=run(['ffmpeg','-v','error','-i',p,'-map','0:v:0','-map','0:a:0?','-f','null','-'])
if decode.returncode!=0: reasons.append('decode_failed')
probe=run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',p])
try:d=json.loads(probe.stdout) if probe.returncode==0 else {}
except:d={}
if not d: reasons.append('ffprobe_failed'); d={'streams':[],'format':{}}
v=next((x for x in d.get('streams',[]) if x.get('codec_type')=='video'),None); a=next((x for x in d.get('streams',[]) if x.get('codec_type')=='audio'),None)
if not v: reasons.append('no_video')
else:
    if (v.get('width'),v.get('height'))!=(1080,1920): reasons.append('resolution_not_1080x1920')
    if v.get('codec_name')!='h264': reasons.append('video_codec_not_h264')
    if v.get('pix_fmt') not in ('yuv420p','yuvj420p'): reasons.append('pixel_format_not_yuv420p')
    fps=fnum(v.get('avg_frame_rate') or v.get('r_frame_rate'))
    if not 23 <= fps <= 61: reasons.append('frame_rate_out_of_range')
if not a: reasons.append('no_audio')
else:
    if a.get('codec_name')!='aac': reasons.append('audio_codec_not_aac')
    try:
        sr=int(a.get('sample_rate') or 0)
        if sr not in (44100,48000): reasons.append('audio_sample_rate_unexpected')
    except: reasons.append('audio_sample_rate_unknown')
try:
    dur=float(d.get('format',{}).get('duration',0))
    if not 30<=dur<=45: reasons.append('duration_outside_30_45')
except: dur=0; reasons.append('duration_unknown')
if v and a:
    try:
        vd=float(v.get('duration') or dur); ad=float(a.get('duration') or dur)
        if abs(vd-ad)>2.0: reasons.append('audio_video_duration_mismatch')
    except: pass
try:
    size=os.path.getsize(p)
    if size<500000: reasons.append('file_too_small')
except:size=0;reasons.append('file_stat_failed')
h=hashlib.sha256()
try:
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    digest=h.hexdigest()
except:digest=None
out={'status':'PASS' if not reasons else 'FAIL','reasons':reasons,'duration':dur,'bytes':size,'sha256':digest,'video':{'codec':v.get('codec_name') if v else None,'width':v.get('width') if v else None,'height':v.get('height') if v else None,'pix_fmt':v.get('pix_fmt') if v else None,'fps':fnum(v.get('avg_frame_rate') or v.get('r_frame_rate')) if v else None},'audio':{'codec':a.get('codec_name') if a else None,'sample_rate':a.get('sample_rate') if a else None,'channels':a.get('channels') if a else None},'decode_stderr':decode.stderr[-1000:] if decode.returncode else ''}
print(json.dumps(out,indent=2));sys.exit(0 if not reasons else 44)
