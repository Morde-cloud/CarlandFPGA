"""Pure private G05 descriptor/snapshot validation. No MMIO or PYNQ import.

Not a hardware receipt, public BOOT verifier or motion grant. The actual
collector must supply before/after register reads and exact operation inputs.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
ROM_SHA='d9d85c32bf2e6dedc843e36658079a18ec0034f55298b9d0bb8792dadf7dfb4b'
MAGIC=0x47303544
PERIOD=2000000
# Private engine revision1 rearms at actual application+7; a completed raw
# capture slot is consumed no earlier than one further edge. This is a logic
# composition bound, not measured cable latency or a public clock guarantee.
CAPTURE_JOIN_MIN_OFFSET=8
# Exact integer floors independently certified by rational Simpson enclosure,
# then matched to reviewed42-row RTL ROM. No caller-supplied limits are trusted.
LIMITS=(
 (0,128234,512938,1154111,2051753,3205865,4616446,6283496,8207015,10387004,12823462,15516389,18465785,21671651,25133986,28852790,32828063,37059806,41548017,46292698,51293849),
 (0,8,32,73,131,205,295,402,525,664,820,993,1181,1386,1608,1846,2100,2371,2659,2962,3282),
)

class Rejected(ValueError):pass

def require(test,message):
    if not test:raise Rejected(message)

def uint(v,bits,name):
    require(type(v) is int and 0<=v<(1<<bits),name+' must be unsigned integer')
    return v

def exact(v,keys,name):
    require(type(v) is dict and set(v)==set(keys),name+' fields mismatch')

def signed16(v):
    v=uint(v,16,'signed16 bits');return v if v<32768 else v-65536

def parse_json(raw):
    require(type(raw) is bytes and 0<len(raw)<=1048576,'bounded JSON bytes required')
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def bad(value):raise Rejected('non-integer/nonfinite JSON number unsupported')
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_constant=bad,parse_float=bad)

def pinned_limits(raw):
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==ROM_SHA,'exact reviewed ROM bytes required')
    rows=parse_json(raw)['rows']
    require(len(rows)==42,'42 ROM entries required')
    observed={(r['profile_id'],r['speed_code']):r['curvature_limit'] for r in rows}
    require(observed=={(p,c):LIMITS[p-1][c] for p in (1,2) for c in range(21)},'ROM differs from independent integer proof')
    return LIMITS

@dataclass(frozen=True)
class Command:
    command_id:int
    tag:int
    profile:int
    yaw:int
    pitch:int
    speed:int
    ttl_ms:int

def validate_command(obj):
    exact(obj,('command_id','tag','profile','yaw','pitch','speed','ttl_ms'),'command')
    cid=uint(obj['command_id'],32,'command_id');require(cid>0,'command_id zero')
    tag=uint(obj['tag'],32,'tag');profile=uint(obj['profile'],8,'profile')
    speed=uint(obj['speed'],8,'speed');ttl=uint(obj['ttl_ms'],16,'TTL')
    require(profile in (1,2) and speed<=20,'unknown profile/speed')
    require(1<=ttl<=(3000 if profile==1 else 12000),'TTL outside frozen range')
    y,p=obj['yaw'],obj['pitch']
    require(type(y) is int and type(p) is int and -15000<=y<=15000 and -15000<=p<=15000,'axis range/type')
    require(speed!=0 or (y==0 and p==0),'zero-speed nonzero axes')
    require(y*y+p*p<=LIMITS[profile-1][speed],'combined postquantized curvature')
    return Command(cid,tag,profile,y,p,speed,ttl)

def command_words(c):
    c=checked_command(c)
    return (c.yaw&65535,c.pitch&65535,c.profile,c.speed,c.ttl_ms,c.command_id,c.tag)

def checked_command(c):
    require(type(c) is Command,'exact Command type required')
    return validate_command({k:getattr(c,k) for k in ('command_id','tag','profile','yaw','pitch','speed','ttl_ms')})

def identity_words(run_hex,nonce_hex,session):
    require(type(run_hex) is str and re.fullmatch('[0-9a-f]{64}',run_hex),'run_id must be full256bit hex')
    require(type(nonce_hex) is str and re.fullmatch('[0-9a-f]{32}',nonce_hex),'nonce must be full128bit hex')
    run=int(run_hex,16);nonce=int(nonce_hex,16);uint(session,32,'session')
    require(run!=0 and nonce!=0 and session!=0,'nonzero fullidentity required')
    return tuple((run>>(32*i))&0xffffffff for i in range(8))+tuple((nonce>>(32*i))&0xffffffff for i in range(4))+(session,)

def decode_high(value,base,step,lo,hi):
    uint(value,32,'high count')
    q=(value-base)//step
    choices={max(lo,min(hi,q)),max(lo,min(hi,q+1))}
    code=min(choices,key=lambda c:(abs(value-(base+step*c)),c))
    require(abs(value-(base+step*code))<=2,'high outside candidate tolerance')
    return code

def _words(value,n,name):
    require(type(value) in (tuple,list) and len(value)==n,name+' length/type')
    return tuple(uint(v,32,name) for v in value)

def _u64(words,i):return words[i]|(words[i+1]<<32)

def validate_snapshot(words,command,session):
    """Validate already-read raw record. This function alone proves no live read."""
    command=checked_command(command)
    w=_words(words,32,'record');uint(session,32,'session')
    require(w[31]==MAGIC and w[30]==session and session!=0,'record identity/magic mismatch')
    require(w[0]>0 and (w[1],w[2])==(command.command_id,command.tag),'record command/sequence mismatch')
    require(w[3]==command.profile+(command.speed<<8),'record profile/speed/reserved mismatch')
    require(w[4]==((command.yaw&65535)|((command.pitch&65535)<<16)) and w[5]==command.ttl_ms,'record payload mismatch')
    applied,deadline,event=_u64(w,6),_u64(w,8),_u64(w,10)
    require(deadline>applied and deadline-applied==command.ttl_ms*100000,'original application/deadline mismatch')
    require(applied<event<deadline,'capture event outside live TTL')
    periods=w[12:15];highs=w[15:18]
    starts=tuple(_u64(w,18+2*i) for i in range(3));ends=tuple(_u64(w,24+2*i) for i in range(3))
    require(event-applied>=CAPTURE_JOIN_MIN_OFFSET+max(ends),'capture witnesses exceed post-application event time')
    require(max(starts)-min(starts)<=2 and max(ends)-min(ends)<=2,'private cross-channel epoch skew')
    for period,high,start,end in zip(periods,highs,starts,ends):
        require(start>0 and end>start and end-start==period,'incomplete/mixed interval')
        require(abs(period-PERIOD)<=2 and 0<high<period,'period/high invalid')
    # Angle code coordinate uses q directly: high=250000+16*q.
    decoded=(decode_high(highs[0],250000,16,-15000,15000),
             decode_high(highs[1],250000,16,-15000,15000),
             decode_high(highs[2],50000,1000,0,20))
    require(decoded==(command.yaw,command.pitch,command.speed),'decoded raw channels differ from command')
    return {'capture_seq':w[0],'command_id':w[1],'tag':w[2],'decoded':decoded,
            'periods':periods,'highs':highs,'starts':starts,'ends':ends,
            'applied_cycle':applied,'deadline_cycle':deadline,'joined_event_cycle':event,
            'movement_authorized':False,'physical_evidence_established':False}

def validate_readback(*,identity_expected,identity_before,identity_after,
                      status_before,status_after,fault_before,fault_after,
                      command_before,command_after,record,sequence_after,command):
    """Check reads immediately before/after record, AFTER LATCH was acknowledged.

    These are caller-supplied bytes, not fabricated device provenance.
    """
    command=checked_command(command)
    ident=_words(identity_expected,13,'expected identity')
    require(any(ident[:8]) and any(ident[8:12]) and ident[12]!=0,'empty identity')
    require(_words(identity_before,13,'identity before')==ident==_words(identity_after,13,'identity after'),'session changed')
    for status in (status_before,status_after):
        uint(status,32,'status')
        require(status&~0x7f==0 and status&0x67==0x25 and status&8==0,'live bound/running/held latch required')
    require(uint(fault_before,32,'fault before')==uint(fault_after,32,'fault after')==0,'device fault')
    require(uint(command_before,32,'command before')==uint(command_after,32,'command after')==command.command_id,'command changed')
    result=validate_snapshot(record,command,ident[12])
    require(uint(sequence_after,32,'held sequence after')==result['capture_seq'],'held record changed')
    return result
