"""Import new offline visual assets and rebuild project-only triplanar surfaces."""
import unreal as u
import pathlib,json
P=pathlib.Path(u.Paths.project_dir()).resolve()
A='/Game/Art';e=u.EditorAssetLibrary;t=u.AssetToolsHelpers.get_asset_tools();m=u.MaterialEditingLibrary
report={}
for source in list((P/'SourceArt/Hands').glob('view_*.glb'))+list((P/'SourceArt/Props').glob('*/*.gltf')):
    name=source.stem; stable=A+'/Meshes/'+name
    if name.startswith('view_') or not e.does_asset_exist(stable):
        pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL
        pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.animation_pipeline.import_animations=False
        stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe)
        task=u.AssetImportTask();task.filename=str(source);task.destination_path=(A+'/Meshes' if name.startswith('view_') else A+'/Visual/'+name);task.destination_name=name;task.replace_existing=True;task.automated=True;task.save=True;task.options=stack
        t.import_asset_tasks([task]);meshes=[e.load_asset(x) for x in task.imported_object_paths if isinstance(e.load_asset(x),u.StaticMesh)]
        if len(meshes)!=1:raise RuntimeError('Expected one mesh '+str(source))
        if meshes[0].get_path_name().split('.')[0]!=stable and not e.rename_asset(meshes[0].get_path_name(),stable):raise RuntimeError('Rename failed')
    mesh=e.load_asset(stable)
    settings=mesh.get_editor_property('nanite_settings');settings.enabled=False;mesh.set_editor_property('nanite_settings',settings)
    bounds=mesh.get_bounds();report[name]={'origin':str(bounds.origin),'extent':str(bounds.box_extent),'slots':[str(x.material_slot_name) for x in mesh.static_materials]}
    e.save_loaded_asset(mesh,only_if_is_dirty=False)
    u.log('VISUAL MESH '+name+' '+str(report[name]))
# Existing mesh reimports may keep a new material slot unassigned. Build the glove
# PBR material explicitly from the verified original maps, then assign both hands.
import sys
sys.path.insert(0,str(P/'Tools'))
from glb_geometry import GLB
b=GLB(P/'SourceArt/Hands/view_right.glb');d=b.doc
source=next(x for x in d['materials'] if x['name']=='Ashgate_Glove')
texmap={}
for key,ref in (('color',source['pbrMetallicRoughness'].get('baseColorTexture')),('normal',source.get('normalTexture')),('orm',source['pbrMetallicRoughness'].get('metallicRoughnessTexture'))):
    if not ref:continue
    image=d['images'][d['textures'][ref['index']]['source']]
    file=P/'SourceArt/Hands'/image['uri'];path=A+'/ViewTextures/'+file.stem
    if not e.does_asset_exist(path):
        task=u.AssetImportTask();task.filename=str(file);task.destination_path=A+'/ViewTextures';task.automated=True;task.save=True;t.import_asset_tasks([task])
    texture=e.load_asset(path)
    if key=='normal':texture.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);texture.set_editor_property('srgb',False);texture.set_editor_property('flip_green_channel',True)
    elif key=='orm':texture.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS);texture.set_editor_property('srgb',False)
    texture.set_editor_property('max_texture_size',2048);e.save_loaded_asset(texture,only_if_is_dirty=False);texmap[key]=texture
path=A+'/Materials/ViewGloves'
mat=e.load_asset(path) if e.does_asset_exist(path) else t.create_asset('ViewGloves',A+'/Materials',u.Material,u.MaterialFactoryNew())
m.delete_all_material_expressions(mat)
for key,texture in texmap.items():
    sample=m.create_material_expression(mat,u.MaterialExpressionTextureSample);sample.texture=texture
    if key=='normal':
        sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL;m.connect_material_property(sample,'RGB',u.MaterialProperty.MP_NORMAL)
    elif key=='orm':
        sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS;m.connect_material_property(sample,'G',u.MaterialProperty.MP_ROUGHNESS);m.connect_material_property(sample,'B',u.MaterialProperty.MP_METALLIC)
    else:
        tint=m.create_material_expression(mat,u.MaterialExpressionConstant3Vector);tint.constant=u.LinearColor(.20,.23,.20)
        multiply=m.create_material_expression(mat,u.MaterialExpressionMultiply);m.connect_material_expressions(sample,'RGB',multiply,'A');m.connect_material_expressions(tint,'',multiply,'B');m.connect_material_property(multiply,'',u.MaterialProperty.MP_BASE_COLOR)
