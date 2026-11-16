import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_dir())/'Tools/import_audio.py'
exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),{'__file__':str(p),'__name__':'__main__','ONLY_PISTOL':True})
