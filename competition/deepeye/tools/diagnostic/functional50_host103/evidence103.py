"""Exclusive local evidence with work/cleanup/finalization partitions."""
from pathlib import Path
from host103 import DEFAULT_LIMITS, Refused, canonical, need, sha

class Evidence:
    EVENT_MAX = 1024
    def __init__(self, output, request, limits=None):
        self.root=Path(output)
        self.limits=dict(DEFAULT_LIMITS if limits is None else limits)
        for key,value in self.limits.items():
            need(key in DEFAULT_LIMITS and type(value) in (int,float) and 0<value<=DEFAULT_LIMITS[key],'limits may only decrease')
            if key in ('wire','retained','frames','nominal_parent_seconds'):
                need(value==DEFAULT_LIMITS[key],'fixed one-scan scope/nominal supervision limits are immutable')
        need(set(self.limits)==set(DEFAULT_LIMITS),'exact limit fields')
        self.caps={k:self.limits[k+'_evidence'] for k in ('work','cleanup','final')}
        self.reserved={k:0 for k in self.caps}
        self.actual={k:0 for k in self.caps}
        self.root.mkdir(parents=True,exist_ok=False)
        self.sequence=0
        self.emit('work',{'event':'OUTPUT_RESERVED','kind':'SOFTWARE_FAKE_CSR','request_sha256':sha(canonical(request))})
        self.file('work','REQUEST.json',canonical(request),262144)

    def _reserve(self,phase,amount):
        need(type(amount) is int and amount>=0,'evidence reserve amount')
        need(self.reserved[phase]+amount<=self.caps[phase],phase+' evidence budget')
        self.reserved[phase]+=amount

    def _append(self,phase,raw):
        # Bytes for an effect outcome were reserved before that effect. Never
        # recheck an elapsed operational deadline before saving its outcome.
        need(self.actual[phase]+len(raw)<=self.reserved[phase],'unreserved log bytes')
        with (self.root/(phase+'.jsonl')).open('ab') as f:
            f.write(raw)
        self.actual[phase]+=len(raw)

    def emit(self,phase,value):
        raw=canonical(value)+b'\n'
        need(len(raw)<=self.EVENT_MAX,'bounded event')
        self._reserve(phase,len(raw));self._append(phase,raw)

    def before(self,phase,intent,counters):
        # Reserve both intent and worst-case outcome; an unlogged action is
        # impossible when the phase has insufficient remaining capacity.
        self._reserve(phase,2*self.EVENT_MAX)
        self.sequence+=1
        token=self.sequence
        raw=canonical({'event':'INTENT','id':token,'intent':intent,'counters':counters})+b'\n'
        need(len(raw)<=self.EVENT_MAX,'intent byte cap')
        self._append(phase,raw)
        return token

    def after(self,phase,token,value=None,error=None):
        raw=canonical({'event':'RETURN' if error is None else 'EFFECT_UNKNOWN',
                       'id':token,'value':value,'error':error})+b'\n'
        need(len(raw)<=self.EVENT_MAX,'outcome byte cap')
        self._append(phase,raw)

    def file(self,phase,name,raw,limit):
        need(type(raw) is bytes and len(raw)<=limit,'artifact byte cap')
        need(Path(name).name==name,'flat evidence filename')
        self._reserve(phase,len(raw))
        with (self.root/name).open('xb') as f:
            f.write(raw)
        self.actual[phase]+=len(raw)

    def finalize(self,result):
        result=dict(result)
        result['evidence_actual_bytes_before_result']=dict(self.actual)
        result['evidence_reserved_bytes_before_result']=dict(self.reserved)
        result['evidence_caps']=dict(self.caps)
        raw=canonical(result)
        self.file('final','RESULT.json',raw,1024*1024)
        need(sum(self.actual.values())<=8*1024*1024,'total evidence cap')
        return result
