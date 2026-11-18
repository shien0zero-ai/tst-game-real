"""Validate actual UE master capture against logged distance/occlusion scenarios."""
import argparse,pathlib,wave,array,math,re,json
ap=argparse.ArgumentParser();ap.add_argument('wav',type=pathlib.Path);ap.add_argument('log',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
with wave.open(str(args.wav),'rb') as w:
 assert w.getsampwidth()==2;rate=w.getframerate();ch=w.getnchannels();pcm=array.array('h',w.readframes(w.getnframes()))
text=args.log.read_text(encoding='utf-8',errors='replace');events=re.findall(r'ACOUSTIC QA event=(\d+) recording_s=([\d.]+) distance_m=([\d.]+) blocked=(\d)',text)
assert len(events)==5 and 'ACOUSTIC QA COMPLETE failures=0' in text
burst='ACOUSTIC BURST COMPLETE' in text
assert ((34<=len(pcm)/ch/rate<=37) if burst else (25<=len(pcm)/ch/rate<=28)),'Recording must retain silent intervals; run acoustic QA with submix auto-disable bypassed in this test process'
measure=[]
for event,t,distance,blocked in events:
 start=max(0,int((float(t)-.02)*rate));end=min(len(pcm)//ch,int((float(t)+.65)*rate));values=pcm[start*ch:end*ch]
 rms=math.sqrt(sum((x/32768)**2 for x in values)/len(values));peak=max(abs(x) for x in values)/32768
 measure.append({'event':int(event),'distance_m':float(distance),'blocked':bool(int(blocked)),'rms_dbfs':20*math.log10(max(1e-12,rms)),'peak_dbfs':20*math.log10(max(1e-12,peak))})
clips=sum(abs(x)>=32767 for x in pcm)
checks={'nonzero_audio':max(abs(x) for x in pcm)>500,'no_mix_clipping':clips==0,'10m_louder_than_50m':measure[1]['rms_dbfs']>measure[2]['rms_dbfs']+1,'50m_louder_than_100m':measure[2]['rms_dbfs']>measure[3]['rms_dbfs']+1,'wall_reduces_50m_level':measure[2]['rms_dbfs']>measure[4]['rms_dbfs']+2}
report={'rate':rate,'channels':ch,'seconds':len(pcm)/ch/rate,'clipped_samples':clips,'events':measure,'checks':checks,'note':'RMS across all rendered channels, first 650ms. Includes the active gunshot layers and distance/occlusion processing; not an isolated filter frequency-response test. The original recording can contain full-scale samples even when rendered mix is unclipped.'}
if burst:
 report['burst_shots']=len(re.findall(r'ACOUSTIC BURST index=',text));checks['eight_trigger_pulls']=report['burst_shots']==8
 report['note']+=' Includes eight real trigger pulls with forest ambience; full output checked for clipping.'
out=args.output or args.wav.with_suffix('.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));assert all(checks.values()),checks
