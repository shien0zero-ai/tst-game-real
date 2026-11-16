"""Prepare CC0 photogrammetry/foliage assets, selecting individual authored variants."""
import pathlib,json,urllib.request,hashlib,copy,struct,math,random
P=pathlib.Path(__file__).resolve().parents[1];R=P.parents[1];C=R/'work/forest-source-cache';S=P/'SourceArt';C.mkdir(parents=True,exist_ok=True)
HEAD={'User-Agent':'Ashgate-Forest-AssetPreparation/1.0 (offline game development)'}
def fetch(url,path,md5=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=180) as resp,path.open('wb') as f:
   total=0
   while True:
    b=resp.read(1024*1024)
    if not b:break
    total+=len(b)
    if total>650*1024*1024:raise RuntimeError('Unexpected file size')
    f.write(b)
 data=path.read_bytes()
 if md5 and hashlib.md5(data).hexdigest()!=md5:raise RuntimeError('Source changed '+str(path))
 return data

class RemoteBuffer:
 def __init__(self,url,ident,records):self.url=url;self.ident=ident;self.records=records
 def __getitem__(self,span):
  start,stop=span.start,span.stop;path=C/(self.ident+'-'+str(start)+'-'+str(stop)+'.range')
  if not path.exists():
   headers=dict(HEAD);headers['Range']='bytes='+str(start)+'-'+str(stop-1)
   with urllib.request.urlopen(urllib.request.Request(self.url,headers=headers),timeout=180) as r:
    if r.status!=206 or r.headers.get('Content-Range','').split('/')[0]!='bytes '+str(start)+'-'+str(stop-1):raise RuntimeError('Incorrect source byte range')
    data=r.read(stop-start+1)
    if len(data)!=stop-start:raise RuntimeError('Source range length mismatch')
    path.write_bytes(data)
  data=path.read_bytes();self.records.append({'url':self.url,'range':[start,stop-1],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});return data

def write_glb(doc,blob,path):
 doc['buffers']=[{'byteLength':len(blob)}];j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*((-len(j))%4);blob+=b'\0'*((-len(blob))%4)
 path.write_bytes(struct.pack('<III',0x46546c67,2,28+len(j)+len(blob))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(blob),0x004e4942)+blob)

def variant(g,raw,mi,name):
 d={k:copy.deepcopy(g[k]) for k in ('asset','materials','images','textures','samplers') if k in g};d['meshes']=[copy.deepcopy(g['meshes'][mi])];d['nodes']=[{'name':name,'mesh':0}];d['scenes']=[{'nodes':[0]}];d['scene']=0
 d['accessors']=[];d['bufferViews']=[];data=bytearray();mapping={};views={}
 for prim in d['meshes'][0]['primitives']:
  refs=list(prim['attributes'].items())+[('indices',prim['indices'])]
  for key,old in refs:
   if old not in mapping:
    a=copy.deepcopy(g['accessors'][old]);v=a['bufferView']
    if v not in views:
     view=copy.deepcopy(g['bufferViews'][v]);start=view.get('byteOffset',0)
     while len(data)%4:data.append(0)
     block=raw[start:start+view['byteLength']];view['byteOffset']=len(data);view['buffer']=0;data.extend(block);views[v]=len(d['bufferViews']);d['bufferViews'].append(view)
    a['bufferView']=views[v];mapping[old]=len(d['accessors']);d['accessors'].append(a)
   if key=='indices':prim['indices']=mapping[old]
   else:prim['attributes'][key]=mapping[old]
 for mat in d.get('materials',[]):
  if mat.get('alphaMode')=='BLEND':mat['alphaMode']='MASK';mat['alphaCutoff']=.45
  mat['doubleSided']=True
 if len(data)<85*1024*1024:write_glb(d,bytes(data),S/'Models'/(name+'.glb'))
 else:
  # Preserve the source geometry while keeping each Git-managed buffer below 60 MiB.
  chunks=[];chunk=bytearray()
  for view in d['bufferViews']:
   old=view['byteOffset'];block=data[old:old+view['byteLength']]
   if len(chunk)+len(block)>60*1024*1024 and chunk:chunks.append(bytes(chunk));chunk=bytearray()
   while len(chunk)%4:chunk.append(0)
   view['buffer']=len(chunks);view['byteOffset']=len(chunk);chunk.extend(block)
  chunks.append(bytes(chunk));d['buffers']=[]
  for i,chunk in enumerate(chunks):
   filename=name+'_'+str(i)+'.bin';(S/'Models'/filename).write_bytes(chunk);d['buffers'].append({'uri':filename,'byteLength':len(chunk)})
  (S/'Models'/(name+'.gltf')).write_text(json.dumps(d,separators=(',',':')),encoding='utf-8')

