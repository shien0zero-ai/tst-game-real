import pathlib,json,unreal as u
P=pathlib.Path(u.Paths.project_dir());S=P/'SourceArt/Integration';E=u.EditorAssetLibrary;A=u.AssetToolsHelpers.get_asset_tools();M=u.MaterialEditingLibrary;B='/Game/Forest/Integration';sub=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
def expr(mat,cls):return M.create_material_expression(mat,cls)
def wire(a,o,b,i):
 if not M.connect_material_expressions(a,o,b,i):raise RuntimeError('Material connection '+o+' -> '+i)
def link(a,o,prop):
 if not M.connect_material_property(a,o,prop):raise RuntimeError('Material property '+str(prop))
def custom_input(name):
 n=u.CustomInput();n.set_editor_property('input_name',name);return n
def custom_output(name,ty):
 n=u.CustomOutput();n.set_editor_property('output_name',name);n.set_editor_property('output_type',ty);return n
def constant(mat,v):
 if isinstance(v,(int,float)):n=expr(mat,u.MaterialExpressionConstant);n.r=v
 else:n=expr(mat,u.MaterialExpressionConstant3Vector);n.constant=u.LinearColor(*v)
 return n
def save_material(mat):
 errors=list(M.recompile_material(mat))
 if errors:raise RuntimeError('Final material compile failed '+mat.get_name()+': '+str(errors))
 E.save_loaded_asset(mat,only_if_is_dirty=False)
 u.log('FIELD MATERIAL COMPILE PASS '+mat.get_name())
def material(name):
 path=B+'/Materials/'+name;mat=E.load_asset(path) if E.does_asset_exist(path) else A.create_asset(name,B+'/Materials',u.Material,u.MaterialFactoryNew())
 for prop in [u.MaterialProperty.MP_BASE_COLOR,u.MaterialProperty.MP_NORMAL,u.MaterialProperty.MP_ROUGHNESS,u.MaterialProperty.MP_METALLIC,u.MaterialProperty.MP_AMBIENT_OCCLUSION]:M.disconnect_material_property(mat,prop)
 M.delete_all_material_expressions(mat);return mat
def coord(mat,index=0,tile=1):
 n=expr(mat,u.MaterialExpressionTextureCoordinate);n.coordinate_index=index;n.u_tiling=tile;n.v_tiling=tile;return n
def sample(mat,name,kind='color',uv=None):
 tex=E.load_asset('/Game/Forest/Viewmodel/Textures/'+name)
 if not tex:raise RuntimeError('Missing existing texture '+name)
 n=expr(mat,u.MaterialExpressionTextureSample);n.texture=tex
 if kind=='normal':n.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
 if kind=='masks':n.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
 if uv:wire(uv,'',n,'UVs')
 return n
def mask(mat,n,c):
 out=expr(mat,u.MaterialExpressionComponentMask)
 for ch in 'rgba':out.set_editor_property(ch,ch==c)
 wire(n,'',out,'');return out
code=(S/'integration_surface.ush').read_text(encoding='utf-8');mats={};report={'materials':{},'meshes':{}}
for kind,name in enumerate(['FieldSteel','FieldPolymer','FieldRubber','FieldBore','FieldControls','FieldCrown']):
 mat=material(name);custom=expr(mat,u.MaterialExpressionCustom);custom.set_editor_property('code',code);custom.set_editor_property('description','Field service finish; physically scaled convex-edge wear');ty=u.CustomMaterialOutputType.CMOT_FLOAT3;custom.set_editor_property('output_type',ty)
 inputs=['UV','Bary','Altitudes','ThirdAltitude','Edges','BaseColor','BaseNormal','Maps','Kind'];custom.set_editor_property('inputs',[custom_input(n) for n in inputs]);custom.set_editor_property('additional_outputs',[custom_output('Color',ty),custom_output('Normal',ty)])
 for index,key in enumerate(['UV','Bary','Altitudes','ThirdAltitude']):wire(coord(mat,index),'',custom,key)
 vertex=expr(mat,u.MaterialExpressionVertexColor);wire(vertex,'',custom,'Edges');wire(sample(mat,'service_pistol_diff_4k'),'RGB',custom,'BaseColor');wire(sample(mat,'service_pistol_nor_gl_4k','normal'),'RGB',custom,'BaseNormal');wire(sample(mat,'service_pistol_arm_4k','masks'),'RGB',custom,'Maps');wire(constant(mat,kind),'',custom,'Kind')
 link(custom,'Color',u.MaterialProperty.MP_BASE_COLOR);link(custom,'Normal',u.MaterialProperty.MP_NORMAL)
 for channel,prop in [('r',u.MaterialProperty.MP_ROUGHNESS),('g',u.MaterialProperty.MP_METALLIC),('b',u.MaterialProperty.MP_AMBIENT_OCCLUSION)]:link(mask(mat,custom,channel),'',prop)
 save_material(mat);mats[name]=mat;report['materials'][name]={'kind':kind,'source_maps':'unaltered original 4K diffuse / normal / ARM','wear_width_mm':[.10,.25]}
