"""Reproduce the B asset geometry fixture in a fresh, isolated Godot project."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone
from mesh_review import review

def sha(blob): return hashlib.sha256(blob).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--godot', required=True)
    p.add_argument('--output-root', required=True)
    p.add_argument('--render', action='store_true', help='Also render eleven inspection PNGs using an actual GPU window.')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    base = here.parents[2]
    out = Path(args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=False)
    project = out/'project'
    project.mkdir()
    executable = Path(args.godot).resolve()
    executable_hash = sha(executable.read_bytes())
    assert executable_hash == 'ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424', 'Use the reviewed official Windows Godot 4.7.2 executable.'
    sources = json.loads((here/'source-manifest.json').read_bytes())
    for item in sources:
        blob = (base/'simulator'/item['path']).read_bytes()
        assert sha(blob) == item['sha256'], item['path']
        target = project/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    shutil.copyfile(here/'export_asset_meshes.gd', project/'export_asset_meshes.gd')
    shutil.copyfile(here/'render/project.godot', project/'project.godot')
    (project/'render').mkdir()
    shutil.copyfile(here/'render/render_capture.gd', project/'render/render_capture.gd')
    commands = []
    steps = [('import',['--headless','--editor','--import','--quit']),
             ('baseline',['--headless','--script','res://tests/test_asset_contract.gd']),
             ('export',['--headless','--script','res://export_asset_meshes.gd'])]
    if args.render:
        steps.append(('render',['--rendering-method','gl_compatibility','--rendering-driver','opengl3',
                                '--position','-3200,120','--resolution','1280x720','--script','res://render/render_capture.gd']))
    for name, flags in steps:
        argv = [str(executable),'--path',str(project),*flags]
        result = subprocess.run(argv, cwd=project, capture_output=True, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        (out/f'{name}.stdout.txt').write_bytes(result.stdout)
        (out/f'{name}.stderr.txt').write_bytes(result.stderr)
        commands.append({'name':name,'argv':argv,'exit_code':result.returncode,
                         'stdout_sha256':sha(result.stdout),'stderr_sha256':sha(result.stderr)})
        (out/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
        assert result.returncode == 0, (name,result.returncode)
    geometry = review(json.loads((project/'exported_meshes.json').read_bytes()))
    unchanged = all(sha((base/'simulator'/s['path']).read_bytes()) == s['sha256'] for s in sources)
    record = {'at_utc':datetime.now(timezone.utc).isoformat(),'engine_sha256':executable_hash,
              'sources':sources,'commands':commands,'geometry':geometry,'source_unchanged':unchanged,
              'render_requested':args.render,'G01':'not_run','board':'not_run','system':'not_run'}
    (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'status':geometry['status'],'asset_count':geometry['asset_count'],
                      'mesh_count':geometry['mesh_count'],'source_unchanged':unchanged,'render':args.render}))
    assert not geometry['findings'] and unchanged

if __name__ == '__main__': main()
