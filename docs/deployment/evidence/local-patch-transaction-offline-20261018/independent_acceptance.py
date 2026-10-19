"""Quality-main black-box checks; all writes are private synthetic fixtures."""
import copy
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fpga_mesh import local_patch_transaction as transaction

OUT=Path(__file__).resolve().parent
FIXTURES=OUT/'main-acceptance-fixtures'

def digest(data):
    return {'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def snapshot(root):
    values={}
    for path in sorted(root.rglob('*')):
        info=path.lstat()
        if path.is_file():values[path.relative_to(root).as_posix()]=(info.st_size,info.st_mtime_ns,info.st_ino,hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():values[path.relative_to(root).as_posix()]=('directory',info.st_ino)
    return values

class IndependentAcceptance(unittest.TestCase):
    def setUp(self):
        FIXTURES.mkdir(exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix='case-',dir=FIXTURES))
        self.target=self.root/'target';self.source=self.root/'source';self.journal=self.root/'journal'
        for root in (self.target,self.source,self.journal):root.mkdir()
        (self.target/'fpga_mesh').mkdir()
        self.before=[b'old-alpha\r\n\x00',b'old-beta\n']
        self.after=[b'new-alpha\r\n\x00',b'new-beta\n']
        files=[]
        for i,name in enumerate(('alpha','beta')):
            path='fpga_mesh/'+name+'.py';source='payload'+str(i)+'.bin'
            (self.target/path).write_bytes(self.before[i]);(self.source/source).write_bytes(self.after[i])
            files.append({'path':path,'source':source,'preimage':digest(self.before[i]),'postimage':digest(self.after[i])})
        self.plan={'schema':1,'operation_id':'main-independent-'+self.root.name,'target_root':str(self.target.resolve()),'source_root':str(self.source.resolve()),'journal_root':str(self.journal.resolve()),'files':files}
        self.plan_path=self.root/'plan.json'
        self.write_plan()

    def write_plan(self):
        raw=(json.dumps(self.plan,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
        self.plan_path.write_bytes(raw);self.reviewed=hashlib.sha256(raw).hexdigest()

    def call(self,name,sha=None):
        return getattr(transaction,name)(self.plan_path,reviewed_plan_sha256=sha or self.reviewed)

    def refused_without_writes(self,name='apply',sha=None):
        before=snapshot(self.root)
        with self.assertRaises(Exception):self.call(name,sha)
        self.assertEqual(snapshot(self.root),before)
        self.assertEqual(list(self.journal.iterdir()),[])

    def test_three_boundaries_success_exact_bytes_then_inspect_is_read_only(self):
        before=snapshot(self.root)
        dry=self.call('dry_run');self.assertIsInstance(dry,dict)
        self.assertEqual(snapshot(self.root),before)
        result=self.call('apply');self.assertIsInstance(result,dict)
        for i,name in enumerate(('alpha','beta')):self.assertEqual((self.target/'fpga_mesh'/f'{name}.py').read_bytes(),self.after[i])
        self.assertEqual(len(list(self.journal.iterdir())),1)
        before_inspect=snapshot(self.root)
        inspected=self.call('inspect');self.assertIsInstance(inspected,dict)
        self.assertEqual(snapshot(self.root),before_inspect)
        self.assertIn('postimage',json.dumps(inspected).lower())

    def test_last_target_conflict_prevents_all_writes(self):
        (self.target/'fpga_mesh/beta.py').write_bytes(b'foreign-last-target')
        self.refused_without_writes()

    def test_last_source_corruption_prevents_all_writes(self):
        (self.source/'payload1.bin').write_bytes(b'wrong-source')
        self.refused_without_writes()

    def test_reviewed_hash_is_required_and_not_inferred(self):
        self.refused_without_writes(sha='0'*64)
        before=snapshot(self.root)
        with self.assertRaises(TypeError):transaction.apply(self.plan_path)
        self.assertEqual(snapshot(self.root),before)

    def test_duplicate_json_key_rejected(self):
        raw=self.plan_path.read_bytes().replace(b'{',b'{"schema": 1,',1)
        self.plan_path.write_bytes(raw);self.reviewed=hashlib.sha256(raw).hexdigest()
        self.refused_without_writes()

    def test_bool_size_is_rejected(self):
        self.plan['files'][0]['preimage']['size']=True;self.write_plan()
        self.refused_without_writes()

    def test_unknown_field_cannot_expand_authority(self):
        self.plan['force']=True;self.write_plan();self.refused_without_writes()

    def test_protected_config_file_is_rejected_even_with_matching_bytes(self):
        target=self.target/'fpga_mesh/config.py';target.write_bytes(self.before[0])
        self.plan['files'][0]['path']='fpga_mesh/config.py';self.write_plan()
        self.refused_without_writes()

    def test_agents_target_is_rejected_even_with_matching_bytes(self):
        (self.target/'AGENTS.md').write_bytes(self.before[0]);self.plan['files'][0]['path']='AGENTS.md';self.write_plan()
        self.refused_without_writes()

    def test_target_case_alias_is_rejected(self):
        entry=copy.deepcopy(self.plan['files'][0]);entry['path']='fpga_mesh/ALPHA.py';entry['source']='alias.bin'
        (self.source/'alias.bin').write_bytes(self.after[0]);self.plan['files'].append(entry);self.write_plan()
        self.refused_without_writes()

    def test_actual_hardlinked_source_is_rejected(self):
        os.link(self.source/'payload0.bin',self.root/'payload-alias.bin')
        self.assertEqual((self.source/'payload0.bin').stat().st_nlink,2)
        self.refused_without_writes()

    def test_target_and_journal_overlap_is_rejected(self):
        inside=self.target/'journal';inside.mkdir();self.plan['journal_root']=str(inside.resolve());self.write_plan()
        before=snapshot(self.root)
        with self.assertRaises(Exception):self.call('apply')
        self.assertEqual(snapshot(self.root),before)

    def test_plan_inside_source_is_rejected(self):
        self.plan_path=self.source/'plan.json';self.write_plan();self.refused_without_writes()

    def test_existing_empty_journal_refuses_replay(self):
        (self.journal/self.plan['operation_id']).mkdir()
        before=snapshot(self.root)
        with self.assertRaises(Exception):self.call('apply')
        self.assertEqual(snapshot(self.root),before)

    def test_existing_completed_journal_refuses_changed_reviewed_plan(self):
        self.call('apply')
        for i,entry in enumerate(self.plan['files']):
            next_bytes=b'third-'+bytes([48+i]);entry['preimage']=digest(self.after[i]);entry['postimage']=digest(next_bytes)
            (self.source/entry['source']).write_bytes(next_bytes)
        self.write_plan();before=snapshot(self.root)
        with self.assertRaises(Exception):self.call('apply')
        self.assertEqual(snapshot(self.root),before)

    def test_torn_journal_inspect_is_ambiguous_and_read_only(self):
        self.call('apply')
        logs=list(self.journal.rglob('*.jsonl'));self.assertEqual(len(logs),1)
        with logs[0].open('ab') as stream:stream.write(b'{"incomplete":')
        before=snapshot(self.root);report=self.call('inspect')
        self.assertEqual(snapshot(self.root),before)
        text=json.dumps(report).lower()
        self.assertTrue(any(word in text for word in ('ambiguous','corrupt','torn','invalid')),text)
        self.assertTrue(report.get('requires_main_review'),report)

    def test_foreign_postcommit_content_needs_review_without_restoration(self):
        self.call('apply');target=self.target/'fpga_mesh/alpha.py';target.write_bytes(b'foreign-edit')
        before=snapshot(self.root);report=self.call('inspect')
        self.assertEqual(snapshot(self.root),before);self.assertEqual(target.read_bytes(),b'foreign-edit')
        self.assertIn('other',json.dumps(report).lower());self.assertTrue(report.get('requires_main_review'),report)

    def test_same_bytes_foreign_replacement_before_postcheck_is_not_rollback_owned(self):
        real_replace=os.replace
        alpha=self.target/'fpga_mesh/alpha.py';beta=self.target/'fpga_mesh/beta.py'
        foreign_identity=[]
        def replace(source,destination):
            if Path(destination)==beta:raise OSError('injected second replacement failure')
            result=real_replace(source,destination)
            if Path(destination)==alpha and not foreign_identity:
                foreign=self.root/'foreign-same-bytes.bin';foreign.write_bytes(self.after[0]);real_replace(foreign,alpha)
                foreign_identity.append((alpha.stat().st_dev,alpha.stat().st_ino))
            return result
        with mock.patch.object(transaction.os,'replace',side_effect=replace):report=self.call('apply')
        self.assertFalse(report['success'],report)
        self.assertEqual(alpha.read_bytes(),self.after[0],'Foreign same-bytes file was overwritten by rollback')
        self.assertEqual((alpha.stat().st_dev,alpha.stat().st_ino),foreign_identity[0])

    def test_missing_one_target_does_not_block_safe_independent_rollback(self):
        gamma=self.target/'fpga_mesh/gamma.py';gamma.write_bytes(b'old-gamma')
        (self.source/'payload2.bin').write_bytes(b'new-gamma')
        self.plan['files'].append({'path':'fpga_mesh/gamma.py','source':'payload2.bin','preimage':digest(b'old-gamma'),'postimage':digest(b'new-gamma')});self.write_plan()
        alpha=self.target/'fpga_mesh/alpha.py';beta=self.target/'fpga_mesh/beta.py';real_replace=os.replace
        def replace(source,destination):
            if Path(destination)==gamma:
                beta.unlink();raise OSError('injected final replacement failure after foreign deletion')
            return real_replace(source,destination)
        with mock.patch.object(transaction.os,'replace',side_effect=replace):report=self.call('apply')
        self.assertFalse(report['success'],report);self.assertFalse(beta.exists())
        self.assertEqual(alpha.read_bytes(),self.before[0],'Safe first file was not rolled back')

    def test_concurrent_journal_corruption_stops_before_next_target(self):
        original=transaction._Journal.append;injected=[]
        def append(journal,kind,**fields):
            value=original(journal,kind,**fields)
            if kind=='applied' and fields.get('index')==0 and not injected:
                with journal.path.open('r+b') as stream:stream.write(b'CORRUPT')
                injected.append(True)
            return value
        with mock.patch.object(transaction._Journal,'append',new=append):report=self.call('apply')
        self.assertEqual(injected,[True])
        self.assertFalse(report['success'],'Corrupted durable journal was reported as successful')
        self.assertEqual((self.target/'fpga_mesh/beta.py').read_bytes(),self.before[1])

    def test_replaced_journal_root_is_rejected_before_journal_writes(self):
        original=transaction._prepare_transaction
        def prepare(*args,**kwargs):
            self.journal.rename(self.root/'original-journal-root');self.journal.mkdir()
            return original(*args,**kwargs)
        with mock.patch.object(transaction,'_prepare_transaction',side_effect=prepare):report=self.call('apply')
        self.assertFalse(report['success'],report)
        self.assertEqual(list(self.journal.iterdir()),[],'A replacement journal directory received unauthorized writes')
        for i,name in enumerate(('alpha','beta')):self.assertEqual((self.target/'fpga_mesh'/f'{name}.py').read_bytes(),self.before[i])

    def test_payload_temporary_tampering_after_intent_is_rejected_before_replace(self):
        original=transaction._Journal.append
        def append(journal,kind,**fields):
            value=original(journal,kind,**fields)
            if kind=='write_intent' and fields.get('index')==0:
                temporary=self.target/'fpga_mesh'/fields['temporary'];temporary.write_bytes(b'foreign-temporary')
            return value
        with mock.patch.object(transaction._Journal,'append',new=append):report=self.call('apply')
        self.assertFalse(report['success'],report)
        self.assertEqual((self.target/'fpga_mesh/alpha.py').read_bytes(),self.before[0])

    def test_foreign_same_preimage_after_rollback_is_not_clean_ownership(self):
        original=transaction._write_temp_sibling
        def temporary(target,payload,*,tag):
            if Path(target).name=='beta.py' and tag=='apply':raise OSError('injected temporary write failure')
            return original(target,payload,tag=tag)
        with mock.patch.object(transaction,'_write_temp_sibling',side_effect=temporary):report=self.call('apply')
        self.assertEqual(report['status'],'rolled_back',report)
        alpha=self.target/'fpga_mesh/alpha.py';before_id=alpha.stat().st_ino
        foreign=self.root/'foreign-preimage.bin';foreign.write_bytes(self.before[0]);os.replace(foreign,alpha)
        self.assertNotEqual(alpha.stat().st_ino,before_id)
        before=snapshot(self.root);inspection=self.call('inspect')
        self.assertEqual(snapshot(self.root),before)
        self.assertTrue(inspection['requires_main_review'],inspection)

    @unittest.skipUnless(os.name=='nt','Actual Windows abandoned mutex test')
    def test_abandoned_mutex_is_released_after_fail_closed_detection(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.ReleaseMutex.argtypes=[ctypes.c_void_p];kernel.ReleaseMutex.restype=ctypes.c_int
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle.restype=ctypes.c_int
        info=self.target.stat();name=transaction._mutex_name(info.st_dev,info.st_ino)
        keeper=kernel.CreateMutexW(None,False,name);self.assertTrue(keeper)
        prefix='import os,sys; from pathlib import Path; sys.path.insert(0,'+repr(str(Path(transaction.__file__).resolve().parents[1]))+'); from fpga_mesh.local_patch_transaction import _TargetMutex; '
        try:
            crash=prefix+'m=_TargetMutex(Path('+repr(str(self.target))+')); m.__enter__(); os._exit(17)'
            first=subprocess.run([sys.executable,'-I','-B','-c',crash],capture_output=True,timeout=15)
            (self.root/'abandoned-owner.stdout.txt').write_bytes(first.stdout);(self.root/'abandoned-owner.stderr.txt').write_bytes(first.stderr)
            self.assertEqual(first.returncode,17,first.stderr)
            with self.assertRaises(transaction.MutexAbandonedError):
                with transaction._TargetMutex(self.target):pass
            acquire=prefix+'m=_TargetMutex(Path('+repr(str(self.target))+')); m.__enter__(); m.__exit__(None,None,None); print("acquired")'
            second=subprocess.run([sys.executable,'-I','-B','-c',acquire],capture_output=True,timeout=15)
            (self.root/'after-abandon.stdout.txt').write_bytes(second.stdout);(self.root/'after-abandon.stderr.txt').write_bytes(second.stderr)
            self.assertEqual(second.returncode,0,second.stderr.decode(errors='replace'))
        finally:
            kernel.ReleaseMutex(keeper);kernel.CloseHandle(keeper)

if __name__=='__main__':unittest.main(verbosity=2)
