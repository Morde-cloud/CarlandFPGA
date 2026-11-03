"""Finite MANUAL display stimulus; explicitly not the real virtual drill feed.
No serial, motor, FPGA or native application operation by this generator.
"""
import argparse,json,math,sys,time

ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-id',required=True)
ap.add_argument('--seconds',type=float,default=4);ap.add_argument('--speed',type=float,default=.025)
a=ap.parse_args()
if not .1<=a.seconds<=10 or not 0<=a.speed<=.25:ap.error('Finite manual trial only')
start=time.perf_counter_ns();index=0
try:
 while True:
  now=time.perf_counter_ns();elapsed=(now-start)/1e9
  if elapsed>=a.seconds:break
  yaw=math.radians(15*math.sin(elapsed*2*math.pi/a.seconds));pitch=math.radians(10*math.sin(elapsed*2*math.pi/a.seconds))
  # yaw about+Y, pitch up about-X, qyaw*qpitch; analytic forward vector.
  sy,cy=math.sin(yaw/2),math.cos(yaw/2);sp,cp=math.sin(pitch/2),math.cos(pitch/2)
  q=[-cy*sp,sy*cp,sy*sp,cy*cp];index+=1
  state=dict(abi='DEEPEYE-CONTINUOUS-NATIVE-794-v1',tick_usec=str(now//1000),read_now_usec=str(now//1000),
    revision=str(index),ready=True,running=a.speed>0,fault='',phase='INSIDE',orientation_xyzw=q,
    speed_m_s=a.speed,deadline_usec=str(now//1000+1_000_000))
  sample=dict(run_id=a.run_id,source='MANUAL',native=state,host=dict(send_qpc_ns=now-1000,
      receive_qpc_ns=now,accepted_tick_qpc_interval_ns=[now-1000,now]))
  print(json.dumps(sample),flush=True);time.sleep(.05)
except BrokenPipeError:
 sys.stdout.close()
