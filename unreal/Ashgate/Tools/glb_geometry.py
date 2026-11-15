"""Small dependency-free glTF reader/writer for attributed offline mesh preparation."""
import json, struct, math, pathlib, copy

def identity(): return [[float(i==j) for j in range(4)] for i in range(4)]
def mul(a,b): return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def point(m,v,w=1): return [sum(m[i][j]*v[j] for j in range(3))+m[i][3]*w for i in range(3)]
def unit(v):
    n=math.sqrt(sum(x*x for x in v)); return [x/max(n,1e-12) for x in v]
def local(n):
    if 'matrix' in n: return [[n['matrix'][j*4+i] for j in range(4)] for i in range(4)]
    x,y,z,w=n.get('rotation',[0,0,0,1]); sx,sy,sz=n.get('scale',[1,1,1])
    r=[[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w,0], [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w,0], [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y,0],[0,0,0,1]]
    for i in range(3):
        for j,s in enumerate((sx,sy,sz)): r[i][j]*=s
        r[i][3]=n.get('translation',[0,0,0])[i]
    return r

class GLB:
    def __init__(self,path):
        self.path=pathlib.Path(path); b=self.path.read_bytes()
        size=struct.unpack_from('<I',b,12)[0]; self.doc=json.loads(b[20:20+size]); self.binary=b[28+size:]
    def read(self,index):
        a=self.doc['accessors'][index]; v=self.doc['bufferViews'][a['bufferView']]
        fmt,nbytes={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}[a['componentType']]
        count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        start=v.get('byteOffset',0)+a.get('byteOffset',0); stride=v.get('byteStride',nbytes*count)
        out=[list(struct.unpack_from('<'+fmt*count,self.binary,start+i*stride)) for i in range(a['count'])]
        if a.get('normalized') and fmt!='f':
            divisor={5120:127,5121:255,5122:32767,5123:65535}[a['componentType']]
            out=[[max(-1,x/divisor) for x in row] for row in out]
        return out
    def image(self,index):
        image=self.doc['images'][index]
        if 'uri' in image: return (self.path.parent/image['uri']).read_bytes()
        view=self.doc['bufferViews'][image['bufferView']]; start=view.get('byteOffset',0)
        return self.binary[start:start+view['byteLength']]
    def pose(self,clip='aim_idle',time=0):
        nodes=copy.deepcopy(self.doc['nodes'])
        animation=next(a for a in self.doc.get('animations',[]) if a['name']==clip)
        for channel in animation['channels']:
            sampler=animation['samplers'][channel['sampler']]; times=[v[0] for v in self.read(sampler['input'])]; values=self.read(sampler['output'])
            hi=next((i for i,t in enumerate(times) if t>=time),len(times)-1); lo=max(0,hi-1)
            f=0 if times[hi]==times[lo] else (time-times[lo])/(times[hi]-times[lo]); a,b=values[lo],values[hi]
            path=channel['target']['path']
            if path=='rotation' and sum(x*y for x,y in zip(a,b))<0: b=[-x for x in b]
            value=[x+(y-x)*f for x,y in zip(a,b)]
            if path=='rotation': value=unit(value)
            nodes[channel['target']['node']][path]=value
        parent={c:i for i,n in enumerate(nodes) for c in n.get('children',[])}; world={}
        def transform(i):
            if i not in world: world[i]=mul(transform(parent[i]),local(nodes[i])) if i in parent else local(nodes[i])
            return world[i]
        for i in range(len(nodes)): transform(i)
        return world

