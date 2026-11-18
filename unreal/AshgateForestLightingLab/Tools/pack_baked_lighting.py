"""Preserve the lab's baked lighting losslessly in Git-sized chunks."""
import pathlib,hashlib,json,zlib
P=pathlib.Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 source=P/'Content/Maps/ForestLightingPatch_BuiltData.uasset';data=source.read_bytes();assert len(data)>1000000,'Lighting has not been baked'
 packed=zlib.compress(data,9);folder=P/'SourceArt/Packed';folder.mkdir(parents=True,exist_ok=True);pieces=[]
 for i,offset in enumerate(range(0,len(packed),40*1024*1024),1):
  block=packed[offset:offset+40*1024*1024];name=f'forest-lighting.zlib.part{i:02}';(folder/name).write_bytes(block);pieces.append({'file':name,'bytes':len(block),'sha256':sha(block)})
 manifest={'target':'Content/Maps/ForestLightingPatch_BuiltData.uasset','bytes':len(data),'sha256':sha(data),'format':'zlib','engine':'5.8.4','quality':'Production','map_sha256':sha((P/'Content/Maps/ForestLightingPatch.umap').read_bytes()),'pieces':pieces}
 assert zlib.decompress(packed)==data
 (folder/'lighting-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(f'Preserved {len(data)} bytes of baked lighting in {len(pieces)} verified chunks ({len(packed)} bytes)')
if __name__=='__main__':main()
