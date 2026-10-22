from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
b=(W/'competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv').read_bytes();sha=lambda x:hashlib.sha256(x).hexdigest()
assert sha(b)=='fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d'
changes={'wrong-channel-mix':(b'end else if (sample_channel == partial_len_q[1:0]) begin',b'end else if (1\'b1) begin'),'ordinal-plus-two':(b'next_seq_q <= next_seq_q + 1\'b1;',b'next_seq_q <= next_seq_q + 2\'d2;')}
records={}
for name,(old,new) in changes.items():
    assert b.count(old)==1
    d=M/'mutants-final'/name;d.mkdir(parents=True,exist_ok=False);p=d/'deepeye_sample_scan_capture.sv';p.write_bytes(b.replace(old,new))
    records[name]={'path':p.relative_to(W).as_posix(),'before':old.decode(),'after':new.decode(),'source_sha256':sha(b),'mutant_sha256':sha(p.read_bytes()),'case':'seq2','healthy_control':'seq2-02','expected_detection':'concrete numeric postreset public output difference; compile errors, warnings, X and timeouts do not count'}
with (M/'MUTANTS_FINAL_FROZEN.json').open('x',encoding='utf-8') as f:json.dump({'at_utc':datetime.now(timezone.utc).isoformat(),'mutants':records},f,indent=2);f.write('\n')
print(json.dumps(records))
