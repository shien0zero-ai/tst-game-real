import pathlib,unreal as u
p=pathlib.Path(u.Paths.project_dir())/'Tools/import_grip.py'
exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})
