"""Analyze wall-clock benchmark frames; keep tail stalls and report each route."""
import csv,pathlib,argparse,statistics,json
p=argparse.ArgumentParser();p.add_argument('csv',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args();rows=list(csv.DictReader(a.csv.open(encoding='utf-8-sig')))
def stats(rows):
 values=sorted(float(x['frame_ms']) for x in rows);n=len(values);assert n>100
 return {'frames':n,'duration_s':sum(values)/1000,'mean_fps':1000/statistics.mean(values),'mean_ms':statistics.mean(values),'p95_ms':values[min(n-1,int(n*.95))],'p99_ms':values[min(n-1,int(n*.99))],'one_percent_low_fps':1000/statistics.mean(values[-max(1,n//100):]),'mean_gpu_ms':statistics.mean(float(x['gpu_ms']) for x in rows),'mean_game_ms':statistics.mean(float(x['game_ms']) for x in rows),'mean_render_ms':statistics.mean(float(x['render_ms']) for x in rows)}
report={'resolution':'1920x1080','screen_percentage':100,'scalability':4,'warmup_seconds_per_route':10,'route_seconds':25,'routes':{str(k):stats([r for r in rows if int(r['segment'])==k]) for k in range(3)},'overall':stats(rows),'targets':{str(k):stats(rows)['mean_fps']>=k for k in [100,80,60]},'limits':'Three automated 25s routes: trail walking, grove camera sweep, trail walking. Startup, per-route 10s warmup excluded; no screenshots or cooking during measurement. Does not guarantee all parts of forest or user display presentation/latency.'}
(a.output or a.csv.with_suffix('.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
