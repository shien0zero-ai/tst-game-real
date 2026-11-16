"""Import forest meshes, explicit cutout foliage and 4K blended forest ground."""
import unreal as u,pathlib,json,struct
P=pathlib.Path(u.Paths.project_dir()).resolve();S=P/'SourceArt';E=u.EditorAssetLibrary;T=u.AssetToolsHelpers.get_asset_tools();M=u.MaterialEditingLibrary
manifest=json.loads((S/'asset-manifest.json').read_text());alphas=json.loads((S/'foliage-alpha.json').read_text());byname={n:x['id'] for x in manifest if 'variants' in x for _,n in x['variants']}
report={}
def expr(mat,cls):return M.create_material_expression(mat,cls)
def connect(a,out,b,inp):
 if not M.connect_material_expressions(a,out,b,inp):raise RuntimeError('Material link '+inp)
def texture(path,kind):
 stable='/Game/Forest/Textures/'+path.stem
 if not E.does_asset_exist(stable):
  task=u.AssetImportTask();task.filename=str(path);task.destination_path='/Game/Forest/Textures';task.automated=True;task.save=True;T.import_asset_tasks([task])
 tex=E.load_asset(stable)
 if kind=='normal':tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);tex.set_editor_property('flip_green_channel',True);tex.set_editor_property('srgb',False)
 elif kind in ('orm','alpha'):tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS);tex.set_editor_property('srgb',False)
 tex.set_editor_property('max_texture_size',4096 if 'Surfaces' in str(path) else 2048);E.save_loaded_asset(tex,only_if_is_dirty=False);return tex
