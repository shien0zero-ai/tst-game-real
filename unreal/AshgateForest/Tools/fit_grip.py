"""Bake an articulated two-hand M1911 grip, retaining authored glove topology/UVs."""
import pathlib,sys,copy,json,math,shutil
P=pathlib.Path(__file__).resolve().parents[1];R=P.parents[1]
sys.path.insert(0,str(R/'unreal/Ashgate/Tools'))
from glb_geometry import GLB,Writer,mul,point,unit
S=P/'SourceArt/Grip';S.mkdir(parents=True,exist_ok=True)
shutil.copytree(R/'unreal/Ashgate/SourceArt/Hands/textures',S/'textures',dirs_exist_ok=True)
g=GLB(R/'assets/raid/enemy.glb');d=g.doc;world=g.pose();names={n.get('name'):i for i,n in enumerate(d['nodes'])};skin=d['skins'][0]
ib=g.read(skin['inverseBindMatrices']);palette=[mul(world[n],[[m[c*4+r] for c in range(4)] for r in range(4)]) for n,m in zip(skin['joints'],ib)]
old=GLB(R/'unreal/Ashgate/SourceArt/Hands/view_right.glb')
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def scale(a,s):return [v*s for v in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def length(v):return math.sqrt(dot(v,v))
def rotation(a,b):
 a=unit(a);b=unit(b);v=cross(a,b);c=dot(a,b)
 if c<-.999:
  ax=unit(cross(a,[1,0,0] if abs(a[0])<.9 else [0,1,0]));return lambda q:sub(scale(ax,2*dot(ax,q)),q)
 return lambda q:add(add(q,cross(v,q)),scale(cross(v,cross(v,q)),1/max(.000001,1+c)))
def position(n):return point(world[names[n]],[0,0,0])
def basis(w,i,p):
 a=unit(sub(i,w));b=sub(p,i);b=unit(sub(b,scale(a,dot(a,b))));return [a,b,unit(cross(a,b))]
def map_basis(q,a,b,scales):return [sum(dot(q,a[j])*b[j][k]*scales[j] for j in range(3)) for k in range(3)]
# Gun-local glTF metres: -Z muzzle direction, +Y up. Fingers wrap the front
# strap; thumbs remain beside the frame, below the moving slide.
right={
 'Index':[[.023,-.027,-.025],[.020,-.029,-.052],[.000,-.034,-.056],[-.007,-.035,-.044]],
 'Middle':[[.026,-.046,-.020],[.013,-.048,-.043],[-.009,-.052,-.037],[-.017,-.051,-.020]],
 'Ring':[[.026,-.064,-.012],[.012,-.066,-.035],[-.010,-.069,-.029],[-.017,-.067,-.012]],
 'Pinky':[[.025,-.081,-.006],[.012,-.084,-.027],[-.007,-.086,-.022],[-.014,-.084,-.006]],
 'Thumb':[[.026,-.050,.010],[-.012,-.025,.026],[-.027,-.020,-.006],[-.026,-.022,-.031]]}
left={
 'Index':[[-.031,-.047,-.036],[-.020,-.049,-.056],[.004,-.052,-.051],[.016,-.052,-.036]],
 'Middle':[[-.032,-.064,-.030],[-.017,-.066,-.049],[.008,-.068,-.041],[.017,-.066,-.024]],
 'Ring':[[-.032,-.081,-.022],[-.016,-.084,-.041],[.007,-.085,-.033],[.016,-.082,-.015]],
 'Pinky':[[-.032,-.096,-.014],[-.015,-.099,-.031],[.005,-.100,-.024],[.013,-.097,-.008]],
 'Thumb':[[-.034,-.061,.007],[-.041,-.040,-.011],[-.037,-.034,-.038],[-.033,-.034,-.062]]}
def smooth_glove(positions,normals,uv,faces):
 # One Loop subdivision: weld only geometry; preserve the original UV seams.
 ids={};gpos=[];gi=[]
 for p in positions:
  key=tuple(round(x,6) for x in p)
  if key not in ids:ids[key]=len(gpos);gpos.append(p)
  gi.append(ids[key])
 neighbours=[set() for _ in gpos];edges={}
 for a,b,c in faces:
  aa,bb,cc=gi[a],gi[b],gi[c]
  for v,w,other in ((aa,bb,cc),(bb,cc,aa),(cc,aa,bb)):
   if v!=w:neighbours[v].add(w);neighbours[w].add(v);edges.setdefault(tuple(sorted((v,w))),[]).append(other)
 boundary={}
 for (a,b),op in edges.items():
  if len(op)==1:boundary.setdefault(a,[]).append(b);boundary.setdefault(b,[]).append(a)
 gp=[]
 for i,p in enumerate(gpos):
  if len(boundary.get(i,[]))==2:gp.append(add(scale(p,.75),scale(add(gpos[boundary[i][0]],gpos[boundary[i][1]]),.125)))
  else:
   n=len(neighbours[i]);beta=3/(8*n) if n>3 else 3/16;v=scale(p,1-n*beta)
   for j in neighbours[i]:v=add(v,scale(gpos[j],beta))
   gp.append(v)
 edgepos={}
 for (a,b),op in edges.items():
  if len(op)==2:edgepos[(a,b)]=add(scale(add(gpos[a],gpos[b]),.375),scale(add(gpos[op[0]],gpos[op[1]]),.125))
  else:edgepos[(a,b)]=scale(add(gpos[a],gpos[b]),.5)
 pp=[gp[i] for i in gi];tt=list(uv);new=[];cache={}
 def midpoint(a,b):
  key=tuple(sorted((a,b)))
  if key not in cache:
   cache[key]=len(pp);pp.append(edgepos.get(tuple(sorted((gi[a],gi[b]))),scale(add(positions[a],positions[b]),.5)));tt.append(scale(add(uv[a],uv[b]),.5))
  return cache[key]
 for a,b,c in faces:
  ab,bc,ca=midpoint(a,b),midpoint(b,c),midpoint(c,a);new.extend([(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
 accum={}
 for a,b,c in new:
  n=cross(sub(pp[b],pp[a]),sub(pp[c],pp[a]))
  for i in (a,b,c):
   key=tuple(round(x,6) for x in pp[i]);accum[key]=add(accum.get(key,[0,0,0]),n)
 nn=[unit(accum.get(tuple(round(x,6) for x in p),[0,1,0])) for p in pp]
 return pp,nn,tt,new

report={'units':'metres in original gun glTF coordinates','source':'assets/raid/enemy.glb, aim_idle','method':'affine palm fitting and per-phalanx frame fitting; source skin weights, UVs and normals retained','parts':{}}
for side in ('right','left'):
 prefix=side.title()+'Hand';sw=position(prefix);se=position(side.title()+'ForeArm');tw=[.031,-.103,.018] if side=='right' else [-.046,-.128,.025]
 targets=copy.deepcopy(right if side=='right' else left)
 if side=='left':
  for finger,points in targets.items():
   if finger!='Thumb':
    for p in points:p[1]-=.010
 sb=basis(sw,position(prefix+'Index1'),position(prefix+'Pinky1'));tb=basis(tw,targets['Index'][0],targets['Pinky'][0])
 palm_scales=[length(sub(targets['Index'][0],tw))/length(sub(position(prefix+'Index1'),sw)),length(sub(targets['Pinky'][0],targets['Index'][0]))/length(sub(position(prefix+'Pinky1'),position(prefix+'Index1'))),.72]
 def palm(p):return add(tw,map_basis(sub(p,sw),sb,tb,palm_scales))
 def normal_palm(n):return unit(map_basis(n,sb,tb,[1/max(.1,v) for v in palm_scales]))
 transforms={names[prefix]:(palm,normal_palm)}
 for finger,points in targets.items():
  for k in range(1,5):
   name=prefix+finger+str(k)
   if name not in names:continue
   sp=position(name);tp=points[k-1]
   sn=position(prefix+finger+str(min(k+1,4)));tn=points[min(k,3)]
   if k==4:sp_prev=position(prefix+finger+'3');sn=add(sp,sub(sp,sp_prev));tn=add(tp,sub(tp,points[2]))
   base_dir=map_basis(sub(sn,sp),sb,tb,[1,1,1]);rot=rotation(base_dir,sub(tn,tp));factor=length(sub(tn,tp))/max(.00001,length(sub(sn,sp)))
   def fit(p,sp=sp,tp=tp,rot=rot,factor=factor):return add(tp,scale(rot(map_basis(sub(p,sp),sb,tb,[1,1,1])),factor))
   def norm(n,rot=rot):return unit(rot(map_basis(n,sb,tb,[1,1,1])))
   transforms[names[name]]=(fit,norm)
 descendants=set()
 def visit(i):
  descendants.add(i)
  for j in d['nodes'][i].get('children',[]):visit(j)
 visit(names[side.title()+'ForeArm']);selected={j for j,n in enumerate(skin['joints']) if n in descendants}
 # Keep the authored sleeve, redirecting its elbow behind and below the view.
 te=[.16 if side=='right' else -.16,-.38,.19];axis=sub(sw,se);axis_len=length(axis);au=unit(axis);target_axis=sub(tw,te);rot_arm=rotation(au,target_axis)
 def arm(p):
  q=sub(p,sw);f=max(-1,min(0,dot(q,au)/axis_len));radial=sub(q,scale(axis,f));return add(add(tw,scale(target_axis,f)),scale(rot_arm(radial),.72))
 w=Writer();w.doc.update({key:copy.deepcopy(old.doc[key]) for key in ('materials','images','textures','samplers')})
 prims=[];tris=0
 for mesh in d['meshes']:
  for prim in mesh['primitives']:
   a=prim['attributes'];pos=g.read(a['POSITION']);nn=g.read(a['NORMAL']);uv=g.read(a['TEXCOORD_0']);js=g.read(a['JOINTS_0']);ws=g.read(a['WEIGHTS_0']);ii=[v[0] for v in g.read(prim['indices'])]
   keep=[sum(v for j,v in zip(joints,weights) if j in selected)>=.45 for joints,weights in zip(js,ws)]
   chosen=[ii[k:k+3] for k in range(0,len(ii),3) if all(keep[v] for v in ii[k:k+3])]
   if not chosen:continue
   used=sorted({v for tri in chosen for v in tri});remap={v:i for i,v in enumerate(used)};pp=[];normals=[]
   for v in used:
    p=[0,0,0];n=[0,0,0]
    # Bake skinning first, then reuse the same influences to articulate each phalanx.
    for j,weight in zip(js[v],ws[v]):
     if weight:
      p=add(p,scale(point(palette[j],pos[v]),weight));n=add(n,scale(point(palette[j],nn[v],0),weight))
    out=[0,0,0];outn=[0,0,0]
    for j,weight in zip(js[v],ws[v]):
     if not weight:continue
     bone=skin['joints'][j]
     if bone in transforms:fn,nfn=transforms[bone];q=fn(p);qn=nfn(n)
     else:q=arm(p);qn=rot_arm(n)
     out=add(out,scale(q,weight));outn=add(outn,scale(qn,weight))
    pp.append(out);normals.append(unit(outn))
   texcoords=[uv[v] for v in used];faces=[[remap[v] for v in tri] for tri in chosen]
   if 'Gloves' in mesh.get('name',''):pp,normals,texcoords,faces=smooth_glove(pp,normals,texcoords,faces)
   attributes={'POSITION':w.accessor(pp,'VEC3'),'NORMAL':w.accessor(normals,'VEC3'),'TEXCOORD_0':w.accessor(texcoords,'VEC2')}
   material=len(w.doc['materials'])-1 if 'Gloves' in mesh.get('name','') else prim.get('material',0)
   prims.append({'attributes':attributes,'indices':w.accessor([[v] for tri in faces for v in tri],'SCALAR',5125),'material':material});tris+=len(faces)
 w.mesh('grip_'+side,prims);w.save(S/('grip_'+side+'.glb'));report['parts'][side]={'wrist':tw,'targets':targets,'triangles':tris}
(S/'grip-fit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('Articulated grip prepared',flush=True)
