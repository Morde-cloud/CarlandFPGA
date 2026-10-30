"""Retired A70 input projection; default closed, no source-kernel execution."""
from __future__ import annotations
import argparse, copy, hashlib, json, math, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'causal_raw4_92'))
import raw4_adapter92 as a

PIN = {'commit': 'd0185d335747acb26439f40a8ce945f7f4eaa9af',
       'tree': 'd2e6533d93efcc09e8dd1341e6cc5d741fe965a5',
       'git_oid': 'fad06cd889be3909d09cf93b3f5bb5813e7f514d', 'bytes': 82496,
       'sha256': '63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c'}

def read_original(raw):
    a._need(type(raw) is bytes and len(raw) <= 100*1024, 'original input byte bound')
    a._need(len(raw) == PIN['bytes'] and a.sha256_bytes(raw) == PIN['sha256'], 'fixed original input byte/hash')
    a._need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == PIN['git_oid'], 'fixed Git blob')
    value = a.load_json_strict(raw)
    def plain(v, depth=0):
        a._need(depth <= 16 and type(v) in (dict,list,str,int,float,bool,type(None)), 'private input plain types')
        if type(v) is float: a._need(math.isfinite(v), 'private finite float')
        if type(v) is dict:
            for k,x in v.items(): a._need(type(k) is str, 'private key'); plain(x,depth+1)
        if type(v) is list:
            a._need(len(v) <= 128, 'private array bound')
            for x in v: plain(x,depth+1)
    plain(value)
    return value

def project(raw):
    v = read_original(raw)
    book = v['original_source_book']
    a._need(v['source_origin_qpc_ns'] == a.RETIRED_ORIGIN and book['source_origin_qpc_ns'] == a.RETIRED_ORIGIN, 'original origin')
    a._need(book['schema'] == 1 and book['native_interval_atomic'] is False and book['state'] == 'RETIRED', 'original book remains retired schema1')
    a._need(len(v['records']) == len(book['samples']) == len(v['actual_record_end_qpc_ns']) == 20, 'exact 20 originals')
    records = []
    for i,(p,s) in enumerate(zip(v['records'],book['samples'])):
        a._exact(p,set(a.PROFILE_METADATA)|{'adc_tick_ms','em_tick_ms','channel_counts','channel_values','quality'},'original nine fields')
        a._need(all(p[k] == x for k,x in a.PROFILE_METADATA.items()),'original candidate profile')
        a._need(p == s['payload'] and a.canonical(p).hex() == s['canonical_source_hex'] and a.digest(p) == s['source_sha256'], 'original canonical payload/book association')
        a._need(s['source_count'] == i+1 and s['tick_ms'] == i*10 and s['nominal_qpc_ns'] == a.RETIRED_ORIGIN+i*10000000,'book count/time')
        a._need(s['held_em_association'] == 'unavailable;original_native_em_association_not_implemented','missing original EM receipt retained')
        a._need(a.RETIRED_ORIGIN+i*10000000 <= s['adc']['begin_qpc_ns'] <= s['adc']['end_qpc_ns'] <= s['finish_qpc_ns'] <= v['actual_record_end_qpc_ns'][i], 'actual ADC/finish/completion ordering')
        a._need(type(p['channel_values']) is list and len(p['channel_values']) == 4,'original private value shape')
        for ch,number in enumerate(p['channel_values']):
            a._need((number is None) == (p['channel_counts'][ch] is None),'original null association')
            if number is not None: a._need(type(number) in (int,float) and math.isfinite(number),'finite original number')
        if i >= 9: a._need(p['channel_values'][3] > 0 and p['channel_counts'][3] == 0,'actual positive RMS valid count zero')
        records.append({k:p[k] for k in ('adc_tick_ms','em_tick_ms','channel_counts','quality')}|{'source_record_sha256':a.digest(p)})
    receipt=dict(PIN)
    receipt.update(original_operation_id=v['original_operation_id'], source_runtime_commit=v['source_commit'],origin_qpc_ns=v['source_origin_qpc_ns'],schema=1,native_interval_atomic=False,retired=True,missing_evidence=v['missing_evidence'],record_completion_qpc_ns=v['actual_record_end_qpc_ns'],book_records=[{'source_count':s['source_count'],'nominal_qpc_ns':s['nominal_qpc_ns'],'finish_qpc_ns':s['finish_qpc_ns'],'observed_source_qpc_ns':s['observed_source_qpc_ns'],'opened_qpc_ns':s['opened_qpc_ns'],'adc':s['adc'],'held_em_association':s['held_em_association'],'source_record_sha256':s['source_sha256']} for s in book['samples']])
    p={'schema':a.SCHEMA,'fixture_kind':a.RETIRED_KIND,'pinned_commit':a.RETIRED_COMMIT,'pinned_tree':a.RETIRED_TREE,'pinned_blob_count':2,'time_basis':a.TIME_BASIS,'origin_qpc_ns':a.RETIRED_ORIGIN,'evaluation_now_qpc_ns':a.RETIRED_ORIGIN+1200000000,'profile':dict(a.PROFILE_METADATA),'records':records,'retired_source_receipt':receipt,'fixture_transport_identity':{
        'kind':'B92_FIXTURE_TRANSPORT_IDENTITY_V1','label':a.RETIRED_KIND,'operation_id':'FIXTURE-RETIRED97-NOT-A-ROOT','kernel_boot_id':a.RETIRED_KIND,'session_id':'FIXTURE-RETIRED97-SESSION','clock_domain_id':'A_ORIGINAL_NOMINAL_QPC_NS-FIXTURE','transport_receipt_id':'FIXTURE-RETIRED97-TRANSPORT','source_note':'not A Root/admission/capture/BOOT/action proof; retired original numerical transport fixture','board':'not_run; A only'}}
    a.validate_projection(p)
    return p

