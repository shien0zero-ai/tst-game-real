import pathlib,unreal as u
script=pathlib.Path(u.Paths.project_dir())/'Tools/import_forest.py'
exec(compile(script.read_text(encoding='utf-8-sig'),str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
