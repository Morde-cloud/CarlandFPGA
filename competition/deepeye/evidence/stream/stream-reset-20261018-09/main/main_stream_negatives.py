import argparse,hashlib,importlib.util,json,re
from pathlib import Path
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_stream',H/'main_stream_review.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
def sha(b):return hashlib.sha256(b).hexdigest()
def run(source,positive,out):
    out.mkdir(exist_ok=False);raw=source.read_bytes();s=raw.decode('utf-8')
    definitions=[
      ('core_cancel_disconnected',r'\.cancel\(cancel\),',".cancel(1'b0),"),
      ('core_ignores_output_backpressure',r'assign core_m_ready\s*=.*?;',"assign core_m_ready = !rst && !cancel && (phase_q == PHASE_OUT);"),
      ('byte_corruption',r'm_data\s*=\s*core_m_data;',"m_data = core_m_data ^ 8'h01;"),
      ('counter_wrap',r'sat_inc\s*=.*?;',"sat_inc = value + 32'd1;")]
    rows=[]
    for name,pattern,replacement in definitions:
        mutant,n=re.subn(pattern,replacement,s,count=0,flags=re.S);assert n==1,(name,n)
        path=out/(name+'.sv');path.write_bytes(mutant.encode())
        rejected=False;error=None
        try:review.run(out/name,path)
        except (AssertionError,RuntimeError) as exc:rejected=True;error=str(exc)[:1200]
        commands=json.loads((out/name/'commands.json').read_bytes())
        assert any(x['name']=='vlog' and x['exit_code']==0 for x in commands),name+' not compiled'
        assert any(x['name']=='vsim' for x in commands),name+' not simulated'
        assert rejected,name+' survived'
        rows.append({'name':name,'mutant_sha256':sha(path.read_bytes()),'rejected':rejected,'reason':error,'actual_rtl_compiled_and_simulated':True})
    lines=positive.read_text(encoding='utf-8').splitlines();events=[]
    for i,line in enumerate(lines):
        if line.startswith('E '):events.append((i,dict(zip(review.FIELDS,map(int,line.split()[1:])))))
    hgood=next(i for i,p in events if p['hf'] and not p['error']);herr=next(i for i,p in events if p['hf'] and p['error'])
    byte=next(i for i,p in events if p['bf']);cfg=next(i for i,p in events if p['cf']);sample=next(i for i,p in events if p['sf'])
    variants=[]
    for field in ['mtag','mcount','me','raw','k','bits','bytes','error']:
        variants.append(('good_header_'+field,hgood,field,1))
    for field in ['mcount','me','raw','k','bits','bytes','mtag']:
        variants.append(('error_header_'+field,herr,field,1))
    for field in ['data','last','okstat','level']:variants.append(('byte_'+field,byte,field,1))
    for field in ['cfgstat','level','filling']:variants.append(('cfg_'+field,cfg,field,1))
    for field in ['sstat','filling']:variants.append(('sample_'+field,sample,field,1))
    logrows=[];logs=out/'corrupted_logs';logs.mkdir()
    for name,index,field,delta in variants:
        copy=lines.copy();values=copy[index].split();pos=review.FIELDS.index(field)+1;values[pos]=str(int(values[pos])+delta);copy[index]=' '.join(values)
        data=('\n'.join(copy)+'\n').encode();p=logs/(name+'.txt');p.write_bytes(data)
        rejected=False
        try:review.check(p)
        except AssertionError:rejected=True
        assert rejected,name+' not rejected'
        logrows.append({'name':name,'line_index':index,'field':field,'delta':delta,'sha256':sha(data),'rejected':True})
    for name,index in [('drop_metadata',hgood),('drop_byte',byte),('duplicate_byte',byte)]:
        copy=lines.copy()
        if name.startswith('drop'):del copy[index]
        else:copy.insert(index,copy[index])
        data=('\n'.join(copy)+'\n').encode();p=logs/(name+'.txt');p.write_bytes(data)
        try:review.check(p)
        except AssertionError:pass
        else:raise AssertionError(name+' not rejected')
        logrows.append({'name':name,'line_index':index,'sha256':sha(data),'rejected':True})
    result={'status':'ALL_NEGATIVE_CONTROLS_REJECTED','source_sha256':sha(raw),'positive_ports_sha256':sha(positive.read_bytes()),'rtl_mutants':rows,'corrupted_logs':logrows,'rtl_count':len(rows),'log_count':len(logrows)}
    review.dump(out/'result.json',result);print(json.dumps({'status':result['status'],'rtl_count':len(rows),'log_count':len(logrows),'source_sha256':sha(raw)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--positive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.positive.resolve(),a.out.resolve())