manifest=[]
alpha_manifest={}
models={'pine_tree_01':[(1,'pine_canopy')],'fir_tree_01':[(2,'fir_canopy'),(1,'fir_lush')],'fir_sapling':[(0,'sapling_a'),(1,'sapling_b'),(2,'sapling_c')],'fern_02':[(i,'fern_'+str(i)) for i in range(4)],'grass_medium_01':[(i,'grass_'+str(i)) for i in (0,2,4,7,8)],'rock_moss_set_01':[(i,'moss_rock_'+str(i)) for i in range(6)],'tree_stump_01':[(0,'stump')],'dead_tree_trunk':[(0,'fallen_log')]}
for id,variants in models.items():
 meta=json.loads(fetch('https://api.polyhaven.com/info/'+id,C/(id+'-info.json')));files=json.loads(fetch('https://api.polyhaven.com/files/'+id,C/(id+'-files.json')));entry=files['gltf']['2k']['gltf']
 g=json.loads(fetch(entry['url'],C/(id+'.gltf'),entry['md5']));raw=None;records=[]
 for relative,item in entry['include'].items():
  isbin=relative.endswith('.bin');dest=C/(id+'-'+pathlib.Path(relative).name) if isbin else S/'Models'/relative
  if id=='pine_tree_01' and isbin:raw=RemoteBuffer(item['url'],id,records);continue
  data=fetch(item['url'],dest,item['md5']);records.append({'file':relative,'url':item['url'],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
  if isbin:raw=data
 if raw is None:raise RuntimeError('No model buffer')
 for key in files:
  if key.lower().endswith('alpha'):
   kinds=files[key]['2k'];kind='png' if 'png' in kinds else 'jpg';item=kinds[kind];relative='textures/'+id+'_'+key+'.'+kind;data=fetch(item['url'],S/'Models'/relative,item['md5']);alpha_manifest[id]={'uri':relative,'key':key};records.append({'file':relative,'url':item['url'],'sha256':hashlib.sha256(data).hexdigest()})
 for mi,name in variants:variant(g,raw,mi,name)
 manifest.append({'id':id,'authors':meta.get('authors'),'source':'https://polyhaven.com/a/'+id,'license':'CC0-1.0','gltf_source_url':entry['url'],'gltf_source_md5':entry['md5'],'gltf_source_sha256':hashlib.sha256((C/(id+'.gltf')).read_bytes()).hexdigest(),'variants':variants,'files':records});print('Prepared',id,flush=True)
for id in ('forest_ground_04','rocky_trail'):
 meta=json.loads(fetch('https://api.polyhaven.com/info/'+id,C/(id+'-info.json')));files=json.loads(fetch('https://api.polyhaven.com/files/'+id,C/(id+'-files.json')));records=[]
 for channel,key in (('color','Diffuse'),('normal','nor_gl'),('orm','arm')):
  available=files[key]['4k'];kind='jpg' if 'jpg' in available else 'png';entry=available[kind];data=fetch(entry['url'],S/'Surfaces'/(id+'_'+channel+'.'+kind),entry['md5']);records.append({'map':channel,'url':entry['url'],'sha256':hashlib.sha256(data).hexdigest()})
 manifest.append({'id':id,'authors':meta.get('authors'),'source':'https://polyhaven.com/a/'+id,'license':'CC0-1.0','resolution':'4k','files':records});print('Prepared 4k ground',id,flush=True)
(S/'sources.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

# A sloping, meandering forest trail with real height variation, not a flat plane.
def trail(x):return 12*math.sin(x*.025)+3*math.sin(x*.065)
def height(x,y):
 d=abs(y-trail(x));return 5+3*math.sin(x*.018)+2*math.cos(y*.027)+1.2*math.sin((x+y)*.035)-.8*math.exp(-d*d/12)+.10*math.sin(x*1.2)*math.sin(y*.8)+.035*math.sin(x*3+y*2)
N=257;pos=[];norm=[];uv=[];col=[];indices=[]
for j in range(N):
 for i in range(N):
  x=i-128;y=j-128;z=height(x,y);dx=(height(x+.1,y)-height(x-.1,y))/.2;dy=(height(x,y+.1)-height(x,y-.1))/.2;n=[-dx,1,-dy];l=sum(v*v for v in n)**.5
  pos.append((x,z,y));norm.append(tuple(v/l for v in n));uv.append((x/2,y/2));d=abs(y-trail(x));w=max(0,min(1,(2.15-d)/.65));col.append((w,0,0,1))
for j in range(N-1):
 for i in range(N-1):
  a=j*N+i;b=a+1;c=a+N;indices.extend([(a,c,b),(b,c,c+1)])
doc={'asset':{'version':'2.0'},'bufferViews':[],'accessors':[],'meshes':[],'nodes':[{'mesh':0,'name':'forest_terrain'}],'scenes':[{'nodes':[0]}],'scene':0};data=bytearray()
def acc(rows,typ,fmt='f',ct=5126):
 while len(data)%4:data.append(0)
 start=len(data)
 for row in rows:data.extend(struct.pack('<'+fmt*len(row),*row))
 vi=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(data)-start});a={'bufferView':vi,'componentType':ct,'count':len(rows),'type':typ}
 if typ=='VEC3':a.update(min=[min(v[k] for v in rows) for k in range(3)],max=[max(v[k] for v in rows) for k in range(3)])
 ai=len(doc['accessors']);doc['accessors'].append(a);return ai
attrs={'POSITION':acc(pos,'VEC3'),'NORMAL':acc(norm,'VEC3'),'TEXCOORD_0':acc(uv,'VEC2'),'COLOR_0':acc(col,'VEC4')};ix=acc([(v,) for tri in indices for v in tri],'SCALAR','I',5125)
doc['meshes']=[{'name':'forest_terrain','primitives':[{'attributes':attrs,'indices':ix}]}];write_glb(doc,bytes(data),S/'Models/forest_terrain.glb')
print('Prepared 256m terrain / 131072 triangles',flush=True)

(S/'asset-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(S/'foliage-alpha.json').write_text(json.dumps(alpha_manifest,indent=2),encoding='utf-8')
