"""Restore the losslessly packed native pine mesh; preserve any local edits."""
from pathlib import Path
import hashlib,gzip,json
P=Path(__file__).resolve().parents[1];folder=P/'SourceArt/Packed';manifest_path=folder/'manifest.json'
if not manifest_path.exists():raise RuntimeError('Packed asset manifest missing; run the forest asset import instead')
m=json.loads(manifest_path.read_text(encoding='utf-8'));target=(P/m['destination']).resolve()
if not target.is_relative_to(P):raise RuntimeError('Unsafe asset destination')
if target.exists():
 if hashlib.sha256(target.read_bytes()).hexdigest()!=m['sha256']:raise RuntimeError('Existing pine asset differs; preserving local edits. Repack intentionally instead of overwriting it.')
 print('Native pine asset already verified')
else:
 blocks=[]
 for part in m['parts']:
  path=(folder/part['file']).resolve()
  if not path.is_relative_to(folder.resolve()):raise RuntimeError('Unsafe packed path')
  data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=part['sha256']:raise RuntimeError('Packed part hash mismatch')
  blocks.append(data)
 data=gzip.decompress(b''.join(blocks))
 if len(data)!=m['bytes'] or hashlib.sha256(data).hexdigest()!=m['sha256']:raise RuntimeError('Restored asset hash mismatch')
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);print('Restored and verified:',target)
