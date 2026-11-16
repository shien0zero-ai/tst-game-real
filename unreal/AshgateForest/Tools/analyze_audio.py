"""Check an actual UE master-submix WAV for silence/clipping; no playback or writes."""
import argparse,array,json,math,pathlib,wave

def analyze(path):
    with wave.open(str(path)) as w:
        if w.getsampwidth()!=2:raise ValueError('Expected signed 16-bit PCM from UE recorder')
        values=array.array('h',w.readframes(w.getnframes()));rate=w.getframerate();channels=w.getnchannels();frames=w.getnframes()
    if frames<rate*10:raise ValueError('Capture too short for a forest gameplay check')
    peak=max(abs(v) for v in values)/32768
    clipped=sum(abs(v)>=32760 for v in values)
    rms=math.sqrt(sum((v/32768)**2 for v in values)/len(values))
    seconds=[]
    for i in range(0,len(values),rate*channels):
        block=values[i:i+rate*channels];seconds.append(round(math.sqrt(sum((v/32768)**2 for v in block)/len(block)),6))
    result={'file':str(path),'seconds':frames/rate,'rate':rate,'channels':channels,'peak_dbfs':round(20*math.log10(max(peak,1e-12)),2),'rms_dbfs':round(20*math.log10(max(rms,1e-12)),2),'clipped_samples':clipped,'one_second_rms':seconds}
    if rms<.0001 or peak<.002:raise ValueError('Silent/near-silent render; verify foreground or temporary capture launch flags')
    if clipped:raise ValueError('Clipping detected: '+str(clipped))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('wav',type=pathlib.Path);args=p.parse_args();print(json.dumps(analyze(args.wav),indent=2))