def boundaries(raw,p):
    rows=[]
    def refusal(name,fn):
        try: fn()
        except a.Rejected as e: rows.append({'case':name,'refused':True,'reason':str(e)}); return
        raise RuntimeError('FALSE_ACCEPT '+name)
    refusal('altered_original_byte',lambda:project(raw[:-1]+bytes([raw[-1]^1])))
    for case in ('receipt_time','record_quality'):
        q=copy.deepcopy(p)
        if case=='receipt_time': q['retired_source_receipt']['record_completion_qpc_ns'][0]+=1
        else: q['records'][1]['quality']=7
        refusal(case,lambda:a.validate_projection(q))
    closed=a.transport_input()
    a._need(closed['input_status']=='INPUT_UNAVAILABLE' and closed['command'] is None and closed['core_ran'] is False and closed['current_source_eligible'] is False,'default closed')
    rows.append({'case':'default','result':closed})
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fixture-mode');ap.add_argument('--input',type=Path);ap.add_argument('--out',type=Path);o=ap.parse_args()
    if o.fixture_mode is None:
        print(json.dumps(a.transport_input()));return 0
    a._need(o.fixture_mode==a.RETIRED_KIND and o.input is not None and o.out is not None,'explicit retired fixture mode/input/output required')
    raw=o.input.read_bytes();p=project(raw);checks=boundaries(raw,p)
    o.out.mkdir(exist_ok=False)
    (o.out/'projection.json').write_bytes(a.canonical(p))
    words=[]
    for r in p['records']: words.extend([0 if n is None else n for n in r['channel_counts']]+[r['em_tick_ms'],r['quality'],r['adc_tick_ms']])
    (o.out/'records.hex').write_text(''.join('%04x\n'%n for n in words),encoding='ascii')
    (o.out/'INPUT_RESULT.json').write_bytes(a.canonical({'input':PIN,'checks':checks,'records':20,'private_floats_transported':False,'current_source_eligible':False,'native_interval_atomic':False}))
    print(json.dumps({'records':20,'fixed_input_verified_before_parse':True,'checks':checks}))
    return 0
if __name__=='__main__': raise SystemExit(main())