# Fine leather normal, subdued reflectance; sleeve stays the existing woven material.
mat=material('FieldGlove');uv=coord(mat,0,7);base=sample(mat,'leather_color',uv=uv);desat=expr(mat,u.MaterialExpressionDesaturation);wire(base,'RGB',desat,'');wire(constant(mat,1),'',desat,'Fraction');tint=expr(mat,u.MaterialExpressionMultiply);wire(desat,'',tint,'A');wire(constant(mat,(.18,.20,.18)),'',tint,'B');link(tint,'',u.MaterialProperty.MP_BASE_COLOR)
norm=sample(mat,'leather_normal','normal',uv);blend=expr(mat,u.MaterialExpressionLinearInterpolate);wire(constant(mat,(0,0,1)),'',blend,'A');wire(norm,'RGB',blend,'B');wire(constant(mat,.55),'',blend,'Alpha');normalize=expr(mat,u.MaterialExpressionNormalize);wire(blend,'',normalize,'');link(normalize,'',u.MaterialProperty.MP_NORMAL)
rough=sample(mat,'leather_rough','masks',uv);mul=expr(mat,u.MaterialExpressionMultiply);wire(rough,'R',mul,'A');wire(constant(mat,.20),'',mul,'B');plus=expr(mat,u.MaterialExpressionAdd);wire(mul,'',plus,'A');wire(constant(mat,.58),'',plus,'B');link(plus,'',u.MaterialProperty.MP_ROUGHNESS);link(constant(mat,0),'',u.MaterialProperty.MP_METALLIC);save_material(mat)
for name in ['field_frame','field_slide','field_magazine']:
 pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL;pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.common_meshes_properties.recompute_normals=False;pipe.common_meshes_properties.recompute_tangents=True;pipe.animation_pipeline.import_animations=False;pipe.material_pipeline.import_materials=False;pipe.material_pipeline.texture_pipeline.import_textures=False;stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe)
 task=u.AssetImportTask();task.filename=str(S/(name+'.glb'));task.destination_path=B+'/Meshes';task.automated=True;task.replace_existing=True;task.save=True;task.options=stack;A.import_asset_tasks([task]);mesh=E.load_asset(B+'/Meshes/'+name)
 if not mesh:raise RuntimeError('Field mesh missing '+name)
 for i,slot in enumerate(mesh.static_materials):
  selected=mats.get(str(slot.material_slot_name))
  if not selected:raise RuntimeError('Unmapped field material '+str(slot.material_slot_name))
  mesh.set_material(i,selected)
 build=sub.get_lod_build_settings(mesh,0);build.recompute_normals=False;build.recompute_tangents=True;build.use_high_precision_tangent_basis=True;build.use_full_precision_u_vs=True;sub.set_lod_build_settings(mesh,0,build);sub.set_generate_lightmap_uv(mesh,False);settings=mesh.get_editor_property('nanite_settings');settings.enabled=False;sub.set_nanite_settings(mesh,settings,True);E.save_loaded_asset(mesh,only_if_is_dirty=False)
 channels=sub.get_num_uv_channels(mesh,0);colors=sub.has_vertex_colors(mesh)
 if channels<4 or not colors:raise RuntimeError('Missing physical wear coordinates / edge flags: '+name)
 report['meshes'][name]={'uv_channels':channels,'vertex_colors':colors,'bounds':str(mesh.get_bounds()),'materials':[str(x.material_slot_name) for x in mesh.static_materials]}
(P/'Saved/integration-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8');u.log('INTEGRATION IMPORT COMPLETE')
