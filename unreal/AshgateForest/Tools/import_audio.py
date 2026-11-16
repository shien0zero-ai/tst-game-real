"""Import only the forest's new sounds; leave original game audio intact."""
import pathlib,json,unreal as u
p=pathlib.Path(u.Paths.project_dir());assets=u.AssetToolsHelpers.get_asset_tools();report={}
for source in sorted((p/'SourceArt/Audio').glob('*.wav')):
    if globals().get('ONLY_PISTOL',False) and not source.stem.startswith('pistol_fire_'):continue
    task=u.AssetImportTask();task.filename=str(source);task.destination_path='/Game/Forest/Audio';task.destination_name=source.stem;task.replace_existing=True;task.automated=True;task.save=True
    factory=u.SoundFactory();factory.set_editor_property('auto_create_cue',False);task.factory=factory;assets.import_asset_tasks([task])
    sound=u.EditorAssetLibrary.load_asset('/Game/Forest/Audio/'+source.stem)
    if not isinstance(sound,u.SoundWave):raise RuntimeError('Missing imported sound '+source.stem)
    sound.set_editor_property('looping',source.stem in ('forest_birds','forest_wind'))
    u.EditorAssetLibrary.save_loaded_asset(sound,only_if_is_dirty=False)
    report[source.stem]={'duration':sound.duration,'looping':sound.get_editor_property('looping')};u.log('FOREST AUDIO IMPORT '+source.stem)
(p/'Saved/audio-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8');u.log('FOREST AUDIO IMPORT COMPLETE')
