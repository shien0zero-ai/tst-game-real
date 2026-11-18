"""Copy missing base-demo content into the isolated lighting lab, without overwriting files.

The licensed sound bank remains local. This does not download or install anything.
"""
import pathlib, shutil

PROJECT = pathlib.Path(__file__).resolve().parents[1]
BASE = PROJECT.parent / 'AshgateForest' / 'Content'

def main():
    if not BASE.is_dir():
        raise RuntimeError('Restore the original AshgateForest assets first; see its README.')
    copied = 0
    for source in BASE.rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(BASE)
        if relative.parts[0] == 'Maps':
            continue
        target = PROJECT / 'Content' / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    # Check the folders rather than assuming import-generated shot asset names.
    for folder in ['Art/Meshes', 'Forest/Meshes', 'Forest/P38Field']:
        if not any((PROJECT / 'Content' / folder).glob('*.uasset')):
            raise RuntimeError('Missing base assets: ' + folder + '. Restore the original demo before building the lab.')
    print(f'Copied {copied} missing assets; existing lab files and the base project were preserved.')

if __name__ == '__main__':
    main()
