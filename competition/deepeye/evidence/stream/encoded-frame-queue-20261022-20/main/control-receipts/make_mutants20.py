from pathlib import Path
import hashlib,json
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
M=W/'competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main'
source=W/'competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv'
raw=source.read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(raw)=='68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a'
out=M/'compiled-mutations-02';out.mkdir(exist_ok=False)
changes=[('early_metadata',b'(slot_status[head_q] == SLOT_SEAL) &&\n                            !slot_meta_done',b'((slot_status[head_q] == SLOT_SEAL) || (slot_status[head_q] == SLOT_RECV)) &&\n                            !slot_meta_done'),
         ('ignore_cancel',b'end else if (cancel) begin',b'end else if (1\'b0 && cancel) begin')]
records=[]
for name,before,after in changes:
    assert raw.count(before)==1,(name,raw.count(before))
    mutated=raw.replace(before,after);p=out/(name+'.sv');p.write_bytes(mutated)
    records.append(dict(name=name,path=str(p),source_sha256=sha(raw),mutant_sha256=sha(mutated),before=before.decode(),after=after.decode()))
(out/'MUTATIONS.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
