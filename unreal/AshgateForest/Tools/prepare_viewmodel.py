"""Bake new CC0 service pistol and anatomical gloved arms; stdlib only.

See SourceArt/Viewmodel/manifest.json and licenses/forest/VIEWMODEL.txt.
Raw sources stay separate from all previous M1911 and hand assets.
"""
import pathlib,sys,json,math,copy,struct
P=pathlib.Path(__file__).resolve().parents[1];R=P.parents[1];S=P/'SourceArt/Viewmodel';sys.path.insert(0,str(R/'unreal/Ashgate/Tools'))
from glb_geometry import GLB,Writer,mul,point,unit,local,identity
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def scale(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def length(v):return math.sqrt(dot(v,v))
def basis(w,i,p):
 a=unit(sub(i,w));b=sub(p,i);b=unit(sub(b,scale(a,dot(a,b))));return [a,b,unit(cross(a,b))]
def mapping(q,a,b,factors):return [sum(dot(q,a[j])*b[j][k]*factors[j] for j in range(3)) for k in range(3)]
def rotate(a,b):
 a=unit(a);b=unit(b);v=cross(a,b);c=dot(a,b)
 if c<-.999:
  ax=unit(cross(a,[1,0,0] if abs(a[0])<.9 else [0,1,0]));return lambda q:sub(scale(ax,2*dot(ax,q)),q)
 return lambda q:add(add(q,cross(v,q)),scale(cross(v,cross(v,q)),1/max(.00001,1+c)))
def primitive(w,pp,nn,uv,indices,mat=0):return {'attributes':{'POSITION':w.accessor(pp,'VEC3'),'NORMAL':w.accessor(nn,'VEC3'),'TEXCOORD_0':w.accessor(uv,'VEC2')},'indices':w.accessor([[v] for v in indices],'SCALAR',5125),'material':mat}

def pistol():
 d=json.loads((S/'Service/service_pistol.gltf').read_text());raw=(S/'Service/service_pistol.bin').read_bytes();g=GLB.__new__(GLB);g.doc=d;g.binary=raw
 report={}
 for name,nodes in [('service_frame',[0,5,6]),('service_slide',[1]),('service_magazine',[2])]:
  w=Writer();w.doc['materials']=[{'name':'ServiceSteelWood','pbrMetallicRoughness':{'metallicFactor':1,'roughnessFactor':.5}}];prims=[];count=0
  for index in nodes:
   node=d['nodes'][index];transform=local(node) if index!=2 else identity()
   for prim in d['meshes'][node['mesh']]['primitives']:
    a=prim['attributes'];pp=[point(transform,v) for v in g.read(a['POSITION'])];nn=[unit(point(transform,v,0)) for v in g.read(a['NORMAL'])]
    # Source +X forward, +Y up -> shared -Z forward/+Y up weapon coordinates.
    pp=[[v[2],v[1]-.060,-v[0]+.015] for v in pp];nn=[[v[2],v[1],-v[0]] for v in nn];ii=[v[0] for v in g.read(prim['indices'])]
    prims.append(primitive(w,pp,nn,g.read(a['TEXCOORD_0']),ii));count+=len(ii)//3
  w.mesh(name,prims);w.save(S/(name+'.glb'));report[name]={'triangles':count}
 return report

def arms():
 g=GLB(S/'arms.glb');d=g.doc;world=g.pose('T-Pose');named={n.get('name'):i for i,n in enumerate(d['nodes'])};skin=d['skins'][0];ib=g.read(skin['inverseBindMatrices']);palette=[mul(world[n],[[m[c*4+r] for c in range(4)] for r in range(4)]) for n,m in zip(skin['joints'],ib)]
 def pos(n):return point(world[named[n]],[0,0,0])
 right={'index':[[.023,-.027,-.016],[.023,-.027,-.045],[.005,-.034,-.051],[-.009,-.036,-.037]],'middle':[[.027,-.047,-.013],[.013,-.049,-.036],[-.009,-.052,-.031],[-.017,-.051,-.014]],'ring':[[.027,-.065,-.006],[.012,-.067,-.030],[-.010,-.070,-.024],[-.017,-.068,-.007]],'pinky':[[.026,-.083,.001],[.012,-.086,-.022],[-.007,-.088,-.017],[-.014,-.086,-.001]],'thumb':[[.028,-.080,.020],[.012,-.054,.039],[-.018,-.041,.010],[-.025,-.039,-.020]]}
 left={'index':[[-.032,-.061,-.023],[-.020,-.063,-.046],[.004,-.066,-.041],[.016,-.066,-.026]],'middle':[[-.033,-.078,-.017],[-.017,-.080,-.039],[.008,-.082,-.032],[.017,-.080,-.016]],'ring':[[-.033,-.094,-.009],[-.016,-.097,-.032],[.007,-.098,-.025],[.016,-.095,-.007]],'pinky':[[-.032,-.107,.001],[-.015,-.110,-.021],[.005,-.111,-.014],[.013,-.108,.002]],'thumb':[[-.035,-.084,.018],[-.032,-.059,-.005],[-.027,-.044,-.038],[-.023,-.043,-.067]]}
 report={}
 for side,letter,targets in [('right','R',right),('left','L',left)]:
  if side=='left':
   for finger,chain in targets.items():
    if finger!='thumb':
     for target in chain:
      if target[0]<=-.030:target[0]+=.006
  wrist='hand.'+letter;forearm='forearm.'+letter;sw=pos(wrist);se=pos(forearm);tw=[.030,-.110,.028] if side=='right' else [-.040,-.135,.035];te=[.16 if side=='right' else -.16,-.38,.19]
  sb=basis(sw,pos('f_index.01.'+letter),pos('f_pinky.01.'+letter));tb=basis(tw,targets['index'][0],targets['pinky'][0]);factors=[length(sub(targets['index'][0],tw))/length(sub(pos('f_index.01.'+letter),sw)),length(sub(targets['pinky'][0],targets['index'][0]))/length(sub(pos('f_pinky.01.'+letter),pos('f_index.01.'+letter))),.1]
  palm=lambda p:add(tw,mapping(sub(p,sw),sb,tb,factors));normal=lambda n:unit(mapping(n,sb,tb,[1/max(.0001,x) for x in factors]));transforms={named[wrist]:(palm,normal)}
  for finger,points in targets.items():
   prefix=('thumb.' if finger=='thumb' else 'f_'+finger+'.')
   for k in range(1,4):
    n=prefix+f'{k:02d}.'+letter;sp=pos(n);tp=points[k-1]
    if k<3:sn=pos(prefix+f'{k+1:02d}.'+letter)
    else:sn=add(sp,scale(sub(sp,pos(prefix+'02.'+letter)),.80))
    tn=points[k];rot=rotate(mapping(sub(sn,sp),sb,tb,[1,1,1]),sub(tn,tp));factor=length(sub(tn,tp))/length(sub(sn,sp))
    def fit(p,sp=sp,tp=tp,rot=rot,factor=factor):return add(tp,scale(rot(mapping(sub(p,sp),sb,tb,[1,1,1])),factor))
    def norm(n,rot=rot):return unit(rot(mapping(n,sb,tb,[1,1,1])))
    transforms[named[n]]=(fit,norm)
   if finger!='thumb':transforms[named['palm_'+finger+'.'+letter]]=(palm,normal)
  selected=set()
  def visit(i):
   selected.add(i)
   for c in d['nodes'][i].get('children',[]):visit(c)
  visit(named[forearm]);selected_j={j for j,n in enumerate(skin['joints']) if d['nodes'][n].get('name','').endswith('.'+letter) and d['nodes'][n].get('name','').split('.')[0] not in ('upper_arm','clavicle','deltoid')}
  armrot=rotate(sub(sw,se),sub(tw,te));axis=sub(sw,se);arm_scale=length(sub(tw,te))/length(axis)
  def arm(p):return add(tw,scale(armrot(sub(p,sw)),arm_scale))
  w=Writer();w.doc['materials']=[{'name':'AnatomicalLeather','pbrMetallicRoughness':{'baseColorFactor':[.04,.045,.04,1]}},{'name':'WovenSleeve','pbrMetallicRoughness':{'baseColorFactor':[.09,.11,.065,1]}}];prims=[];count=0
  for mesh in d['meshes']:
   for prim in mesh['primitives']:
    a=prim['attributes'];pp=g.read(a['POSITION']);nn=g.read(a['NORMAL']);uv=g.read(a['TEXCOORD_0']);js=g.read(a['JOINTS_0']);ws=g.read(a['WEIGHTS_0']);ii=[v[0] for v in g.read(prim['indices'])];keep=[sum(v for j,v in zip(joints,weights) if j in selected_j)>.7 for joints,weights in zip(js,ws)]
    posed=[];normals=[];hand=[]
    for v in range(len(pp)):
     p=[0.,0.,0.];n=[0.,0.,0.]
     for j,weight in zip(js[v],ws[v]):p=add(p,scale(point(palette[j],pp[v]),weight));n=add(n,scale(point(palette[j],nn[v],0),weight))
     out=[0.,0.,0.];outn=[0.,0.,0.];hw=0.
     for j,weight in zip(js[v],ws[v]):
      if not weight:continue
      bone=skin['joints'][j]
      if bone in transforms:fn,nfn=transforms[bone];q=fn(p);qn=nfn(n);hw+=weight
      else:q=arm(p);qn=armrot(n)
      out=add(out,scale(q,weight));outn=add(outn,scale(qn,weight))
     posed.append(out);normals.append(unit(outn));hand.append(hw)
    for mat in (0,1):
     faces=[ii[k:k+3] for k in range(0,len(ii),3) if all(keep[v] for v in ii[k:k+3]) and (sum(hand[v] for v in ii[k:k+3])/3>=.25)==(mat==0)]
     if not faces:continue
     used=sorted({v for tri in faces for v in tri});remap={v:i for i,v in enumerate(used)};prims.append(primitive(w,[posed[v] for v in used],[normals[v] for v in used],[uv[v] for v in used],[remap[v] for tri in faces for v in tri],mat));count+=len(faces)
  w.mesh('anatomical_'+side,prims);w.save(S/('anatomical_'+side+'.glb'));report[side]={'triangles':count,'wrist':tw,'finger_targets':targets}
 return report

if __name__=='__main__':
 report={'gun':pistol(),'hands':arms()};(S/'geometry-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:{n:v.get('triangles') for n,v in x.items()} for k,x in report.items()}))
