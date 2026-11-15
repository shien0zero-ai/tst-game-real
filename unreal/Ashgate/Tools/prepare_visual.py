"""Prepare bounded, attributed first-person arms and CC0 workshop props offline."""
import pathlib, urllib.request, json, hashlib, copy, base64, subprocess, re, html
from glb_geometry import bake_arms, GLB
ROOT=pathlib.Path(__file__).resolve().parents[3]
PROJECT=ROOT/'unreal/Ashgate'
SOURCE=PROJECT/'SourceArt'
CACHE=ROOT/'work/visual-source-cache'
HEAD={'User-Agent':'Ashgate-AssetPreparation/1.0 (offline game development)'}

def download(url,path,expected=None):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        data=urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=90).read()
        if len(data)>90*1024*1024:raise RuntimeError('Unexpected asset size')
        path.write_bytes(data)
    data=path.read_bytes()
    if expected and hashlib.md5(data).hexdigest()!=expected:raise RuntimeError('MD5 mismatch '+str(path))
    return data

def props():
    manifest=[]
    for ident in ('industrial_storage_cart','steel_frame_shelves_02','industrial_caged_sconce'):
        metadata=json.loads(download('https://api.polyhaven.com/info/'+ident,CACHE/(ident+'-info.json')))
        formats=json.loads(download('https://api.polyhaven.com/files/'+ident,CACHE/(ident+'-files.json')))
        entry=formats['gltf']['2k']['gltf']; folder=SOURCE/'Props'/ident
        payload=download(entry['url'],folder/(ident+'.gltf'),entry['md5'])
        records=[]
        for relative,file in entry['include'].items():
            if '..' in pathlib.PurePosixPath(relative).parts:raise RuntimeError('Unsafe companion path')
            data=download(file['url'],folder/relative,file['md5'])
            records.append({'file':relative,'url':file['url'],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        manifest.append({'id':ident,'name':metadata.get('name'),'authors':metadata.get('authors'),'license':'CC0-1.0','license_url':'https://polyhaven.com/license','source':'https://polyhaven.com/a/'+ident,'resolution':'2k','gltf_sha256':hashlib.sha256(payload).hexdigest(),'files':records})
        print('Prepared 2k prop',ident,flush=True)
    (SOURCE/'props-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

def arms():
    folder=SOURCE/'Hands';folder.mkdir(parents=True,exist_ok=True)
    report=bake_arms(ROOT/'assets/raid/enemy.glb',folder)
    # Recover original texture resolution rather than enlarging the reduced game maps.
    manifest=json.loads((ROOT/'tools/source_assets/raid/models-manifest.json').read_text())
    entry=next(x for x in manifest if x['file']=='assets/raid/enemy.glb')
    raw=download(entry['download_url'],CACHE/'soldier_tac.glb')
    if hashlib.sha256(raw).hexdigest()!=entry['source_sha256']:raise RuntimeError('Original guard asset hash changed')
    original=GLB(CACHE/'soldier_tac.glb')
    names={m['name']:m for m in original.doc['materials']};names['Ashgate_Glove']=copy.deepcopy(names['Mil_Suit_R5']);names['Ashgate_Glove']['name']='Ashgate_Glove';names['Ashgate_Glove']['pbrMetallicRoughness']['baseColorFactor']=[.20,.23,.20,1]
    wanted={}
    for side in ('right','left'):
        path=folder/('view_'+side+'.glb'); baked=GLB(path)
        for material in baked.doc['materials']:
            name=material['name']
            if name in names:wanted[name]=copy.deepcopy(names[name])
    # Only export textures referenced by the two arm/clothing materials actually used.
    used_names=set()
    baked=GLB(folder/'view_right.glb')
    for side in ('right','left'):
        b=GLB(folder/('view_'+side+'.glb'))
        used_names.update(b.doc['materials'][p.get('material',0)]['name'] for m in b.doc['meshes'] for p in m['primitives'])
    texture_ids=set()
    def collect(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k.endswith('Texture') and isinstance(v,dict) and 'index' in v:texture_ids.add(v['index'])
                collect(v)
        elif isinstance(value,list):
            for v in value:collect(v)
    for name in used_names:collect(wanted[name])
    originals={}
    for ti in texture_ids:
        tex=original.doc['textures'][ti]; ii=tex.get('source',tex.get('extensions',{}).get('EXT_texture_webp',{}).get('source'))
        if ii is None:raise RuntimeError('Unrecognized texture source')
        originals[ii]=original.image(ii)
    png={}; webp={}
    for ii,data in originals.items():
        if data[:4]==b'\x89PNG':png[ii]=data
        else:webp[str(ii)]=base64.b64encode(data).decode()
    if webp:
        page=CACHE/'decode-hands.html'
        page.write_text('''<body><script>const data='''+json.dumps(webp)+''';Promise.all(Object.entries(data).map(([n,b])=>new Promise((res,rej)=>{let i=new Image();i.onload=()=>{let c=document.createElement('canvas');c.width=i.width;c.height=i.height;c.getContext('2d').drawImage(i,0,0);res([n,c.toDataURL('image/png').split(',')[1]])};i.onerror=rej;i.src='data:image/webp;base64,'+b}))).then(x=>{document.body.innerHTML='';let p=document.createElement('pre');p.id='output';p.textContent=JSON.stringify(Object.fromEntries(x));document.body.append(p)})</script>''',encoding='utf-8')
        command=[r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless','--disable-gpu','--no-first-run','--user-data-dir='+str(CACHE/'edge-profile'),'--virtual-time-budget=10000','--dump-dom',page.as_uri()]
        result=subprocess.run(command,capture_output=True,timeout=120)
        match=re.search(r'<pre id="output">(.*?)</pre>',result.stdout.decode('utf-8',errors='replace'),re.S)
        if not match:raise RuntimeError('Texture decoding failed')
        png.update({int(k):base64.b64decode(v) for k,v in json.loads(html.unescape(match.group(1))).items()})
    textures=[]; images=[]; remap={}
    for ti in sorted(texture_ids):
        tex=original.doc['textures'][ti]; ii=tex.get('source',tex.get('extensions',{}).get('EXT_texture_webp',{}).get('source'))
        filename='original_'+str(ii)+'.png';(folder/'textures'/filename).write_bytes(png[ii])
        remap[ti]=len(textures); textures.append({'source':len(images),'sampler':0});images.append({'uri':'textures/'+filename})
    def replace(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k.endswith('Texture') and isinstance(v,dict) and 'index' in v:v['index']=remap[v['index']]
                replace(v)
        elif isinstance(value,list):
            for v in value:replace(v)
    from glb_geometry import Writer
    for side in ('right','left'):
        b=GLB(folder/('view_'+side+'.glb')); w=Writer();w.doc=b.doc;w.data=bytearray(b.binary[:b.doc['buffers'][0]['byteLength']])
        # Keep material indices stable but only retain texture references for used slots.
        for index,m in enumerate(w.doc['materials']):
            if m['name'] in used_names:
                mat=copy.deepcopy(wanted[m['name']]);replace(mat);w.doc['materials'][index]=mat
            else:w.doc['materials'][index]={'name':m['name'],'pbrMetallicRoughness':{'baseColorFactor':[.1,.1,.1,1],'roughnessFactor':.9}}
        w.doc['textures']=textures;w.doc['images']=images;w.doc['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]
        w.doc.pop('extensionsUsed',None);w.doc.pop('extensionsRequired',None);w.save(folder/('view_'+side+'.glb'))
    report.update(original_texture_source=entry['download_url'],original_texture_sha256=entry['source_sha256'],materials=sorted(used_names),texture_sha256={str(i):hashlib.sha256(data).hexdigest() for i,data in png.items()})
    (folder/'arm-bake.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Prepared authored arms:',report['parts'],flush=True)

if __name__=='__main__':
    CACHE.mkdir(parents=True,exist_ok=True);SOURCE.mkdir(parents=True,exist_ok=True)
    props();arms()
