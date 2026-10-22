"""Execute real Python entrypoint with explicitly synthetic vendor-call seam.
No ModelSim executable is started by this fixture.
"""
import argparse,importlib.util,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--runner',required=True);p.add_argument('--scenario',required=True);p.add_argument('--out',required=True);a=p.parse_args()
M=Path(__file__).parent;W=M.parents[5];D=Path(a.out);D.mkdir(parents=True,exist_ok=False)
vendor=D/'SYNTHETIC_VENDOR_NOT_EXECUTABLE';vendor.mkdir()
for n in ['vlog.exe','vsim.exe']:(vendor/n).write_bytes(b'NOT AN EXECUTABLE: controlled Python seam only\n')
spec=importlib.util.spec_from_file_location('entry_candidate21',a.runner);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
stats='SAMPLE_SCAN_STATS case=directed checks=407 errors=0 windows=1 events=14 scans=3 retired=2 discarded=6 order_errors=1 overruns=1 partial_len=0 occupied=0 armed=1 exhausted=0\nSAMPLE_SCAN_PASS\nErrors: 0, Warnings: 0\n'
def fake(argv,cwd,timeout):
    code=0;timed=False;err=b''
    if '-version' in argv:out=b'SYNTHETIC CONTROL: ModelSim SE-64 10.7\n'
    elif Path(argv[0]).stem=='vlog':
        out=b'Errors: 0, Warnings: 0\n'
        if a.scenario=='compile-error':err=b'error: injected compiler failure\n'
    elif 'guard' in str(cwd):
        out=b'NOT_** Fatal: deepeye_sample_scan_capture: SEQ_W out of range\nErrors: 1, Warnings: 0\n'
    else:
        out=stats.encode()
        if a.scenario=='sim-error':err=b'** Error: injected runtime failure\n'
        if a.scenario=='sim-exit':code=7
        if a.scenario=='timeout':timed=True;code=None
        if a.scenario=='mixed-selection' and Path(cwd).name!='directed':code=9
    return dict(argv=argv,cwd=str(cwd),exit=code,timed_out=timed,elapsed_seconds=0.0,stdout_bytes=out,stderr_bytes=err)
m._run_hidden=fake
argv=['--root',str(W),'--out',str(D/'run'),'--modelsim',str(vendor),'--case','guard_seq_w_1' if a.scenario=='guard-substring' else 'directed']
if a.scenario=='mixed-selection':argv+=['--case','exhaustive6']
if a.scenario=='duplicate-selection':argv+=['--case','directed']
print('SYNTHETIC_VENDOR_SEAM; actual Python main/selection/aggregation/exit only',flush=True)
sys.exit(m.main(argv))
