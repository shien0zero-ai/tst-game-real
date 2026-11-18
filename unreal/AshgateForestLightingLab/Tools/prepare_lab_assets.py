import pathlib,json,unreal as u
P=pathlib.Path(u.Paths.project_dir());E=u.EditorAssetLibrary;A=u.AssetToolsHelpers.get_asset_tools();sub=u.get_editor_subsystem(u.StaticMeshEditorSubsystem);report={}
for path in E.list_assets('/Game/Forest/Meshes',recursive=False):
 m=E.load_asset(path)
 if not isinstance(m,u.StaticMesh):continue
 channels=sub.get_num_uv_channels(m,0);report[m.get_name()]={'uv_channels':channels,'lightmap_coordinate_before':m.get_editor_property('light_map_coordinate_index')}
 if m.get_editor_property('light_map_coordinate_index')>=channels:m.set_editor_property('light_map_coordinate_index',0);E.save_loaded_asset(m,only_if_is_dirty=False)
pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL;pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.animation_pipeline.import_animations=False;pipe.material_pipeline.import_materials=False;pipe.material_pipeline.texture_pipeline.import_textures=False;stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe)
t=u.AssetImportTask();t.filename=str(P/'SourceArt/Models/lab_terrain.glb');t.destination_path='/Game/LightingLab';t.destination_name='lab_terrain';t.automated=True;t.replace_existing=True;t.save=True;t.options=stack;A.import_asset_tasks([t]);m=E.load_asset('/Game/LightingLab/lab_terrain');assert m
m.set_material(0,E.load_asset('/Game/Forest/Materials/ForestGround'));m.set_editor_property('light_map_coordinate_index',1);m.set_editor_property('light_map_resolution',1024);sub.set_generate_lightmap_uv(m,False);body=m.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE);E.save_loaded_asset(m,only_if_is_dirty=False);assert sub.get_num_uv_channels(m,0)>=2
(P/'Saved/lab-mesh-audit.json').write_text(json.dumps(report,indent=2));u.log('LAB ASSETS READY')
