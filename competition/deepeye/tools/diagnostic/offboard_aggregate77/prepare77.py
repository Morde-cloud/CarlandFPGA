"""Author synthetic raw12 fixture and pin unchanged dependencies to B74 source."""
import sys
sys.dont_write_bytecode=True
import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[3];ROOT=P.parents[1]
BASE='4264eb954bb4c26cea80689e5c3bb68b9040b2b3'
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def main():
    fixed=[P/f'fpga/acquisition/{n}.sv' for n in ['deepeye_sample_scan_capture','deepeye_raw_scan_queue','deepeye_buffered_scan_capture','deepeye_scan_lane_stream']]
    fixed += [P/f'fpga/codec/{n}.sv' for n in ['deepeye_block_encoder','deepeye_trace_payload_candidate']]
    fixed += [P/f'fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/{n}.sv' for n in ['deepeye_trace_block_payload_1us_candidate','deepeye_trace_block_uart_50mhz_candidate']]
    fixed += [P/f'fpga/transport/{n}.sv' for n in ['deepeye_crc16_byte','deepeye_wire_serializer','deepeye_uart_tx']]
    fixed += [P/'golden/codec/trace_candidate.py',P/'tools/diagnostic/g05_capture/build/owned_process.py',ROOT/'fpga_mesh/windows_job.py']
    pins={}
    for f in fixed:
        rel=f.relative_to(ROOT).as_posix();raw=f.read_bytes()
        original=subprocess.run(['git','show',BASE+':'+rel],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10).stdout
        assert raw==original,('dependency differs from fixed source',rel)
        pins[rel]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    (P/'fpga/diagnostic/offboard_aggregate77/dependency_pins.json').write_text(json.dumps(dict(source=BASE,files=pins),indent=2)+'\n')
    origin=9007199254740993
    values=[32769,65280,4096,65535,32770,65279,5000,0,32771,65278,6000,65535]
    quality=[128,254,85,163]
    context=dict(operation_id='B77-SYNTHETIC-NOT-ADC',kernel_boot_id='SYNTHETIC-NO-REAL-BOOT',session_id='SYNTHETIC-B77-RAW12',
      clock_domain_id='SYNTHETIC-ORIGINAL-QPC-NS',request_hash='77'*32,tested_commit=BASE,build_manifest_sha256='76'*32)
    records=[]
    for i,value in enumerate(values):
        sn,ch=divmod(i,4);q=origin+10000123+sn*10000000+ch*1007
        r=dict(channel=ch,index=i,native_tag=17,native_first_seq=4*sn,native_last_seq=4*sn+3,
          acquisition_qpc_ns=q,source_qpc_ns=q,remainder_ns=(q-origin)%1000,raw_quality=quality[ch],original_value=value,valid=True,held=False)
        r['source_identity']=dict(context,source_record_sha256=digest(r),capture_sha256=digest(dict(scan=sn,values=values[sn*4:sn*4+4])),
          tag=17,generation=1,trigger_id=77,request_seq=1,capture_seq=sn,source_admission_index=i)
        records.append(r)
    f=dict(schema='B77_SYNTHETIC_RAW12_V1',evidence_kind='SYNTHETIC_FIXTURE',origin_qpc_ns=origin,
      context=context,receiver_qpc_ns=origin+40000000,now_qpc_ns=origin+50000000,records=records,
      note='All identities are synthetic labels, not actual ADC/BOOT/authentication. tested_commit labels source dependency, execution uses exact snapshots.')
    (P/'golden/diagnostic/offboard_aggregate77/SYNTHETIC_raw12.json').write_bytes(canonical(f)+b'\n')
    print(json.dumps(dict(fixed_dependencies=len(pins),synthetic_records=12,requirements='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804')))
if __name__=='__main__':main()
