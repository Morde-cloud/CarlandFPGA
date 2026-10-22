"""Create a reviewed scope handoff selection with lossless raw-evidence bundles."""
import gzip,hashlib,io,json,tarfile
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');E=W/'competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22';M=E/'main'
sha=lambda b:hashlib.sha256(b).hexdigest()
def put(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
assert json.loads((M/'ACCEPTANCE.json').read_bytes())['decision']=='ACCEPT_BOUNDED_TOOLCHECK_REPAIR_PENDING_COORDINATOR'
bundles=M/'bundles';bundles.mkdir(exist_ok=False);archived=set();bundle_records=[]
directories=[E/'author',M/'coordinator-red',M/'original-direct-01',M/'original-entry-01',M/'final-direct-01',M/'final-entry-01']
for directory in directories:
    name='author' if directory==E/'author' else directory.name
    paths=sorted(p for p in directory.rglob('*') if p.is_file())
    index={p.relative_to(E).as_posix(): {'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in paths}
    archive=bundles/(name+'.tar.gz')
    with archive.open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as gz:
            with tarfile.open(fileobj=gz,mode='w') as tf:
                for p in paths:
                    b=p.read_bytes();info=tarfile.TarInfo(str(p.relative_to(E)).replace('\\','/'));info.size=len(b);info.mode=0o644;info.mtime=0;tf.addfile(info,io.BytesIO(b))
    readback={}
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf:
            assert member.isfile() and member.name not in readback and not member.name.startswith('/') and '..' not in Path(member.name).parts
            b=tf.extractfile(member).read();readback[member.name]={'bytes':len(b),'sha256':sha(b)}
    assert readback==index
    indexpath=bundles/(name+'.index.json');put(indexpath,{'scope':'All raw bytes in this owned directory, losslessly archived; no member omission','archive_sha256':sha(archive.read_bytes()),'files':index})
    bundle_records.append({'archive':str(archive.relative_to(W)),'sha256':sha(archive.read_bytes()),'index':str(indexpath.relative_to(W)),'index_sha256':sha(indexpath.read_bytes()),'raw_file_count':len(paths),'raw_bytes':sum(x['bytes'] for x in index.values())})
    archived.update(str(p.relative_to(W)) for p in paths)
put(M/'BUNDLE_MANIFEST.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Raw directories retained locally and represented exactly by gzip/tar members in publication; all member hashes read back without extraction','bundles':bundle_records})
(M/'.gitattributes').write_bytes(b'* -text\n')
selected=[]
sources=['competition/deepeye/tools/acquisition/run_sample_scan_capture.py','competition/deepeye/tests/acquisition/test_sample_scan_toolcheck.py']
for p in [W/s for s in sources]+[p for p in M.rglob('*') if p.is_file() and str(p.relative_to(W)) not in archived]:
    selected.append({'path':p.relative_to(W).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
assert len({f['path'] for f in selected})==len(selected)
put(O/'SELECTED.json',{'root':str(W),'baseline':'cd007dc8190b7c2d911d2be6c1136aabab3518e5','files':sorted(selected,key=lambda x:x['path']),'raw_files_in_bundles':len(archived),'bundles':bundle_records})
print(json.dumps({'selected':len(selected),'bytes':sum(x['bytes'] for x in selected),'raw_files_in_bundles':len(archived),'bundles':len(bundle_records)}))
