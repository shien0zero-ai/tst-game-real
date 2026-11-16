"""Adapt licensed field recordings/foley with Python stdlib and UE's existing libsndfile.

Run with --cache pointing to the original downloads listed in manifest.json.
No installation, engine edits, or network access are performed by this script.
"""
import argparse,array,ctypes,hashlib,json,math,os,pathlib,random,wave

RATE=48000
def main():
    cli=argparse.ArgumentParser();cli.add_argument('--only-pistol',action='store_true',help='Rebuild only gunshot takes; retain every other WAV and manifest entry');cli.add_argument('--cache',type=pathlib.Path,required=True);cli.add_argument('--project',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);cli.add_argument('--engine',type=pathlib.Path,default=pathlib.Path('D:/UE5/UE_5.8'));args=cli.parse_args()
    out=args.project/'SourceArt/Audio';out.mkdir(parents=True,exist_ok=True);cache=args.cache
    dll=args.engine/'Engine/Binaries/ThirdParty/libsndfile/Win64/libsndfile-1.dll';dllpath=os.add_dll_directory(str(dll.parent));lib=ctypes.CDLL(str(dll))
    class Info(ctypes.Structure):_fields_=[('frames',ctypes.c_longlong),('rate',ctypes.c_int),('channels',ctypes.c_int),('format',ctypes.c_int),('sections',ctypes.c_int),('seekable',ctypes.c_int)]
    lib.sf_open.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(Info)];lib.sf_open.restype=ctypes.c_void_p
    lib.sf_seek.argtypes=[ctypes.c_void_p,ctypes.c_longlong,ctypes.c_int];lib.sf_readf_float.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_longlong];lib.sf_close.argtypes=[ctypes.c_void_p]
    report=json.loads((out/'manifest.json').read_text(encoding='utf-8')) if args.only_pistol and (out/'manifest.json').exists() else {'rate':RATE,'sources':{},'outputs':{}}
    urls={'park_ambience_birds.wav':'https://opengameart.org/sites/default/files/park_ambience_birds.wav','park_ambience_wind.wav':'https://opengameart.org/sites/default/files/park_ambience_wind.wav','steps.zip':'https://opengameart.org/sites/default/files/%5Bkdd%5DDifferentSteps_0.zip','gunreload1.wav':'https://opengameart.org/sites/default/files/gunreload1.wav','sounds.zip':'https://opengameart.org/sites/default/files/sounds.zip'}
    for name,url in urls.items():report['sources'][name]={'url':url,'sha256':hashlib.sha256((cache/name).read_bytes()).hexdigest()}
    def read(rel,start=0,duration=None,stereo=False):
        f=cache/rel;info=Info();h=lib.sf_open(str(f).encode(),16,ctypes.byref(info));assert h,f
        offset=int(start*info.rate);lib.sf_seek(h,offset,0);count=min(info.frames-offset,int(duration*info.rate) if duration else info.frames-offset);buf=(ctypes.c_float*(count*info.channels))();lib.sf_readf_float(h,buf,count);lib.sf_close(h)
        channels=2 if stereo else 1;result=[array.array('f') for _ in range(channels)]
        for i in range(int(count*RATE/info.rate)):
            x=min(count-1,int(i*info.rate/RATE))
            for c in range(channels):result[c].append(float(buf[x*info.channels+min(c,info.channels-1)]) if stereo else sum(buf[x*info.channels+j] for j in range(info.channels))/info.channels)
        return result
    def filt(data,hp=80,lp=10000):
        a=math.exp(-2*math.pi*hp/RATE);b=1-math.exp(-2*math.pi*lp/RATE)
        for channel in data:
            prev=high=low=0.
            for i,x in enumerate(channel):high=a*(high+x-prev);prev=x;low+=b*(high-low);channel[i]=low
        return data
    def loop(data,seconds=2):
        n=int(seconds*RATE)
        for k,c in enumerate(data):
            # Rotate the head into a linear tail crossfade, with no silent gap.
            blend=array.array('f',(c[len(c)-n+i]*(1-i/n)+c[i]*(i/n) for i in range(n)))
            data[k]=c[n:-n]+blend
        return data
    def save(name,data,peak=.65,fade=.005,note=''):
        n=min(len(c) for c in data);m=max(abs(v) for c in data for v in c) or 1;gain=peak/m;edge=int(fade*RATE);pcm=array.array('h')
        for i in range(n):
            env=min(1,i/max(1,edge),(n-1-i)/max(1,edge)) if fade else 1
            for c in data:pcm.append(round(max(-.98,min(.98,c[i]*gain*env))*32767))
        f=out/(name+'.wav')
        with wave.open(str(f),'wb') as w:w.setnchannels(len(data));w.setsampwidth(2);w.setframerate(RATE);w.writeframes(pcm.tobytes())
        report['outputs'][name]={'seconds':n/RATE,'channels':len(data),'peak':peak,'note':note,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()};print(name,round(n/RATE,3),flush=True)
    if not args.only_pistol:
        save('forest_birds',loop(filt(read('park_ambience_birds.wav',35,54,True),300,8500)),.48,0,'Thimras; 35s excerpt, filtered, 2s wrap crossfade')
        save('forest_wind',loop(filt(read('park_ambience_wind.wav',20,44,True),110,2100)),.42,0,'Thimras; 20s excerpt, filtered, 2s wrap crossfade')
        for name,source in [('step_trail_0','gravel.ogg'),('step_trail_1','mud02.ogg'),('step_leaves_0','leaves01.ogg'),('step_leaves_1','leaves02.ogg')]:save(name,filt(read('steps/'+source),65,7000),.50,note='TinyWorlds; mono, DC/rumble removal, peak normalization')
    # Locate the four real handgun transients; retain three different takes.
    raw=filt(read('shots/sounds/cz.wav'),170,10000)[0];starts=[];block=240
    for i in range(0,len(raw)-block,block):
        rms=math.sqrt(sum(v*v for v in raw[i:i+block])/block)
        if rms>.095 and (not starts or i-starts[-1]>RATE*.8):starts.append(max(0,i-240))
    assert len(starts)>=3,starts
    full=filt(read('shots/sounds/cz.wav'),65,9000)[0]
    for j,start in enumerate(starts[:3]):
        sample=full[start:start+int(RATE*1.3)];low=0.;coef=1-math.exp(-2*math.pi*330/RATE)
        for i,x in enumerate(sample):
            t=i/RATE;low+=coef*(x-low)
            # Preserve the recorded crack; add chest/body energy rather than only gain.
            phase=2*math.pi*(88*t+2.9*(1-math.exp(-18*t)))
            body=.24*math.sin(phase)*math.exp(-22*t)*min(1,t*1800)
            envelope=math.exp(-max(0,t-.23)*3.3)
            sample[i]=math.tanh((x+1.4*low+body)*1.55)*envelope
        save('pistol_fire_'+str(j),[sample],.88,.0008,'Vincent Sevedge / Tabasco CZ-52 derivative: 65Hz high-pass, 330Hz body shelf, original short 140-to-88Hz impact layer, soft saturation and longer gated tail; not an authentic M1911 recording')
    if not args.only_pistol:
        reload=filt(read('gunreload1.wav'),200,11000)[0]
        for name,a,b in [('mag_out',.06,.31),('mag_in',.62,1.07),('slide_release',1.20,1.47),('dry_fire',.12,.17)]:save(name,[reload[int(a*RATE):int(b*RATE)]],.55,.004,'SpringySpringo airsoft pistol; isolated mechanical transient')
        rng=random.Random(1911);cloth=array.array('f',(rng.uniform(-1,1)*math.sin(math.pi*i/(RATE*.24))**2 for i in range(int(RATE*.24))));save('gear_rustle',filt([cloth],180,1800),.18,.012,'Original filtered-noise cloth layer; synthesized, not a field recording')
        # Quiet brass-like tick, with rapid decay so it does not ring like concrete in a forest.
        brass=array.array('f',((math.sin(i/RATE*2*math.pi*3460)+.45*math.sin(i/RATE*2*math.pi*5173))*math.exp(-i/RATE*65) for i in range(int(RATE*.17))));save('case_soft',filt([brass],700,6500),.18,.001,'Original synthesized quiet metallic casing accent; not a recorded casing')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
