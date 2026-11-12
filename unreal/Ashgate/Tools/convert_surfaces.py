"""Decode existing lossless WebP with the installed Edge, without installing packages.
Uses embedded data URLs in an offline temporary page; canvas exports PNG pixels.
Run using the Python bundled with UE. Output is ignored Intermediate/ArtSource.
"""
import base64, html, json, pathlib, re, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[3]
PROJECT = pathlib.Path(__file__).resolve().parents[1]
OUT = PROJECT / "Intermediate" / "ArtSource"
OUT.mkdir(parents=True, exist_ok=True)
sources = list((ROOT / "assets/raid/textures").glob("*.webp"))
payload = {p.stem: base64.b64encode(p.read_bytes()).decode() for p in sources}
page = OUT / "decode.html"
page.write_text('''<!doctype html><meta charset="utf-8"><body><script>
const data = ''' + json.dumps(payload) + ''';
Promise.all(Object.entries(data).map(([name,b64])=>new Promise((resolve,reject)=>{
 const img=new Image(); img.onload=()=>{let c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);resolve([name,c.toDataURL('image/png').split(',')[1]]);};img.onerror=reject;img.src='data:image/webp;base64,'+b64;
}))).then(items=>{document.body.innerHTML='';const pre=document.createElement('pre');pre.id='output';pre.textContent=JSON.stringify(Object.fromEntries(items));document.body.appendChild(pre);});
</script>''', encoding="utf-8")
edge = pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
result = subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--user-data-dir="+str(OUT/"edge-profile"), "--virtual-time-budget=10000", "--dump-dom", page.as_uri()], capture_output=True, timeout=90)
(OUT/"decoder-stderr.txt").write_bytes(result.stderr)
match = re.search(r'<pre id="output">(.*?)</pre>', result.stdout.decode("utf-8", errors="replace"),re.S)
if not match:
    raise RuntimeError("Edge did not decode the embedded images: " + result.stderr.decode(errors="replace")[-1000:])
for name, value in json.loads(html.unescape(match.group(1))).items():
    (OUT/(name+".png")).write_bytes(base64.b64decode(value))
print("Decoded",len(sources),"existing WebP maps to PNG without resampling")