class Writer:
    def __init__(self):
        self.data=bytearray(); self.doc={'asset':{'version':'2.0','generator':'Ashgate offline asset adapter'},'buffers':[{'byteLength':0}],'bufferViews':[],'accessors':[],'meshes':[],'nodes':[],'scenes':[{'nodes':[]}],'scene':0,'materials':[]}
    def accessor(self,rows,kind,component=5126):
        while len(self.data)%4:self.data.append(0)
        start=len(self.data); fmt='f' if component==5126 else 'I'
        for row in rows:self.data.extend(struct.pack('<'+fmt*len(row),*row))
        vi=len(self.doc['bufferViews']); self.doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(self.data)-start})
        ai=len(self.doc['accessors']); a={'bufferView':vi,'componentType':component,'count':len(rows),'type':kind}
        if kind=='VEC3': a.update(min=[min(r[i] for r in rows) for i in range(3)],max=[max(r[i] for r in rows) for i in range(3)])
        self.doc['accessors'].append(a); return ai
    def mesh(self,name,primitives):
        mi=len(self.doc['meshes']); ni=len(self.doc['nodes']); self.doc['meshes'].append({'name':name,'primitives':primitives}); self.doc['nodes'].append({'name':name,'mesh':mi}); self.doc['scenes'][0]['nodes'].append(ni)
    def save(self,path):
        self.doc['buffers'][0]['byteLength']=len(self.data)
        j=json.dumps(self.doc,separators=(',',':')).encode(); j+=b' '*((-len(j))%4)
        self.data.extend(b'\0'*((-len(self.data))%4))
        pathlib.Path(path).write_bytes(struct.pack('<III',0x46546c67,2,28+len(j)+len(self.data))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(self.data),0x004e4942)+self.data)

