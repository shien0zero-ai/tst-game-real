import pathlib,unreal as u,json
P=pathlib.Path(u.Paths.project_dir()).resolve();E=u.EditorAssetLibrary;A=u.AssetToolsHelpers.get_asset_tools();report={}
for side in ('right','left'):
 name='grip_'+side;source=P/'SourceArt/Grip'/(name+'.glb');stable='/Game/Art/Meshes/'+name
 pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL;pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.animation_pipeline.import_animations=False;pipe.material_pipeline.import_materials=False;pipe.material_pipeline.texture_pipeline.import_textures=False
 stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe)
 task=u.AssetImportTask();task.filename=str(source);task.destination_path='/Game/Art/Meshes';task.destination_name=name;task.replace_existing=True;task.automated=True;task.save=True;task.options=stack;A.import_asset_tasks([task]);mesh=E.load_asset(stable)
 if not mesh:raise RuntimeError('Grip mesh missing '+stable)
 original=E.load_asset('/Game/Art/Meshes/view_'+side);mapping={str(s.material_slot_name):s.material_interface for s in original.static_materials}
 for i,s in enumerate(mesh.static_materials):
  mat=mapping.get(str(s.material_slot_name))
  if not mat:raise RuntimeError('Missing original material '+str(s.material_slot_name))
  mesh.set_material(i,mat)
 settings=mesh.get_editor_property('nanite_settings');settings.enabled=False;u.get_editor_subsystem(u.StaticMeshEditorSubsystem).set_nanite_settings(mesh,settings,True);E.save_loaded_asset(mesh,only_if_is_dirty=False)
 report[name]={'materials':list(mapping),'bounds':str(mesh.get_bounds())};u.log('GRIP IMPORT '+name)
(P/'Saved/grip-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8');u.log('GRIP IMPORT COMPLETE')
