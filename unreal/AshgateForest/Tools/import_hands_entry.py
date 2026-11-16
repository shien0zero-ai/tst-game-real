import pathlib,unreal as u
p=pathlib.Path(u.Paths.project_dir())/'Tools/import_acoustics_grip.py';exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),{'__file__':str(p),'HANDS_ONLY':True})
