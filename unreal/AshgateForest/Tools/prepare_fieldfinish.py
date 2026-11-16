"""Field-finish geometry: semantic materials, physical edge masks, grip wrap and muzzle depth.

Original viewmodel meshes and all original texture pixels remain untouched.
Extra UV sets encode barycentrics and triangle altitudes in metres, permitting
sub-millimetre edge wear without painting every triangulation edge.
"""
import pathlib,sys,math,json,struct,collections
P=pathlib.Path(__file__).resolve().parents[1];R=P.parents[1];S=P/'SourceArt/FieldFinish';V=P/'SourceArt/Viewmodel';sys.path.insert(0,str(R/'unreal/Ashgate/Tools'))
from glb_geometry import GLB,Writer,unit
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def scale(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def length(a):return math.sqrt(dot(a,a))
def center(points):return [sum(v[k] for v in points)/len(points) for k in range(3)]
MATERIALS=['FieldSteel','FieldPolymer','FieldRubber','FieldBore','FieldControls','FieldCrown']

def hull(points):
 points=sorted(set((round(x,6),round(z,6)) for x,z in points))
 def area(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 lo=[];hi=[]
 for p in points:
  while len(lo)>1 and area(lo[-2],lo[-1],p)<=0:lo.pop()
  lo.append(p)
 for p in reversed(points):
  while len(hi)>1 and area(hi[-2],hi[-1],p)<=0:hi.pop()
  hi.append(p)
 return lo[:-1]+hi[:-1]

def main():
 S.mkdir(parents=True,exist_ok=True);data=(S/'arm-samples.bin').read_bytes();width,height=struct.unpack_from('<ii',data);pixels=data[8:]
 def metallic(uv):return pixels[(min(height-1,max(0,int(uv[1]*height)))*width+min(width-1,max(0,int(uv[0]*width))))*3+2]/255
 report={'units':'metres','materials':MATERIALS,'wear_band_metres':[.00012,.00045],'meshes':{}}
 for part in ['frame','slide','magazine']:
  g=GLB(V/('service_'+part+'.glb'));surfaces=[];source_triangles=[]
  for prim_index,prim in enumerate(g.doc['meshes'][0]['primitives']):
   a=prim['attributes'];pp=g.read(a['POSITION']);nn=g.read(a['NORMAL']);uv=g.read(a['TEXCOORD_0']);ii=[x[0] for x in g.read(prim['indices'])];faces=[ii[i:i+3] for i in range(0,len(ii),3)]
   normals=[unit(cross(sub(pp[b],pp[a]),sub(pp[c],pp[a]))) for a,b,c in faces];centers=[center([pp[i] for i in f]) for f in faces];edges=collections.defaultdict(list)
   weld=[tuple(round(v,6) for v in p) for p in pp]
   for f,tri in enumerate(faces):
    for a,b in [(tri[1],tri[2]),(tri[2],tri[0]),(tri[0],tri[1])]:edges[tuple(sorted((weld[a],weld[b])))].append(f)
   for f,tri in enumerate(faces):
    points=[pp[i] for i in tri];c=centers[f];tex=center([[*uv[i],0] for i in tri]);mat=4 if part=='frame' and prim_index>0 else 0
    if part=='frame' and prim_index==0 and c[1]<-.018 and c[2]>-.055 and abs(c[0])>.009 and metallic(tex)<.38:mat=1
    bits=[];alt=[]
    for k,(a,b) in enumerate([(tri[1],tri[2]),(tri[2],tri[0]),(tri[0],tri[1])]):
     adjacent=edges[tuple(sorted((weld[a],weld[b])))];hard=len(adjacent)==1
     for other in adjacent:
      if other!=f and dot(normals[f],normals[other])<.78 and dot(sub(centers[f],centers[other]),normals[f])>1e-7:hard=True
     bits.append(float(hard));alt.append(length(cross(sub(points[(k+1)%3],points[k]),sub(points[(k+2)%3],points[k])))/max(1e-8,length(sub(pp[a],pp[b]))))
    surfaces.append((points,[nn[i] for i in tri],[uv[i] for i in tri],mat,bits,alt));source_triangles.append(points)
  def triangle(points,normals,uv,mat):
   if dot(cross(sub(points[1],points[0]),sub(points[2],points[0])),center(normals))<0:points=[points[0],points[2],points[1]];normals=[normals[0],normals[2],normals[1]];uv=[uv[0],uv[2],uv[1]]
   surfaces.append((points,normals,uv,mat,[0,0,0],[1,1,1]))
  if part=='frame':
   # A thin, bevelled rubber sleeve follows the actual grip cross-section.
   y=-.092;intersections=[]
   for tri in source_triangles:
    for a,b in [(tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])]:
     if (a[1]-y)*(b[1]-y)<0:
      t=(y-a[1])/(b[1]-a[1]);p=add(a,scale(sub(b,a),t))
      if p[2]>-.04:intersections.append((p[0],p[2]))
   outline=hull(intersections);assert len(outline)>5,'Missing grip section';cx=sum(x for x,z in outline)/len(outline);cz=sum(z for x,z in outline)/len(outline)
   # Resample perimeter so bevel thickness remains consistent around corners.
   perimeter=[]
   for a,b in zip(outline,outline[1:]+outline[:1]):
    count=max(1,int(math.hypot(b[0]-a[0],b[1]-a[1])/.0015))
    for k in range(count):perimeter.append((a[0]+(b[0]-a[0])*k/count,a[1]+(b[1]-a[1])*k/count))
   profiles=[(-.098,.00020),(-.0976,.00085),(-.0864,.00085),(-.086,.00020)];rings=[];n=len(perimeter)
   for yy,offset in profiles:
    ring=[]
    for x,z in perimeter:
     radial=unit([x-cx,0,z-cz]);ring.append(([x+radial[0]*offset,yy,z+radial[2]*offset],radial))
    rings.append(ring)
   for j in range(len(rings)-1):
    for i in range(n):
     k=(i+1)%n;a,an=rings[j][i];b,bn=rings[j][k];c,cn=rings[j+1][k];d,dn=rings[j+1][i]
     triangle([a,b,c],[an,bn,cn],[[i/n,j/3],[(i+1)/n,j/3],[(i+1)/n,(j+1)/3]],2);triangle([a,c,d],[an,cn,dn],[[i/n,j/3],[(i+1)/n,(j+1)/3],[i/n,(j+1)/3]],2)
   # Dense circular crown with a recessed bore: real silhouette/depth, not a black decal.
   near=[v for tri in source_triangles for v in tri if v[2]<-.155 and abs(v[0])>.004];cx=(min(v[0] for v in near)+max(v[0] for v in near))/2;cy=(min(v[1] for v in near)+max(v[1] for v in near))/2;z=min(v[2] for v in near)-.00015
   # A 48-sided outer barrel skin rounds the formerly angular exposed profile.
   barrel_rings=[(z+.0015,.0075),(z+.003,.0076),(-.094,.0076),(-.091,.0078)]
   for j in range(len(barrel_rings)-1):
    za,ra=barrel_rings[j];zb,rb=barrel_rings[j+1]
    for i in range(48):
     ta=i*2*math.pi/48;tb=(i+1)*2*math.pi/48
     def bp(r,z,t):return [cx+r*math.cos(t),cy+r*math.sin(t),z]
     a,b,c,d=bp(ra,za,ta),bp(ra,za,tb),bp(rb,zb,tb),bp(rb,zb,ta);na=[math.cos(ta),math.sin(ta),0];nb=[math.cos(tb),math.sin(tb),0]
     triangle([a,b,c],[na,nb,nb],[[i/48,j/3],[(i+1)/48,j/3],[(i+1)/48,(j+1)/3]],5);triangle([a,c,d],[na,nb,na],[[i/48,j/3],[(i+1)/48,(j+1)/3],[i/48,(j+1)/3]],5)
   profiles=[(.0075,z+.0015),(.0078,z+.00035),(.0076,z),(.0046,z),(.0044,z+.0012),(.0044,z+.012)]
   for j in range(len(profiles)-1):
    ra,za=profiles[j];rb,zb=profiles[j+1]
    for i in range(48):
     t=i*2*math.pi/48;q=(i+1)*2*math.pi/48
     def v(r,z,t):return [cx+r*math.cos(t),cy+r*math.sin(t),z]
     a,b,c,d=v(ra,za,t),v(ra,za,q),v(rb,zb,q),v(rb,zb,t)
     sign=-1 if j>=3 else 1;na=[0,0,-1] if j==2 else unit([sign*math.cos(t),sign*math.sin(t),-.4]);nb=[0,0,-1] if j==2 else unit([sign*math.cos(q),sign*math.sin(q),-.4]);mat=3 if j>=3 else 5
     triangle([a,b,c],[na,nb,nb],[[i/48,j/5],[(i+1)/48,j/5],[(i+1)/48,(j+1)/5]],mat);triangle([a,c,d],[na,nb,na],[[i/48,j/5],[(i+1)/48,(j+1)/5],[i/48,(j+1)/5]],mat)
  w=Writer();w.doc['materials']=[{'name':n,'pbrMetallicRoughness':{'metallicFactor':0 if n in ('FieldPolymer','FieldRubber') else 1,'roughnessFactor':.6}} for n in MATERIALS];prims=[];counts={}
  for mat in range(len(MATERIALS)):
   selected=[s for s in surfaces if s[3]==mat]
   if not selected:continue
   pp=[];nn=[];uv=[];bary=[];alt0=[];alt1=[];colors=[]
   for points,normals,tex,_,bits,heights in selected:
    for i in range(3):pp.append(points[i]);nn.append(normals[i]);uv.append(tex[i]);bary.append(([1,0],[0,1],[0,0])[i]);alt0.append(heights[:2]);alt1.append([heights[2],0]);colors.append(bits+[1])
   attrs={'POSITION':w.accessor(pp,'VEC3'),'NORMAL':w.accessor(nn,'VEC3'),'TEXCOORD_0':w.accessor(uv,'VEC2'),'TEXCOORD_1':w.accessor(bary,'VEC2'),'TEXCOORD_2':w.accessor(alt0,'VEC2'),'TEXCOORD_3':w.accessor(alt1,'VEC2'),'COLOR_0':w.accessor(colors,'VEC4')};prims.append({'attributes':attrs,'indices':w.accessor([[i] for i in range(len(pp))],'SCALAR',5125),'material':mat});counts[MATERIALS[mat]]=len(selected)
  name='field_'+part;w.mesh(name,prims);w.save(S/(name+'.glb'));report['meshes'][name]={'triangles':len(surfaces),'material_triangles':counts,'uv_channels':4}
 (S/'geometry-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
