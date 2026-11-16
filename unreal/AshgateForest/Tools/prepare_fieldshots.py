"""Prepare clean field-recorded handgun shots; no synthesized bass or pitch shift."""
import pathlib,ctypes,os,array,wave,math,json,hashlib
P=pathlib.Path(__file__).resolve().parents[1];S=P/'SourceArt/Viewmodel';D=S/'Audio';D.mkdir(parents=True,exist_ok=True)
dll=pathlib.Path('D:/UE5/UE_5.8/Engine/Binaries/ThirdParty/libsndfile/Win64/libsndfile-1.dll');handle=os.add_dll_directory(str(dll.parent));lib=ctypes.CDLL(str(dll))
class Info(ctypes.Structure):_fields_=[('frames',ctypes.c_longlong),('rate',ctypes.c_int),('channels',ctypes.c_int),('format',ctypes.c_int),('sections',ctypes.c_int),('seekable',ctypes.c_int)]
lib.sf_open.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(Info)];lib.sf_open.restype=ctypes.c_void_p;lib.sf_readf_float.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_longlong];lib.sf_close.argtypes=[ctypes.c_void_p]
source=S/'1911-near.wav';info=Info();f=lib.sf_open(str(source).encode(),16,ctypes.byref(info));assert f;raw=(ctypes.c_float*(info.frames*info.channels))();lib.sf_readf_float(f,raw,info.frames);lib.sf_close(f);rate=48000
starts=[];block=int(info.rate*.002)
for i in range(0,info.frames-block,block):
 rms=math.sqrt(sum(raw[j*info.channels]**2 for j in range(i,i+block))/block)
 if rms>.10 and (not starts or i-starts[-1]>info.rate*2):starts.append(max(0,i-int(info.rate*.003)))
assert len(starts)==2,starts
report={'source':'The Free Firearm Sound Library, A_42P.wav; near-distance 1911 .45 recording','license':'CC0-1.0','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'synthesis':False,'pitch_shift':False,'takes':{}}
for k,(start,channel) in enumerate([(starts[0],0),(starts[1],0),(starts[0],1)]):
 values=[];last=hp=lp=0.;alpha=math.exp(-2*math.pi*35/info.rate);beta=1-math.exp(-2*math.pi*16000/info.rate)
 for i in range(int(info.rate*1.1)):
  x=float(raw[(start+i)*info.channels+channel]);hp=alpha*(hp+x-last);last=x;lp+=beta*(hp-lp)
  if i%2==0:values.append(lp)
 peak=max(abs(x) for x in values);pcm=array.array('h')
 for i,v in enumerate(values):
  t=i/rate;fade=min(1,t/.0004,(1.1-t)/.12);pcm.append(round(v/peak*.79*max(0,fade)*32767))
 out=D/('field_shot_'+str(k)+'.wav')
 with wave.open(str(out),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
 report['takes'][out.stem]={'source_start_seconds':start/info.rate,'channel':channel,'duration':len(values)/rate,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('New recorded gunshots prepared; no old CZ-52 takes or generated bass layers used')