materials={}
for file in sorted(list((S/'Models').glob('*.glb'))+list((S/'Models').glob('*.gltf'))):
 name=file.stem;stable='/Game/Forest/Meshes/'+name
 if not E.does_asset_exist(stable):
  pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL;pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.animation_pipeline.import_animations=False;pipe.material_pipeline.import_materials=False;pipe.material_pipeline.texture_pipeline.import_textures=False
  stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe);task=u.AssetImportTask();task.filename=str(file);task.destination_path='/Game/Forest/Imported/'+name;task.automated=True;task.save=True;task.options=stack
  T.import_asset_tasks([task]);meshes=[E.load_asset(p) for p in task.imported_object_paths if isinstance(E.load_asset(p),u.StaticMesh)]
  if len(meshes)!=1:raise RuntimeError('Expected combined mesh '+name)
  if not E.rename_asset(meshes[0].get_path_name(),stable):raise RuntimeError('Rename failed '+name)
 mesh=E.load_asset(stable);data=file.read_bytes();d=json.loads(data if file.suffix=='.gltf' else data[20:20+struct.unpack_from('<I',data,12)[0]])
 for mi,source in enumerate(d.get('materials',[])):
  mn=source['name'];path='/Game/Forest/Materials/'+mn
  if mn not in materials:
   mat=E.load_asset(path) if E.does_asset_exist(path) else T.create_asset(mn,'/Game/Forest/Materials',u.Material,u.MaterialFactoryNew());M.delete_all_material_expressions(mat)
   mat.set_editor_property('used_with_nanite',True);mat.set_editor_property('used_with_instanced_static_meshes',True);mat.set_editor_property('two_sided',True)
   leaf=source.get('alphaMode')=='MASK' or any(w in mn for w in ('twig','grass','fern'))
   if leaf:mat.set_editor_property('shading_model',u.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
   pbr=source.get('pbrMetallicRoughness',{});maps={}
   for kind,ref in (('color',pbr.get('baseColorTexture')),('normal',source.get('normalTexture')),('orm',pbr.get('metallicRoughnessTexture'))):
    if not ref:continue
    image=d['images'][d['textures'][ref['index']]['source']];maps[kind]=texture(S/'Models'/image['uri'],kind)
   ident=byname.get(name)
   if leaf and ident in alphas and source.get('alphaMode')=='MASK':maps['alpha']=texture(S/'Models'/alphas[ident]['uri'],'alpha')
   if 'alpha' in maps:mat.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED);mat.set_editor_property('opacity_mask_clip_value',.45)
   for kind,tex in maps.items():
    sample=expr(mat,u.MaterialExpressionTextureSample);sample.texture=tex
    if kind=='color':
     M.connect_material_property(sample,'RGB',u.MaterialProperty.MP_BASE_COLOR)
     if leaf:M.connect_material_property(sample,'RGB',u.MaterialProperty.MP_SUBSURFACE_COLOR)
    elif kind=='normal':sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL;M.connect_material_property(sample,'RGB',u.MaterialProperty.MP_NORMAL)
    elif kind=='orm':sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS;M.connect_material_property(sample,'G',u.MaterialProperty.MP_ROUGHNESS);M.connect_material_property(sample,'R',u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    else:sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS;M.connect_material_property(sample,'R',u.MaterialProperty.MP_OPACITY_MASK)
   M.recompile_material(mat);E.save_loaded_asset(mat,only_if_is_dirty=False);materials[mn]=mat
  for index,slot in enumerate(mesh.static_materials):
   if str(slot.material_slot_name)==mn:mesh.set_material(index,materials[mn])
 settings=mesh.get_editor_property('nanite_settings');settings.enabled=name!='forest_terrain';settings.keep_percent_triangles=1.0;settings.shape_preservation=u.NaniteShapePreservation.PRESERVE_AREA;u.get_editor_subsystem(u.StaticMeshEditorSubsystem).set_nanite_settings(mesh,settings,True)
 if name=='forest_terrain' or name.startswith('moss_rock') or name in ('fallen_log','stump'):
  body=mesh.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
 E.save_loaded_asset(mesh,only_if_is_dirty=False);bounds=mesh.get_bounds();report[name]={'origin':str(bounds.origin),'extent':str(bounds.box_extent),'slots':[str(x.material_slot_name) for x in mesh.static_materials]};u.log('FOREST IMPORT '+name+' '+str(report[name]))
# PBR terrain transition; the red vertex channel follows the authored meandering path.
path='/Game/Forest/Materials/ForestGround';mat=E.load_asset(path) if E.does_asset_exist(path) else T.create_asset('ForestGround','/Game/Forest/Materials',u.Material,u.MaterialFactoryNew());M.delete_all_material_expressions(mat)
pos=expr(mat,u.MaterialExpressionWorldPosition);mask=expr(mat,u.MaterialExpressionComponentMask)
for n,v in (('r',True),('g',True),('b',False),('a',False)):mask.set_editor_property(n,v)
connect(pos,'',mask,'');uv=expr(mat,u.MaterialExpressionMultiply);uv.set_editor_property('const_b',.005);connect(mask,'',uv,'A');vc=expr(mat,u.MaterialExpressionCustom);ci=u.CustomInput();ci.set_editor_property('input_name','P');vc.set_editor_property('inputs',[ci]);vc.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1);vc.set_editor_property('code','float2 p=P.xy*0.01; float y=sin(p.x*0.025)*12+sin(p.x*0.065)*3; return saturate((1.25-abs(p.y-y)+0.10*sin(p.x*4))/0.55);');connect(pos,'',vc,'P')
for kind in ('color','normal','orm'):
 nodes=[]
 for id in ('forest_ground_04','rocky_trail'):
  file=next((S/'Surfaces').glob(id+'_'+kind+'.*'));tex=texture(file,kind);sample=expr(mat,u.MaterialExpressionTextureSample);sample.texture=tex
  if kind=='normal':sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
  if kind=='orm':sample.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
  connect(uv,'',sample,'UVs');nodes.append(sample)
 lerp=expr(mat,u.MaterialExpressionLinearInterpolate);connect(nodes[0],'RGB',lerp,'A');connect(nodes[1],'RGB',lerp,'B');connect(vc,'',lerp,'Alpha')
 if kind=='color':
  tint=expr(mat,u.MaterialExpressionConstant3Vector);tint.constant=u.LinearColor(.36,.42,.34)
  multiply=expr(mat,u.MaterialExpressionMultiply);connect(lerp,'',multiply,'A');connect(tint,'',multiply,'B');M.connect_material_property(multiply,'',u.MaterialProperty.MP_BASE_COLOR)
 elif kind=='normal':norm=expr(mat,u.MaterialExpressionNormalize);connect(lerp,'',norm,'VectorInput');M.connect_material_property(norm,'',u.MaterialProperty.MP_NORMAL)
 else:
  for channel,prop in (('g',u.MaterialProperty.MP_ROUGHNESS),('r',u.MaterialProperty.MP_AMBIENT_OCCLUSION)):
   channelmask=expr(mat,u.MaterialExpressionComponentMask)
   for c in ('r','g','b','a'):channelmask.set_editor_property(c,c==channel)
   connect(lerp,'',channelmask,'');M.connect_material_property(channelmask,'',prop)
mat.set_editor_property('used_with_nanite',True);M.recompile_material(mat);E.save_loaded_asset(mat,only_if_is_dirty=False);ground=E.load_asset('/Game/Forest/Meshes/forest_terrain');ground.set_material(0,mat);E.save_loaded_asset(ground,only_if_is_dirty=False)
level='/Game/Maps/ForestTrail';sub=u.get_editor_subsystem(u.LevelEditorSubsystem)
if not E.does_asset_exist(level):
 sub.new_level(level);actors=u.get_editor_subsystem(u.EditorActorSubsystem);actors.spawn_actor_from_class(u.SkyAtmosphere,u.Vector(0,0,0));actors.spawn_actor_from_class(u.PlayerStart,u.Vector(-7500,-1100,600));sub.save_current_level()
E.save_directory('/Game/Forest',only_if_is_dirty=True,recursive=True);(P/'Saved/import-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');u.log('FOREST IMPORT COMPLETE')
