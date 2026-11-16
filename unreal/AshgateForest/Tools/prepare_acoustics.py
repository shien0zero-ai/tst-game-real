"""Derive recorded outdoor 9mm layers; preserves sources and old gunshot assets.

No generated bass, pitch shift, exciter, saturation, or synthetic reverb.
Re-run with --cache containing pinned X_39.wav and X_31.wav (see manifest).
"""
import pathlib,ctypes,os,math,array,wave,json,hashlib,argparse
P=pathlib.Path(__file__).resolve().parents[1];D=P/'SourceArt/Acoustics';D.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--cache',type=pathlib.Path,required=True);args=ap.parse_args()
dll=pathlib.Path('D:/UE5/UE_5.8/Engine/Binaries/ThirdParty/libsndfile/Win64/libsndfile-1.dll');handle=os.add_dll_directory(str(dll.parent));lib=ctypes.CDLL(str(dll))
class Info(ctypes.Structure):_fields_=[('frames',ctypes.c_longlong),('rate',ctypes.c_int),('channels',ctypes.c_int),('format',ctypes.c_int),('sections',ctypes.c_int),('seekable',ctypes.c_int)]
lib.sf_open.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(Info)];lib.sf_open.restype=ctypes.c_void_p;lib.sf_readf_float.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_longlong];lib.sf_close.argtypes=[ctypes.c_void_p]
def read(p):
 i=Info();f=lib.sf_open(str(p).encode(),16,ctypes.byref(i));assert f,p;b=(ctypes.c_float*(i.frames*i.channels))();lib.sf_readf_float(f,b,i.frames);lib.sf_close(f);return i,b
report={'library':'The Free Firearm Sound Library','license':'CC0-1.0','commit':'beb2f4041f3d6740fa0aeaf0e71159bd65a78c1b','sources':{},'outputs':{},'limits':'PPQ 9mm is a recording proxy for the service pistol, not a P38-specific recording. Raw near source has 18 clipped sample values across both channels; selected takes have 0, 3, and 1. Previous 1911 near source has 444 at 96kHz; its original assets remain for the M1911. Professional dry shooter-perspective, distant, action and ground-specific casing recordings remain needed for final production.'}
def resample(info,b,start,seconds,channels):
 # Windowed-sinc anti-aliasing, 192/96 -> 48k, before decimation.
 ratio=info.rate//48000;assert info.rate%48000==0;cutoff=20000/info.rate;radius=24*ratio
 kernel=[(2*cutoff if k==0 else math.sin(2*math.pi*cutoff*k)/(math.pi*k))*(.5+.5*math.cos(math.pi*k/radius)) for k in range(-radius,radius+1)];norm=sum(kernel);kernel=[v/norm for v in kernel]
 output=[array.array('f') for _ in channels];offset=round(start*info.rate)
 for j in range(round(seconds*48000)):
  center=offset+j*ratio
  for c,out in zip(channels,output):out.append(sum(b[max(0,min(info.frames-1,center+k-radius))*info.channels+c]*w for k,w in enumerate(kernel)))
 return output
def save(name,data,reference_gain=1.,tail=False):
 n=len(data[0]);rate=48000;hpcoef=math.exp(-2*math.pi*25/rate)
 for c in data:
  last=high=0.
  for j,x in enumerate(c):
   high=hpcoef*(high+x-last);last=x;t=j/rate
   fade=min(1,t/(.014 if tail else .00012),(n-j)/rate/(.4 if tail else .12));c[j]=high*max(0,fade)*reference_gain
 peak=max(abs(x) for c in data for x in c);gain=min(1,.82/max(peak,1e-9));pcm=array.array('h')
 for j in range(n):
  for c in data:pcm.append(round(c[j]*gain*32767))
 file=D/(name+'.wav')
 with wave.open(str(file),'wb') as w:w.setnchannels(len(data));w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
 report['outputs'][name]={'duration':n/rate,'channels':len(data),'peak':peak*gain,'clip_samples':sum(abs(x)>=32767 for x in pcm),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
for source,starts in [('X_39.wav',[1.402,6.440,10.656]),('X_31.wav',[1.080,5.238])]:
 file=args.cache/source;info,b=read(file);report['sources'][source]={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'url':'https://raw.githubusercontent.com/buddingmonkey/FreeFirearmsSFXLibrary/'+report['commit']+'/Master%20Tracks/Walther%20PPQ/'+source,'rate':info.rate,'clip_samples':sum(abs(x)>=.9999 for x in b),'starts':starts}
 for k,start in enumerate(starts):
  if source=='X_39.wav':save('woods_close_'+str(k),resample(info,b,start,1.6,[1 if k==0 else 0]))
  else:
   save('woods_far_'+str(k),resample(info,b,start,2.8,[1 if k==1 else 0]))
   save('woods_tail_'+str(k),resample(info,b,start+.070,2.65,[0,1]),reference_gain=3.5,tail=True)
# Recorded mechanical proxy, kept well below blast; no artificial metallic case ping.
i,b=read(P/'SourceArt/Audio/slide_release.wav');peak_index=max(range(i.frames),key=lambda j:abs(b[j*i.channels]));start=max(0,peak_index/i.rate-.018);save('woods_action',resample(i,b,start,.12,[0]),reference_gain=.18)
(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report['outputs'],indent=2))