def bake_arms(source,out):
    g=GLB(source); d=g.doc; world=g.pose(); named={n.get('name'):i for i,n in enumerate(d['nodes'])}
    skin=d['skins'][0]; matrices=g.read(skin['inverseBindMatrices']); palette=[mul(world[n],[[m[c*4+r] for c in range(4)] for r in range(4)]) for n,m in zip(skin['joints'],matrices)]
    wrist=point(world[named['RightHand']],[0,0,0]); elbow=point(world[named['RightForeArm']],[0,0,0])
    flip=wrist[2]>elbow[2]
    def orient(p): return [-p[0],p[1],-p[2]] if flip else p
    reference=orient(wrist); target=[.025,-.115,-.030]
    report={'pose':'aim_idle at 0 seconds','source_wrist':wrist,'source_elbow':elbow,'flip_yaw_180':flip,'target_wrist_m':target,'parts':{}}
    for side in ('right','left'):
        root=named[side.title()+'ForeArm']; descendants=set()
        def visit(n):
            descendants.add(n)
            for c in d['nodes'][n].get('children',[]): visit(c)
        visit(root); selected={i for i,n in enumerate(skin['joints']) if n in descendants}
        handroot=named[side.title()+'Hand']; descendants=set();visit(handroot)
        handjoints={i for i,n in enumerate(skin['joints']) if n in descendants}
        sw=point(world[handroot],[0,0,0]);se=point(world[root],[0,0,0])
        tw=target if side=='right' else [-.035,-.135,-.040]
        te=[.15 if side=='right' else -.15,-.38,.18]
        axis=[sw[k]-se[k] for k in range(3)];length=sum(v*v for v in axis)**.5; au=unit(axis);bu=unit([tw[k]-te[k] for k in range(3)])
        cross=lambda a,b:[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        rotation_axis=cross(au,bu);c=sum(a*b for a,b in zip(au,bu))
        def rotate(q):
            x=cross(rotation_axis,q);y=cross(rotation_axis,x)
            return [q[k]+x[k]+y[k]/max(.001,1+c) for k in range(3)]
        def deform(p,n,js,ws):
            # Correct the inherited full-body elbow pose for a first-person two-hand grip.
            # Preserve authored finger topology and UVs; elbow cut planes extend behind the camera.
            h=min(1,max(0,(sum(v for j,v in zip(js,ws) if j in handjoints)-.05)/.9))
            q=[p[k]-sw[k] for k in range(3)];hp=[tw[0]-q[0]*.65,tw[1]-q[1]*.65,tw[2]+q[2]*.65];hn=[-n[0],-n[1],n[2]]
            f=max(-1.0,min(0.0,sum(q[k]*au[k] for k in range(3))/length))
            radial=[q[k]-f*axis[k] for k in range(3)];radial=rotate(radial)
            fp=[tw[k]+f*(tw[k]-te[k])+radial[k]*.8 for k in range(3)];fn=rotate(n)
            return [fp[k]*(1-h)+hp[k]*h for k in range(3)],unit([fn[k]*(1-h)+hn[k]*h for k in range(3)])
        writer=Writer(); writer.doc['materials']=copy.deepcopy(d['materials']); writer.doc['images']=copy.deepcopy(d.get('images',[])); writer.doc['textures']=copy.deepcopy(d.get('textures',[])); writer.doc['samplers']=copy.deepcopy(d.get('samplers',[]))
        # Images are shared between both arms; PNG bytes are copied without resampling.
        image_dir=pathlib.Path(out)/'textures'; image_dir.mkdir(parents=True,exist_ok=True)
        for i,im in enumerate(writer.doc['images']):
            suffix='.png' if g.image(i)[:4]==b'\x89PNG' else '.jpg'
            filename='tactical_'+str(i)+suffix; (image_dir/filename).write_bytes(g.image(i)); im.clear(); im['uri']='textures/'+filename
        glovemat=copy.deepcopy(writer.doc['materials'][4]);glovemat['name']='Ashgate_Glove';glovemat['pbrMetallicRoughness']['baseColorFactor']=[.20,.23,.20,1];glove_index=len(writer.doc['materials']);writer.doc['materials'].append(glovemat)
        primitives=[]; allpoints=[]; triangles=0
        for mesh in d['meshes']:
            for prim in mesh['primitives']:
                a=prim['attributes']; positions=g.read(a['POSITION']); normals=g.read(a['NORMAL']); uv=g.read(a['TEXCOORD_0']); joints=g.read(a['JOINTS_0']); weights=g.read(a['WEIGHTS_0'])
                keep=[sum(w for j,w in zip(js,ws) if j in selected)>=.45 for js,ws in zip(joints,weights)]
                indices=[x[0] for x in g.read(prim['indices'])]
                chosen=[indices[i:i+3] for i in range(0,len(indices),3) if all(keep[x] for x in indices[i:i+3])]
                if not chosen:continue
                used=sorted(set(x for tri in chosen for x in tri)); remap={v:i for i,v in enumerate(used)}; pp=[]; nn=[]
                for v in used:
                    p=[0.,0.,0.]; n=[0.,0.,0.]
                    for j,w in zip(joints[v],weights[v]):
                        if w==0:continue
                        q=point(palette[j],positions[v]); normal=point(palette[j],normals[v],0)
                        for k in range(3):p[k]+=q[k]*w;n[k]+=normal[k]*w
                    if 'Gloves' in mesh.get('name',''):
                        q=[p[k]-sw[k] for k in range(3)];p=[tw[0]-q[0]*.65,tw[1]-q[1]*.65,tw[2]+q[2]*.65];n=[-n[0],-n[1],n[2]]
                    else:
                        p,n=deform(p,n,joints[v],weights[v])
                    pp.append(p);nn.append(unit(n));allpoints.append(p)
                attributes={'POSITION':writer.accessor(pp,'VEC3'),'NORMAL':writer.accessor(nn,'VEC3'),'TEXCOORD_0':writer.accessor([uv[v] for v in used],'VEC2')}
                primitives.append({'attributes':attributes,'indices':writer.accessor([[remap[v]] for tri in chosen for v in tri],'SCALAR',5125),'material':glove_index if 'Gloves' in mesh.get('name','') else prim.get('material',0)})
                triangles+=len(chosen)
        if not primitives: raise RuntimeError('No arm geometry selected')
        writer.mesh('view_'+side,primitives); writer.save(pathlib.Path(out)/('view_'+side+'.glb'))
        report['parts'][side]={'triangles':triangles,'bounds_m':[[min(p[k] for p in allpoints),max(p[k] for p in allpoints)] for k in range(3)]}
    (pathlib.Path(out)/'arm-bake.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); return report
