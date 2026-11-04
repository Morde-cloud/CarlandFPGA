"""Offline MTR5 paced-reply build and focused safety/FIFO regression. No hardware."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys
H=Path(__file__).resolve().parent;G=H/'generated';S=H/'src';B=H/'build4';E=H/'build4-evidence';B.mkdir();E.mkdir();calls=[];W=H.parents[3];BASE=W/'output/drill-joint-uart-20261104/mtr4_reference/firmware'
SDK=Path('C:/ti/mspm0_sdk_2_11_00_07');CC=Path('C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,cwd=H):
 n=len(calls);now=datetime.datetime.now(datetime.timezone.utc).isoformat();q=subprocess.Popen([str(a) for a in args],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);out,err=q.communicate();(E/f'{n:02}.stdout').write_bytes(out);(E/f'{n:02}.stderr').write_bytes(err);r={'argv':[str(a) for a in args],'cwd':str(cwd),'actual_pid':q.pid,'started_utc':now,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':q.returncode,'stdout_sha256':hashlib.sha256(out).hexdigest(),'stderr_sha256':hashlib.sha256(err).hexdigest()};calls.append(r);(E/'COMMANDS.json').write_text(json.dumps(calls,indent=2),encoding='utf-8');print(json.dumps(r));assert q.returncode==0,(out+err).decode(errors='replace');return out
host=H/'host4';host.mkdir();flags=['cl','/nologo','/TC','/W4','/WX','/DDEMO_GIMBAL_ONLY=1','/DDEMO_YAW_BOUND_CDEG=9000','/DDEMO_PITCH_BOUND_CDEG=9000','/I'+str(H),'/I'+str(S),'/I'+str(H/'firmware'),'/I'+str(BASE)]
argv=flags+[str(H/'delta_test.c'),str(H/'motor_control.c'),str(S/'free_control.c'),str(H/'firmware/demo_core.c'),'/Fe'+str(host/'delta_test.exe')]
cmd='@echo off\ncall "D:/develop/vs2022/Community/VC/Auxiliary/Build/vcvars64.bat"\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(argv)+'\nexit /b %errorlevel%\n';(H/'compile_host4.cmd').write_text(cmd,encoding='ascii')
run(['cmd.exe','/d','/c',H/'compile_host4.cmd'],host);run([host/'delta_test.exe'])
pacer_args=flags+[str(H/'uart_reply_pacer_test.c'),'/Fe'+str(host/'uart_reply_pacer_test.exe')]
pacer_cmd='@echo off\ncall "D:/develop/vs2022/Community/VC/Auxiliary/Build/vcvars64.bat"\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(pacer_args)+'\nexit /b %errorlevel%\n'
(H/'compile_pacer4.cmd').write_text(pacer_cmd,encoding='ascii')
run(['cmd.exe','/d','/c',H/'compile_pacer4.cmd'],host)
schedule=run([host/'uart_reply_pacer_test.exe']);(E/'PACER_SCHEDULE.json').write_bytes(schedule)
run([CC/'bin/tiarmclang.exe','--version'])
flags=['-march=thumbv6m','-mcpu=cortex-m0plus','-mfloat-abi=soft','-mlittle-endian','-mthumb','-DDEMO_GIMBAL_ONLY=1','-DDEMO_YAW_BOUND_CDEG=9000','-DDEMO_PITCH_BOUND_CDEG=9000','-O2','-g','-Wall','-Wextra','-Werror','@'+str(G/'device.opt'),'-I'+str(G),'-I'+str(S),'-I'+str(H),'-I'+str(H/'firmware'),'-I'+str(BASE),'-I'+str(SDK/'source'),'-I'+str(SDK/'source/third_party/CMSIS/Core/Include')]
sources=[S/'free_control_main.c',S/'free_control.c',H/'motor_control.c',H/'drill_pwm.c',H/'firmware/demo_core.c',G/'ti_msp_dl_config.c',SDK/'source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c'];objects=[]
for src in sources:
 obj=B/(src.stem+'.o');objects.append(obj);run([CC/'bin/tiarmclang.exe','-c',*flags,src,'-o',obj])
run([CC/'bin/tiarmclang.exe',*flags,*objects,'-Wl,-m'+str(B/'motor_delta.map'),'-Wl,-i'+str(SDK/'source'),'-Wl,-i'+str(CC/'lib'),'-Wl,--rom_model','-Wl,--warn_sections','-Wl,-l'+str(G/'device_linker.cmd'),'-Wl,-l'+str(G/'device.cmd.genlibs'),'-Wl,-llibc.a','-o',B/'motor_delta.out'])
run([CC/'bin/tiarmhex.exe','--byte','--memwidth=8','--romwidth=8','--intel','-o',B/'motor_delta.hex',B/'motor_delta.out'])
files=[*sources[:-1],S/'free_control.h',H/'motor_control.h',H/'drill_pwm.h',H/'motor.syscfg',Path(__file__),H/'delta_test.c',H/'uart_reply_pacer.h',H/'uart_reply_pacer_test.c',BASE/'demo_core.h',G/'ti_msp_dl_config.h',G/'device.opt',G/'device_linker.cmd',G/'device.cmd.genlibs',B/'motor_delta.out',B/'motor_delta.map',B/'motor_delta.hex']
manifest={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':'B-A169-UART-OVERRUN-REPAIR-20261104-492','firmware_signature':'0x4d545235','baseline_ELF_SHA':'49baf1e83fa06158e211533154e77d03958f1c273d49139ff42c23ff24fe1cbc','opcode':6,'schema':'COMPOUND_DELTA_V1','candidate_only':True,'mcu_flashed':False,'actual_servo_or_motor_tested':False,'requirements_sha256':'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d','commands_exit':[r['exit_code'] for r in calls],'files':[{'path':f.relative_to(W).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]};(E/'BUILD_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps({'commands':len(calls),'commands_exit':manifest['commands_exit'],'image_sha256':sha(B/'motor_delta.out'),'HEX_sha256':sha(B/'motor_delta.hex'),'actual_hardware':False}));sys.exit(0)
