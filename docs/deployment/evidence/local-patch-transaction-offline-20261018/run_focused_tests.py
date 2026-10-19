import argparse
import functools
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import unittest
from pathlib import Path

OUT=Path(__file__).resolve().parent
WT=Path('D:/pynq/CarlandFPGA/.local/worktrees/runtime-continuity-20261016')
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--suite',choices=['worker','independent','both','targeted'],required=True);parser.add_argument('--case',action='append',default=[])
args=parser.parse_args()
RUN=(OUT/args.run).resolve();assert RUN.parent==OUT.resolve()
RUN.mkdir(exist_ok=False)
sys.dont_write_bytecode=True;sys.path.insert(0,str(WT))
temp=RUN/'temp';temp.mkdir();os.environ['TEMP']=str(temp);os.environ['TMP']=str(temp);os.environ['PYTHONDONTWRITEBYTECODE']='1'
from fpga_mesh import local_patch_transaction as transaction
observations=RUN/'call-observations.jsonl'
def observed(name,function):
    @functools.wraps(function)
    def invoke(*arguments,**keywords):
        record={'api':name,'plan_path':str(arguments[0]) if arguments else str(keywords.get('plan_path'))}
        try:
            value=function(*arguments,**keywords);record['result']=value
            return value
        except BaseException as exc:
            record['exception']={'type':type(exc).__name__,'message':str(exc)}
            raise
        finally:
            with observations.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(record,ensure_ascii=False)+'\n')
    return invoke
for api_name in ('dry_run','apply','inspect'):
    setattr(transaction,api_name,observed(api_name,getattr(transaction,api_name)))
class ObservedResult(unittest.TextTestResult):
    def __init__(self,*arguments,**keywords):
        super().__init__(*arguments,**keywords);self.subtest_observations=[]
    def addSubTest(self,test,subtest,error):
        self.subtest_observations.append({'id':subtest.id(),'outcome':'passed' if error is None else 'failed','exception':None if error is None else str(error[1])})
        super().addSubTest(test,subtest,error)
suite=unittest.TestSuite()
if args.suite=='targeted':
    assert args.case
    suite.addTests(unittest.defaultTestLoader.loadTestsFromNames(args.case))
if args.suite in ('worker','both'):suite.addTests(unittest.defaultTestLoader.loadTestsFromName('tests.test_local_patch_transaction'))
if args.suite in ('independent','both'):
    spec=importlib.util.spec_from_file_location('independent_acceptance',OUT/'independent_acceptance.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
def ids(tests):
    for item in tests:
        if isinstance(item,unittest.TestSuite):yield from ids(item)
        else:yield item.id()
selected=list(ids(suite))
(RUN/'selected-tests.json').write_text(json.dumps(selected,indent=2)+'\n',encoding='utf-8')
start=time.monotonic();result=unittest.TextTestRunner(verbosity=2,resultclass=ObservedResult).run(suite)
modules={}
for name,module in list(sys.modules.items()):
    if name=='fpga_mesh' or name.startswith('fpga_mesh.') or name=='tests' or name.startswith('tests.'):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve();assert path.is_relative_to(WT.resolve()),(name,str(path))
            modules[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
record={'tests_run':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':[(str(t),reason) for t,reason in result.skipped],'subtest_observations':result.subtest_observations,'elapsed_seconds':round(time.monotonic()-start,3),'python':sys.version,'platform':platform.platform(),'suite':args.suite,'project_imports':modules,'all_project_imports_in_worktree':True,'source_sha256':hashlib.sha256((WT/'fpga_mesh/local_patch_transaction.py').read_bytes()).hexdigest(),'test_sha256':hashlib.sha256((WT/'tests/test_local_patch_transaction.py').read_bytes()).hexdigest()}
(RUN/'RESULT.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() else 1)