mat.set_editor_property('used_with_nanite',True);m.recompile_material(mat);e.save_loaded_asset(mat,only_if_is_dirty=False)
for name in ('view_right','view_left'):
    mesh=e.load_asset(A+'/Meshes/'+name)
    for index,slot in enumerate(mesh.static_materials):
        if str(slot.material_slot_name)=='Ashgate_Glove':mesh.set_material(index,mat)
    e.save_loaded_asset(mesh,only_if_is_dirty=False)
    report[name]['materials']=[str(x.material_interface.get_path_name()) if x.material_interface else None for x in mesh.static_materials]
# Persist the intended non-Nanite mode of pre-existing translucent lamp/generator.
for name in ('lamp','generator'):
    mesh=e.load_asset(A+'/Meshes/'+name);settings=mesh.get_editor_property('nanite_settings');settings.enabled=False;mesh.set_editor_property('nanite_settings',settings);e.save_loaded_asset(mesh,only_if_is_dirty=False)

for path in e.list_assets(A+'/Visual',recursive=True,include_folder=False):
    a=e.load_asset(path)
    if isinstance(a,u.Material):
        a.set_editor_property('used_with_nanite',True);m.recompile_material(a);e.save_loaded_asset(a,only_if_is_dirty=False)

def ex(mat,cls):return m.create_material_expression(mat,cls)
def connect(a,out,b,inp):
    if not m.connect_material_expressions(a,out,b,inp):raise RuntimeError('Connection '+inp)
for surface in ('asphalt','concrete','brick','corrugated','steel','wood'):
    mat=e.load_asset(A+'/Materials/'+surface);m.delete_all_material_expressions(mat)
    mat.set_editor_property('tangent_space_normal',False)
    pos=ex(mat,u.MaterialExpressionWorldPosition);n=ex(mat,u.MaterialExpressionVertexNormalWS)
    textures={}
    for suffix in ('color','roughness','normalgl'):
        tex=ex(mat,u.MaterialExpressionTextureObject);tex.texture=e.load_asset(A+'/Surfaces/'+surface+'_'+suffix);textures[suffix]=tex
    color=ex(mat,u.MaterialExpressionMaterialFunctionCall);color.set_material_function(e.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture'))
    size=ex(mat,u.MaterialExpressionConstant3Vector);size.constant=u.LinearColor(200,200,200)
    connect(textures['color'],'',color,'TextureObject');connect(size,'',color,'TextureSize')
    tint=ex(mat,u.MaterialExpressionVectorParameter);tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',u.LinearColor(1,1,1,1))
    mul=ex(mat,u.MaterialExpressionMultiply);connect(color,'XYZ Texture',mul,'A');connect(tint,'',mul,'B');m.connect_material_property(mul,'',u.MaterialProperty.MP_BASE_COLOR)
    for kind in ('roughness','normalgl'):
        node=ex(mat,u.MaterialExpressionCustom)
        ins=[]
        for name in ('P','N','T'):
            ci=u.CustomInput();ci.set_editor_property('input_name',name);ins.append(ci)
        node.set_editor_property('inputs',ins)
        connect(pos,'',node,'P');connect(n,'',node,'N');connect(textures[kind],'',node,'T')
        base='float3 w=pow(abs(N),4); w/=max(dot(w,float3(1,1,1)),0.001); float3 q=P*0.005; '
        if kind=='roughness':
            node.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1)
            code=base+'return clamp(Texture2DSample(T,TSampler,q.yz).r*w.x+Texture2DSample(T,TSampler,q.xz).r*w.y+Texture2DSample(T,TSampler,q.xy).r*w.z,0.48,1.0);'
            prop=u.MaterialProperty.MP_ROUGHNESS
        else:
            node.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT3)
            code=base+'''float2 ax=(Texture2DSample(T,TSampler,q.yz).rg*2-1)*0.55; float2 ay=(Texture2DSample(T,TSampler,q.xz).rg*2-1)*0.55; float2 az=(Texture2DSample(T,TSampler,q.xy).rg*2-1)*0.55;
float3 nx=float3(sqrt(saturate(1-dot(ax,ax)))*sign(N.x),ax.x,ax.y); float3 ny=float3(ay.x,sqrt(saturate(1-dot(ay,ay)))*sign(N.y),ay.y); float3 nz=float3(az.x,az.y,sqrt(saturate(1-dot(az,az)))*sign(N.z)); return normalize(nx*w.x+ny*w.y+nz*w.z);'''
            prop=u.MaterialProperty.MP_NORMAL
        node.set_editor_property('code',code)
        m.connect_material_property(node,'',prop)
    metal=ex(mat,u.MaterialExpressionConstant);metal.r=.65 if surface in ('steel','corrugated') else 0;m.connect_material_property(metal,'',u.MaterialProperty.MP_METALLIC)
    m.recompile_material(mat);e.save_loaded_asset(mat,only_if_is_dirty=False)
e.save_directory(A,only_if_is_dirty=True,recursive=True)
(P/'Saved/visual-import-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
u.log('VISUAL IMPORT COMPLETE')
