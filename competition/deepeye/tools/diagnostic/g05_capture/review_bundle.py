"""Verify the exact content-addressed-raw-evidence-v1 bundle; stdlib only.

python review_bundle.py --bundle DIR --expected-manifest-sha256 TRUSTED_SHA
Add --restore NEW_DIR [--prefix LABEL/] to restore independent ordinary copies.
No destination is created until the entire archive and index have verified.
Restore rereads/rechecks the parts; failures leave a visibly incomplete NEW_DIR,
never overwrite/retry. Keep inputs and destination parents under exclusive local
control: portable lstat/open checks do not defeat a hostile concurrent filesystem
writer. No extraction APIs, external commands, network, or hardware are used.

Finite limits: 64MiB per JSON, 100000 logical files/unique blobs, 4096 parts
(4GiB compressed), 8GiB per file, 64GiB unique and 256GiB logical bytes.
Streaming buffers are 1MiB. These limits accommodate 15000 files and >1GiB
logical evidence; they are resource ceilings, not a claim about a real bundle.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import unicodedata

FORMAT='content-addressed-raw-evidence-v1'
CHUNK=1024*1024
MAX_JSON=64*CHUNK
MAX_FILES=100000
MAX_PARTS=4096
MAX_FILE=8*1024**3
MAX_UNIQUE=64*1024**3
MAX_LOGICAL=256*1024**3
EXCLUSION='private lease files and Python __pycache__ only; logical file bytes are preserved through the hash map'
RESERVED={'CON','PRN','AUX','NUL','CONIN$','CONOUT$'}|{p+n for p in ('COM','LPT') for n in '123456789¹²³'}


class Rejected(ValueError):
    pass


def need(ok,message):
    if not ok:raise Rejected(message)


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'invalid SHA256')
    return value


def number(value,maximum,minimum=0):
    need(type(value) is int and minimum<=value<=maximum,'invalid byte/count bound')
    return value


def exact(obj,keys):
    need(type(obj) is dict and set(obj)==set(keys),'unexpected metadata schema')


def logical(name):
    need(type(name) is str and 0<len(name.encode('utf-8'))<=4096,'invalid logical path length')
    parts=name.split('/')
    need(len(parts)<=64,'logical path depth bound')
    for part in parts:
        need(part not in ('','.','..') and len(part.encode('utf-8'))<=255,'invalid logical path component')
        need(not any(c in '<>:"\\|?*' or unicodedata.category(c).startswith('C') for c in part),'unsafe logical path character')
        need(not part.endswith(('.', ' ')),'trailing dot/space forbidden')
        need(part.split('.')[0].rstrip(' .').upper() not in RESERVED,'reserved Windows name')
    return parts


def path_catalog(names):
    seen={}
    for name in names:
        parts=logical(name)
        for i in range(1,len(parts)+1):
            spelling='/'.join(parts[:i]);key=spelling.casefold();kind='file' if i==len(parts) else 'directory'
            prior=seen.get(key)
            need(prior is None or prior==(spelling,'directory') and kind=='directory',
                 'duplicate/case alias or file-directory collision: '+spelling)
            seen[key]=(spelling,kind)


def checked_path(value):
    path=Path(value)
    need('..' not in path.parts,'host path traversal forbidden')
    path=Path(os.path.abspath(path))
    for item in reversed((path,*path.parents)):
        try:s=item.lstat()
        except FileNotFoundError:continue
        need(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400,'symlink/reparse path forbidden')
        need(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode),'nonordinary filesystem input')
        if stat.S_ISREG(s.st_mode):need(s.st_nlink==1,'hardlinked file forbidden')
        if item!=path:need(stat.S_ISDIR(s.st_mode),'nondirectory parent')
    return path


def fingerprint(s):
    # Windows 3.12 lstat/fstat can disagree on ctime (creation vs change time).
    # Device/inode, size, mtime and link count agree; retain ctime on POSIX.
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)+( () if os.name=='nt' else (s.st_ctime_ns,) )


def open_input(path,limit,expected_size=None):
    path=checked_path(path);before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'ordinary single-link input required')
    number(before.st_size,limit)
    if expected_size is not None:need(before.st_size==expected_size,'input size differs: '+path.name)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    stream=os.fdopen(fd,'rb')
    try:need(fingerprint(os.fstat(stream.fileno()))==fingerprint(before),'input replaced during open')
    except BaseException:stream.close();raise
    return stream,before


def unchanged(stream,path,before):
    checked_path(path)
    need(fingerprint(os.fstat(stream.fileno()))==fingerprint(before)==fingerprint(path.lstat()),'input changed while reading')


def metadata(path,expected):
    f,s=open_input(path,MAX_JSON)
    with f:
        chunks=[];remaining=s.st_size
        while remaining:
            chunk=f.read(min(CHUNK,remaining));need(chunk,'truncated metadata');chunks.append(chunk);remaining-=len(chunk)
        need(not f.read(1),'metadata grew');unchanged(f,path,s)
    raw=b''.join(chunks);need(hashlib.sha256(raw).hexdigest()==digest(expected),'metadata hash mismatch: '+path.name)
    def pairs(items):
        obj={}
        for key,value in items:
            need(key not in obj,'duplicate JSON key');obj[key]=value
        return obj
    def forbidden(value):raise Rejected('noninteger JSON number')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=forbidden,parse_constant=forbidden)


class Parts:
    """Concatenate ordered parts while verifying every byte and source identity."""
    def __init__(self,root,manifest,prior=None):
        self.root=root;self.manifest=manifest;self.prior=prior;self.signatures={}
        self.index=0;self.stream=None;self.total=0;self.combined=hashlib.sha256()

    def read(self,size=-1):
        need(type(size) is int and size>=0,'unbounded archive read forbidden')
        if not size:return b''
        if self.stream is None:
            if self.index==len(self.manifest['parts']):return b''
            self.entry=self.manifest['parts'][self.index];self.path=self.root/self.entry['path']
            self.stream,self.before=open_input(self.path,CHUNK,self.entry['bytes'])
            signature=fingerprint(self.before)
            if self.prior is not None:need(self.prior[self.entry['path']]==signature,'part changed since full verification')
            self.signatures[self.entry['path']]=signature;self.remaining=self.entry['bytes'];self.hasher=hashlib.sha256()
        chunk=self.stream.read(min(size,CHUNK,self.remaining));need(chunk,'truncated archive part')
        self.hasher.update(chunk);self.combined.update(chunk);self.remaining-=len(chunk);self.total+=len(chunk)
        if not self.remaining:
            need(not self.stream.read(1),'archive part grew');unchanged(self.stream,self.path,self.before)
            need(self.hasher.hexdigest()==self.entry['sha256'],'archive part hash mismatch')
            self.stream.close();self.stream=None;self.index+=1
        return chunk

    def finish(self):
        need(self.index==len(self.manifest['parts']) and self.stream is None,'archive not fully consumed')
        need(self.total==self.manifest['archive_bytes'] and self.combined.hexdigest()==self.manifest['archive_sha256'],'combined archive hash/size mismatch')

    def close(self):
        if self.stream is not None:self.stream.close();self.stream=None


def read_exact(stream,size):
    chunks=[]
    while size:
        chunk=stream.read(min(size,CHUNK));need(chunk,'truncated tar data');chunks.append(chunk);size-=len(chunk)
    return b''.join(chunks)


def new_file(root,name):
    path=root.joinpath(*logical(name))
    for parent in reversed(path.parents):
        if parent==root or root in parent.parents:
            checked_path(parent)
            try:parent.mkdir(mode=0o700)
            except FileExistsError:need(parent.is_dir(),'restore parent is not directory')
            checked_path(parent)
    checked_path(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0),0o600)
    return path,os.fdopen(fd,'wb')


def ordinary_copy(source,root,name,expected,size):
    inp,before=open_input(source,MAX_FILE,size)
    with inp:
        path,out=new_file(root,name);hasher=hashlib.sha256();left=size
        with out:
            while left:
                chunk=inp.read(min(left,CHUNK));need(chunk,'restored source truncated')
                out.write(chunk);hasher.update(chunk);left-=len(chunk)
            need(not inp.read(1),'restored source grew');unchanged(inp,source,before)
            need(hasher.hexdigest()==expected,'restored source hash changed')
            out.flush();os.fsync(out.fileno())
        checked_path(path)


def scan(root,manifest,blobs,targets=None,destination=None,prior=None):
    parts=Parts(root,manifest,prior);seen=set()
    try:
        with gzip.GzipFile(fileobj=parts,mode='rb') as gz:
            while True:
                block=read_exact(gz,512)
                if block==bytes(512):
                    need(read_exact(gz,512)==bytes(512),'tar end marker missing')
                    # Exact writer pads only to a 10240-byte record; never expand a tail bomb.
                    tail=0
                    while chunk:=gz.read(512):
                        tail+=len(chunk);need(tail<=10240 and not any(chunk),'invalid/excessive tar trailing data')
                    break
                member=tarfile.TarInfo.frombuf(block,'utf-8','strict')
                need(member.type==tarfile.REGTYPE and re.fullmatch(r'blobs/[0-9a-f]{64}',member.name),'nonregular/unexpected tar member')
                key=member.name[6:]
                need(key in blobs and key not in seen,'unknown/duplicate tar blob')
                need(member.size==blobs[key],'tar member size mismatch');seen.add(key)
                names=targets.get(key,()) if targets is not None else ()
                out=None;first=None;hasher=hashlib.sha256();remaining=member.size
                try:
                    if names:first,out=new_file(destination,names[0])
                    while remaining:
                        chunk=read_exact(gz,min(remaining,CHUNK));remaining-=len(chunk);hasher.update(chunk)
                        if out is not None:out.write(chunk)
                    need(hasher.hexdigest()==key,'tar member hash mismatch')
                    if out is not None:out.flush();os.fsync(out.fileno())
                finally:
                    if out is not None:out.close()
                padding=read_exact(gz,(-member.size)%512)
                need(not any(padding),'nonzero tar member padding')
                for name in names[1:]:ordinary_copy(first,destination,name,key,member.size)
        need(seen==set(blobs),'tar exact blob set mismatch');parts.finish()
        return parts.signatures
    finally:parts.close()


def review(bundle,expected_manifest_sha256,restore=None,prefix=None):
    root=checked_path(bundle);need(root.is_dir(),'bundle directory required')
    manifest=metadata(root/'BUNDLE_MANIFEST.json',expected_manifest_sha256)
    exact(manifest,('format','archive_sha256','archive_bytes','parts','raw_index_sha256','logical_files','unique_blobs',
                    'verified_all_unique_members','original_sources_postchecked','no_extraction_performed'))
    need(manifest['format']==FORMAT,'unknown bundle format')
    for key in ('verified_all_unique_members','original_sources_postchecked','no_extraction_performed'):
        need(manifest[key] is True,'unexpected producer metadata flag')
    digest(manifest['archive_sha256']);number(manifest['archive_bytes'],MAX_PARTS*CHUNK,1)
    need(type(manifest['parts']) is list and 1<=len(manifest['parts'])<=MAX_PARTS,'part count bound')
    for i,part in enumerate(manifest['parts']):
        exact(part,('path','sha256','bytes'));digest(part['sha256']);number(part['bytes'],CHUNK,1)
        need(part['path']==f'raw-evidence.blobs.tar.gz.part{i:03d}','unexpected part name/order')
        need(i==len(manifest['parts'])-1 or part['bytes']==CHUNK,'nonfinal part size mismatch')
    need(sum(p['bytes'] for p in manifest['parts'])==manifest['archive_bytes'],'part byte sum mismatch')
    index=metadata(root/'RAW_INDEX.json',manifest['raw_index_sha256'])
    exact(index,('format','files','excluded_paths','exclusion_scope','logical_files','unique_blobs'))
    need(index['format']==FORMAT and index['exclusion_scope']==EXCLUSION,'unknown raw index format')
    files=index['files'];need(type(files) is dict and len(files)<=MAX_FILES,'logical file count bound')
    path_catalog(files)
    need(type(index['excluded_paths']) is list and len(index['excluded_paths'])<=MAX_FILES,'excluded path bound')
    path_catalog(index['excluded_paths'])
    blobs={};logical_bytes=0
    for name,entry in files.items():
        exact(entry,('sha256','bytes'));key=digest(entry['sha256']);size=number(entry['bytes'],MAX_FILE)
        need(key not in blobs or blobs[key]==size,'inconsistent duplicate blob size')
        blobs[key]=size;logical_bytes+=size
    need(sum(blobs.values())<=MAX_UNIQUE and logical_bytes<=MAX_LOGICAL,'total data bound')
    for doc in (manifest,index):
        need(number(doc['logical_files'],MAX_FILES)==len(files) and number(doc['unique_blobs'],MAX_FILES)==len(blobs),'index count mismatch')
    need(prefix is None or restore is not None,'prefix requires restore')
    if prefix is not None:
        need(type(prefix) is str and prefix.endswith('/') and len(logical(prefix[:-1]))==1,'prefix must be one LABEL/')
        need(any(n.startswith(prefix) for n in files),'prefix matches no logical files')
    selected={n[len(prefix):] if prefix else n:entry for n,entry in files.items() if prefix is None or n.startswith(prefix)}
    path_catalog(selected)
    destination=None
    if restore is not None:
        destination=checked_path(restore)
        need(not os.path.lexists(destination),'restore destination already exists')
        need(destination.parent.is_dir(),'restore parent must already exist')
        need(destination!=root and root not in destination.parents and destination not in root.parents,'restore/bundle overlap')
    signatures=scan(root,manifest,blobs)
    # No output or temporary file has been created before this point.
    if destination is not None:
        checked_path(destination);destination.mkdir(mode=0o700,exist_ok=False)
        targets={}
        for name,entry in selected.items():targets.setdefault(entry['sha256'],[]).append(name)
        scan(root,manifest,blobs,targets,destination,signatures)
    return {'status':'restored_verified_copies' if destination is not None else 'verified_only',
            'format':FORMAT,'manifest_sha256':expected_manifest_sha256,'archive_sha256':manifest['archive_sha256'],
            'archive_bytes':manifest['archive_bytes'],'logical_files':len(files),'unique_blobs':len(blobs),
            'logical_bytes':logical_bytes,'restored_files':len(selected) if destination is not None else 0,
            'restored_bytes':sum(e['bytes'] for e in selected.values()) if destination is not None else 0,
            'prefix':prefix,'restore':str(destination) if destination is not None else None,
            'scope':'byte verification/restoration only; no build, source acceptance or board claim'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--expected-manifest-sha256',required=True)
    parser.add_argument('--restore',type=Path)
    parser.add_argument('--prefix')
    args=parser.parse_args(argv)
    try:
        report=review(args.bundle,args.expected_manifest_sha256,args.restore,args.prefix)
    except Exception as error:
        print(json.dumps({'status':'rejected','error':type(error).__name__+': '+str(error),
                          'restore_may_be_partial':args.restore is not None and os.path.lexists(args.restore)},sort_keys=True),file=sys.stderr)
        return 2
    print(json.dumps(report,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
