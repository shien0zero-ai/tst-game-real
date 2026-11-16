"""Losslessly preserve native Unreal assets that exceed GitHub's single-file limit."""
import pathlib,json,gzip,hashlib
P=pathlib.Path(__file__).resolve().parents[1];target=P/'SourceArt/Packed';target.mkdir(parents=True,exist_ok=True)
file=P/'Content/Forest/Meshes/pine_canopy.uasset';raw=file.read_bytes();sha=hashlib.sha256(raw).hexdigest();packed=gzip.compress(raw,compresslevel=6,mtime=0);parts=[]
for i,start in enumerate(range(0,len(packed),45*1024*1024)):
 data=packed[start:start+45*1024*1024];name='pine-'+sha[:12]+'.part'+str(i).zfill(2);(target/name).write_bytes(data);parts.append({'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(target/'manifest.json').write_text(json.dumps({'destination':'Content/Forest/Meshes/pine_canopy.uasset','compression':'gzip','bytes':len(raw),'sha256':sha,'parts':parts},indent=2),encoding='utf-8')
print('Preserved native asset losslessly:',len(raw),'bytes;',len(packed),'compressed bytes;',len(parts),'parts')
