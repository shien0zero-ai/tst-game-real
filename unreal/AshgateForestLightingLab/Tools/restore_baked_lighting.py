"""Restore missing baked lighting, checking every chunk and the final SHA256.

An existing local bake is retained, including an edited bake. No engine or base-demo file is touched.
"""
import pathlib,hashlib,json,zlib,argparse
P=pathlib.Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
 folder=P/'SourceArt/Packed';m=json.loads((folder/'lighting-manifest.json').read_text());parts=[]
 for item in m['pieces']:
  part=(folder/item['file']).read_bytes();assert len(part)==item['bytes'] and sha(part)==item['sha256'],'Packed lighting chunk failed integrity check';parts.append(part)
 data=zlib.decompress(b''.join(parts));assert len(data)==m['bytes'] and sha(data)==m['sha256'],'Restored lighting failed integrity check'
 target=(P/m['target']).resolve();assert target.is_relative_to((P/'Content').resolve())
 if args.verify_only:print('Packed lighting round-trip SHA256 verification passed');return
 if target.exists():
  state='matches saved source' if sha(target.read_bytes())==m['sha256'] else 'local edited bake retained'
  print('Existing lighting preserved: '+state);return
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);print('Restored verified baked lighting: '+str(target))
if __name__=='__main__':main()
