"""Prepare free GDC licensed P38/forest recordings locally, without installing tools.

Audio remains licensed material: do not commit WAVs or SoundWave assets publicly.
Only finished game packages may redistribute these recordings under the GDC terms.
"""
import argparse,array,ctypes,hashlib,json,math,os,pathlib,urllib.request,wave
ap=argparse.ArgumentParser();ap.add_argument('--project',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);ap.add_argument('--cache',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);ap.add_argument('--manifest',type=pathlib.Path);ap.add_argument('--report',type=pathlib.Path);ap.add_argument('--download',action='store_true');a=ap.parse_args()
P=a.project;cache=a.cache or P.parents[1]/'work/p38-source-cache';D=a.output or P/'SourceArt/P38Field';cache.mkdir(parents=True,exist_ok=True);D.mkdir(parents=True,exist_ok=True)
m=json.loads((a.manifest or P/'SourceArt/P38FieldManifest.json').read_text(encoding='utf-8'))
for name,v in m['files'].items():
 p=cache/name
 if not p.exists():
  if not a.download:raise RuntimeError('Missing licensed recording '+name+'; use --download to obtain free GDC recordings')
  with urllib.request.urlopen(urllib.request.Request(v['url'],headers={'User-Agent':'Ashgate-AssetFetcher/1.0'}),timeout=120) as r:
   data=r.read(v['bytes']+1);assert len(data)==v['bytes'];assert hashlib.sha256(data).hexdigest()==v['sha256'];p.write_bytes(data)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],'Source hash mismatch '+name
dll=pathlib.Path('D:/UE5/UE_5.8/Engine/Binaries/ThirdParty/libsndfile/Win64/libsndfile-1.dll');handle=os.add_dll_directory(str(dll.parent));lib=ctypes.CDLL(str(dll))
class Info(ctypes.Structure):_fields_=[('frames',ctypes.c_longlong),('rate',ctypes.c_int),('channels',ctypes.c_int),('format',ctypes.c_int),('sections',ctypes.c_int),('seekable',ctypes.c_int)]
lib.sf_open.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(Info)];lib.sf_open.restype=ctypes.c_void_p;lib.sf_readf_float.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_longlong];lib.sf_close.argtypes=[ctypes.c_void_p]
def read(name):
 i=Info();f=lib.sf_open(str(cache/name).encode(),16,ctypes.byref(i));assert f;b=(ctypes.c_float*(i.frames*i.channels))();assert lib.sf_readf_float(f,b,i.frames)==i.frames;lib.sf_close(f);return i,b
def segment(i,b,start,seconds,channel):
 ratio=i.rate/48000;cutoff=min(20000/i.rate,.45);radius=48;weights=[(2*cutoff if k==0 else math.sin(2*math.pi*cutoff*k)/(math.pi*k))*(.5+.5*math.cos(math.pi*k/radius)) for k in range(-radius,radius+1)];z=sum(weights);weights=[v/z for v in weights];out=array.array('f')
 for j in range(round(seconds*48000)):
  c=round((start+j/48000)*i.rate);out.append(sum(b[max(0,min(i.frames-1,c+k-radius))*i.channels+channel]*v for k,v in enumerate(weights)))
 return out
report={'sources':m['files'],'outputs':{},'processing':'Windowed-sinc to 48k PCM16 mono; shared gain per layer family, no bass synthesis, pitch shifting, saturation or hard limiter. Original sources preserved. Not a promise of unclipped source capture.'}
def save(name,data,gain,fade_in=.0001,fade_out=.015,origin=None):
 n=len(data);last=high=0.;coef=math.exp(-2*math.pi*25/48000);pcm=array.array('h')
 for j,x in enumerate(data):
  high=coef*(high+x-last);last=x;env=max(0,min(1,j/48000/fade_in,(n-j)/48000/fade_out));v=high*gain*env;assert abs(v)<.99;pcm.append(round(v*32767))
 p=D/(name+'.wav')
 with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(pcm.tobytes())
 report['outputs'][name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'seconds':n/48000,'peak':max(abs(v) for v in pcm)/32767,'clipped_samples':sum(abs(v)>=32767 for v in pcm),'gain':gain,'source_segment':origin}
i,b=read('P38, Firing, t1, 2m, Behind, LS5.wav');starts=[8.454,24.019,31.910];takes=[segment(i,b,t,.20,1) for t in starts];gain=.80/max(abs(v) for take in takes for v in take)
for k,(t,data) in enumerate(zip(starts,takes)):
 raw=[b[j*i.channels+1] for j in range(round(t*i.rate),round((t+.20)*i.rate))];origin={'name':'P38, Firing, t1, 2m, Behind, LS5.wav','start_seconds':t,'channel':1,'source_near_fullscale_samples':sum(abs(v)>=.9999 for v in raw)};save('p38_shot_'+str(k),data,gain,origin=origin)
tail_name='MP5_forest_road_10m_behind_gun_pointing_at_forest_off_axis_MKH8060.wav';i,b=read(tail_name);starts=[.467,3.474];tails=[segment(i,b,t,2.2,0) for t in starts];gain=min(5.,.20/max(abs(v) for take in tails for v in take))
for k,(t,data) in enumerate(zip(starts,tails)):
 raw=[b[j*i.channels] for j in range(round(t*i.rate),round((t+2.2)*i.rate))];assert not any(abs(v)>=.9999 for v in raw);save('p38_tail_'+str(k),data,gain,.010,.35,{'name':tail_name,'start_seconds':t,'attack_removed_seconds':.10,'source_near_fullscale_samples':0})
i,b=read('P38, Handling, Removing Magazine, 1m, Right, MKH8060.wav');data=segment(i,b,.420,.48,0);save('p38_mag_out',data,min(1.,.50/max(abs(v) for v in data)),.004,.06,{'name':'P38, Handling, Removing Magazine, 1m, Right, MKH8060.wav','start_seconds':.420})
(a.report or P/'Saved/p38-preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report['outputs'],indent=2))
