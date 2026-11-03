"""Display speed0=OFF; speed(0,100] maps running PWM250..750permille.

Only explicit motor commands may ARM. keepalive can renew but never restart.
Software speed/RPM units can be normalized by the eventual application adapter.
"""
from __future__ import annotations
import math,struct
from fpga_link.session import DisplaySession,LinkError,UINT32_MAX,_integer
from pc.codec import crc16_ccitt_false,decode_reply,SOURCE_TO_CODE

def duty_from_speed(speed):
    if isinstance(speed,bool)or not isinstance(speed,(int,float))or not math.isfinite(speed)or not 0<=speed<=100:
        raise LinkError('speed_pct must be finite0..100')
    return 0 if speed==0 else int(round(250+5*speed))

def encode_motor(seq,source,duty,lease=300):
    _integer(seq,'sequence',1,UINT32_MAX);_integer(duty,'duty',0,750);_integer(lease,'lease',100,500)
    if duty and duty<250:raise LinkError('display running duty minimum250')
    p=bytearray(32);p[:4]=bytes([0xd3,0x4c,1,5]);p[8]=SOURCE_TO_CODE[source]
    struct.pack_into('<I',p,4,seq);struct.pack_into('<H',p,14,duty);struct.pack_into('<H',p,18,lease)
    struct.pack_into('<H',p,30,crc16_ccitt_false(p[:30]));return bytes(p)

class VariableDisplaySession(DisplaySession):
    def __init__(self,*args,allow_motor=False,physical_path=None,**kwargs):
        super().__init__(*args,**kwargs);self.allow_motor=allow_motor
        self.motor_duty=0;self.motor_speed_pct=0;self.physical_path=physical_path

    @staticmethod
    def _capabilities(reply):
        if not reply.gimbal_output_compiled_enabled or reply.requested_duty_permille and not reply.motor_output_compiled_enabled:
            raise LinkError('gimbal and supported motor capabilities required')

    @staticmethod
    def _fresh(reply):
        VariableDisplaySession._capabilities(reply)
        if reply.last_joho_error or not reply.yaw_feedback.fresh or not reply.pitch_feedback.fresh:
            raise LinkError('fresh healthy two-axis feedback required')

    def stop(self):
        self.motor_duty=0;self.motor_speed_pct=0
        return super().stop()

    def _running_status(self):
        reply=self._send(4,require_ok=False);self._fresh(reply)
        if self.motor_duty and (not reply.armed or reply.requested_duty_permille!=self.motor_duty):
            raise LinkError('motor lease lost or changed; never auto-rearm/replay')
        return reply

    def _motor_send(self,duty,deadline):
        seq=self.journal.reserve()
        if self.clock_ms()>=deadline:raise LinkError('expired before motor dispatch')
        self.transport.write_frame(encode_motor(seq,self.source,duty))
        raw=self.transport.read_frame(.3)
        if raw is None:raise LinkError('motor reply missing; no replay')
        reply=decode_reply(raw)
        if reply.seq!=seq or reply.result_code or reply.requested_duty_permille!=duty or duty and not reply.armed:
            raise LinkError('motor refused/mismatch; stop without retry')
        self._fresh(reply)
        return reply

    def handle(self,request):
        if self.failed:raise LinkError('session fault latched; reconnect explicitly without replay')
        try:
            op=request.get('op')if isinstance(request,dict)else None
            if op not in ('motor','keepalive'):
                if op in ('pose','home')and self.motor_duty:self._running_status()
                result=super().handle(request)
                if op=='stop':self.motor_duty=0;self.motor_speed_pct=0
                if self.motor_duty and result['status']['requested_duty_permille']!=self.motor_duty:
                    raise LinkError('motor stopped during pose; never replay')
                return result
            fields={'session','request_id','expires_ms','op'}|({'speed_pct'}if op=='motor'else set())
            if set(request)-fields or request.get('session')!=self.session_id:raise LinkError('unknown field/session')
            rid=_integer(request.get('request_id'),'request_id',1,UINT32_MAX)
            deadline=_integer(request.get('expires_ms'),'expires_ms',0,2**53)
            if rid<=self.request_id or not 0<deadline-self.clock_ms()<=1000:raise LinkError('stale/expired motor request')
            self.request_id=rid
            if op=='keepalive':
                reply=self._running_status()if self.motor_duty else self._send(4,require_ok=False)
                if self.motor_duty:reply=self._motor_send(self.motor_duty,deadline)
            else:
                if not self.allow_motor:raise LinkError('motor output disabled by profile')
                duty=duty_from_speed(request.get('speed_pct'))
                if not duty:reply=self.stop()
                else:
                    status=self._running_status()
                    if not status.motor_output_compiled_enabled:raise LinkError('MTR4 motor firmware required')
                    if not self.motor_duty:self._fresh(self._send(1,deadline_ms=deadline))
                    reply=self._motor_send(duty,deadline)
                    self.motor_duty=duty;self.motor_speed_pct=request['speed_pct']
            if self.clock_ms()>deadline:raise LinkError('request expired during exchange')
            return self.record(reply,op)
        except Exception:
            self.failed=True
            try:self.stop()
            except Exception:pass
            raise

    def record(self,reply,event):
        result=super().record(reply,event)
        result.update(motor_output=bool(reply.requested_duty_permille),motor_speed_pct=self.motor_speed_pct,
                      motor_speed_mapping={'zero':'OFF','positive':'250+5*speed_pct permille','maximum':750},measured_rpm=None)
        if self.physical_path:result['physical_path']=self.physical_path
        return result
