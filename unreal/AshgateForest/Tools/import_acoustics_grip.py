import pathlib,json,unreal as u
P=pathlib.Path(u.Paths.project_dir());A=u.AssetToolsHelpers.get_asset_tools();E=u.EditorAssetLibrary
for f in ([] if globals().get('HANDS_ONLY',False) else sorted((P/'SourceArt/Acoustics').glob('*.wav'))):
 t=u.AssetImportTask();t.filename=str(f);t.destination_path='/Game/Forest/Acoustics';t.destination_name=f.stem;t.replace_existing=True;t.automated=True;t.save=True
 fac=u.SoundFactory();fac.set_editor_property('auto_create_cue',False);t.factory=fac;A.import_asset_tasks([t]);s=E.load_asset(t.destination_path+'/'+f.stem);assert isinstance(s,u.SoundWave)
 s.set_editor_property('looping',False);s.set_sound_asset_compression_type(u.SoundAssetCompressionType.PCM);E.save_loaded_asset(s,only_if_is_dirty=False);u.log('ACOUSTIC IMPORT '+f.stem)
for name in ['gripfit_right','gripfit_left']:
 t=u.AssetImportTask();t.filename=str(P/'SourceArt/GripFit'/(name+'.glb'));t.destination_path='/Game/Forest/GripFit/Meshes';t.automated=True;t.replace_existing=True;t.save=True
 pipe=u.InterchangeGenericAssetsPipeline();pipe.mesh_pipeline.combine_static_meshes_behavior=u.InterchangeCombineStaticMeshesBehavior.ALL;pipe.common_meshes_properties.force_all_mesh_as_type=u.InterchangeForceMeshType.IFMT_STATIC_MESH;pipe.animation_pipeline.import_animations=False;pipe.material_pipeline.import_materials=False;pipe.material_pipeline.texture_pipeline.import_textures=False
 stack=u.InterchangePipelineStackOverride();stack.add_pipeline(pipe);t.options=stack;A.import_asset_tasks([t]);m=E.load_asset(t.destination_path+'/'+name);assert m
 for k,slot in enumerate(m.static_materials):
  mat='/Game/Forest/FieldFinish/Materials/FieldGlove' if str(slot.material_slot_name)=='AnatomicalLeather' else '/Game/Forest/Viewmodel/Materials/WovenSleeve';m.set_material(k,E.load_asset(mat))
 sub=u.get_editor_subsystem(u.StaticMeshEditorSubsystem);settings=m.get_editor_property('nanite_settings');settings.enabled=False;sub.set_nanite_settings(m,settings,True);sub.set_generate_lightmap_uv(m,False);E.save_loaded_asset(m,only_if_is_dirty=False);u.log('GRIP FIT IMPORT '+name)
u.log('ACOUSTICS GRIP IMPORT COMPLETE')
