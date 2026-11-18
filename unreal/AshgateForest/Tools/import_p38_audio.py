import pathlib,unreal as u
P=pathlib.Path(u.Paths.project_dir());A=u.AssetToolsHelpers.get_asset_tools();E=u.EditorAssetLibrary
for f in sorted((P/'SourceArt/P38Field').glob('*.wav')):
 t=u.AssetImportTask();t.filename=str(f);t.destination_path='/Game/Forest/P38Field';t.destination_name=f.stem;t.automated=True;t.replace_existing=True;t.save=True;factory=u.SoundFactory();factory.set_editor_property('auto_create_cue',False);t.factory=factory;A.import_asset_tasks([t]);s=E.load_asset(t.destination_path+'/'+f.stem);assert isinstance(s,u.SoundWave);s.set_editor_property('looping',False);s.set_sound_asset_compression_type(u.SoundAssetCompressionType.PCM);E.save_loaded_asset(s,only_if_is_dirty=False);u.log('P38 PCM IMPORT '+f.stem)
assert len(list((P/'SourceArt/P38Field').glob('*.wav')))==6;u.log('P38 AUDIO IMPORT COMPLETE')
