"""Match the grip with rigid hand rotations, blending only through sleeves."""
import pathlib,sys,json,math
P=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(P.parents[1]/'unreal/Ashgate/Tools'))
from glb_geometry import GLB,Writer,unit
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
D=P/'SourceArt/GripFit';D.mkdir(parents=True,exist_ok=True);report={}
for side in ['right','left']:
 source=P/'SourceArt/Viewmodel'/('anatomical_'+side+'.glb');g=GLB(source);w=Writer();w.doc['materials']=g.doc['materials'];primitives=[]
 angle=math.radians(-19 if side=='right' else -15);cs=math.cos(angle);sn=math.sin(angle);cy,cz=(-.027,-.016) if side=='right' else (-.061,-.023);dy,dz=(0,0) if side=='right' else (.006,.018);minimum_jacobian=10.
 for prim in g.doc['meshes'][0]['primitives']:
  pp=g.read(prim['attributes']['POSITION']);nn=g.read(prim['attributes']['NORMAL']);uv=g.read(prim['attributes']['TEXCOORD_0']);out=[];norm=[]
  for p,n in zip(pp,nn):
   x,y,z=p;t=max(0,min(1,(y+.30)/.14));f=t*t*(3-2*t);df=(6*t*(1-t)/.14) if 0<t<1 else 0.
   ry=cy+cs*(y-cy)-sn*(z-cz)+dy;rz=cz+sn*(y-cy)+cs*(z-cz)+dz;delta_y=ry-y;delta_z=rz-z
   out.append([x,y+f*delta_y,z+f*delta_z])
   cols=[[1,0,0],[0,1+f*(cs-1)+df*delta_y,f*sn+df*delta_z],[0,-f*sn,1+f*(cs-1)]]
   cof=[cross(cols[1],cols[2]),cross(cols[2],cols[0]),cross(cols[0],cols[1])];det=dot(cols[0],cof[0]);minimum_jacobian=min(minimum_jacobian,det);norm.append(unit([sum(n[j]*cof[j][k] for j in range(3)) for k in range(3)]))
  attrs={'POSITION':w.accessor(out,'VEC3'),'NORMAL':w.accessor(norm,'VEC3'),'TEXCOORD_0':w.accessor(uv,'VEC2')};primitives.append({'attributes':attrs,'indices':w.accessor(g.read(prim['indices']),'SCALAR',5125),'material':prim['material']})
 assert minimum_jacobian>0,minimum_jacobian
 name='gripfit_'+side;w.mesh(name,primitives);w.save(D/(name+'.glb'));report[side]={'source':source.relative_to(P).as_posix(),'triangles':sum(len(g.read(p['indices']))//3 for p in g.doc['meshes'][0]['primitives']),'minimum_jacobian':minimum_jacobian,'grip_rotation_degrees':math.degrees(angle),'translation_cm':[0,dy*100,dz*100],'note':'Hand/finger shape is rigid; sleeves blend continuously. Static finger-pose and mesh-detail limits remain.'}
(D/'geometry-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
