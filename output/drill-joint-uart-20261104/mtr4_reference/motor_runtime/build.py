"""Build MTR4 from the accepted V8 snapshot; offline, never opens hardware."""
from pathlib import Path
from datetime import datetime
import hashlib,json,re,subprocess
H=Path(__file__).resolve().parent;R=H.parent;BASE=R/'gimbal';S=H/'src';G=H/'generated';B=H/'build';E=H/'evidence'
for p in (S,G,B,E):p.mkdir(parents=True,exist_ok=True)
SDK=Path('C:/ti/mspm0_sdk_2_11_00_07');CC=Path('C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS')
stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f');calls=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):
    p=subprocess.run([str(x) for x in args],cwd=H,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
    calls.append({'command':[str(x) for x in args],'exit_code':p.returncode,'output':p.stdout})
    (E/('build-'+stamp+'.json')).write_text(json.dumps(calls,indent=2)+'\n',encoding='utf8')
    print(p.stdout,end='');p.check_returncode()
baseline=json.loads((R/'evidence/free-control-20261103/latest-build.json').read_text())
assert baseline['firmware_signature']=='0x46524338'
for item in baseline['files']:
    if item['path'].replace('\\','/').startswith('gimbal/free_control'):
        assert sha(R/item['path'])==item['sha256']
(S/'free_control.h').write_bytes((BASE/'free_control.h').read_bytes())
c=(BASE/'free_control.c').read_text();assert c.count('0x46524338u')==1
(S/'free_control.c').write_text(c.replace('0x46524338u','0x4d545234u'),encoding='utf8')
main=(BASE/'free_control_main.c').read_text()
main=main.replace('Candidate UART1 PC controller. No motor configuration or output exists.','MTR4 UART1 PC controller; motor-only leases with unchanged V8 gimbal control.')
main=main.replace('#include "free_control.h"','#include "free_control.h"\n#include "motor_control.h"\n#include "drill_pwm.h"')
main=main.replace('FreeControl free_diagnostics;','FreeControl free_diagnostics;\nMotorRuntime motor_diagnostics;\nvolatile uint32_t motor_pwm_applied,motor_pwm_peak,motor_gpio_output,motor_pincm;')
main=main.replace('SYSCFG_DL_init();','SYSCFG_DL_init();drill_pwm_init_off();mc_init(&motor_diagnostics);')
main=main.replace('fc_command(&free_diagnostics,pc,ticks,reply);','mc_command(&motor_diagnostics,&free_diagnostics,pc,ticks,reply);')
needle='        DL_GPIO_clearPins(STATUS_PORT,STATUS_BLUE_PIN|STATUS_RED_PIN|STATUS_GREEN_PIN);'
assert main.count(needle)==1
main=main.replace(needle,'''        mc_tick(&motor_diagnostics,&free_diagnostics,ticks);
        if(motor_diagnostics.duty!=drill_pwm_get_permille())
            (void)drill_pwm_set_permille(motor_diagnostics.duty);
        motor_pwm_applied=drill_pwm_get_permille();
        if(motor_pwm_applied>motor_pwm_peak)motor_pwm_peak=motor_pwm_applied;
        motor_gpio_output=GPIO_DRILL_PWM_C0_PORT->DOUT31_0 & GPIO_DRILL_PWM_C0_PIN;
        motor_pincm=IOMUX->SECCFG.PINCM[GPIO_DRILL_PWM_C0_IOMUX];
'''+needle)
(S/'free_control_main.c').write_text(main,encoding='utf8')
syscfg=(BASE/'free_control.syscfg').read_text()+'''
const PWM=scripting.addModule("/ti/driverlib/PWM",{},false);
const DRILL=PWM.addInstance();
DRILL.$name="DRILL_PWM";DRILL.ccIndex=[0];DRILL.clockPrescale=1;DRILL.timerCount=1600;
DRILL.peripheral.$assign="TIMG0";DRILL.peripheral.ccp0Pin.$assign="PA12";
DRILL.PWM_CHANNEL_0.dutyCycle=0;
'''
(H/'motor.syscfg').write_text(syscfg,encoding='utf8')
run(['C:/ti/sysconfig_1.28.0/sysconfig_cli.bat','--script',H/'motor.syscfg','--output',G,'--product',SDK/'.metadata/product.json','--compiler','ticlang'])
header=(G/'ti_msp_dl_config.h').read_text()
for key,value in {'DRILL_PWM_INST':'TIMG0','DRILL_PWM_INST_CLK_FREQ':'32000000','GPIO_DRILL_PWM_C0_PIN':'DL_GPIO_PIN_12',
 'GPIO_DRILL_PWM_C0_IOMUX':'(IOMUX_PINCM34)','GPIO_DRILL_PWM_C0_IOMUX_FUNC':'IOMUX_PINCM34_PF_TIMG0_CCP0','BUS_UART_INST':'UART0','PC_UART_INST':'UART1'}.items():
    assert re.search(r'^#define\s+'+key+r'\s+'+re.escape(value)+r'\s*$',header,re.M),(key,value)
generated=(G/'ti_msp_dl_config.c').read_text()
assert 'DL_TIMER_CC_OCTL_INIT_VAL_LOW' in generated and 'DL_TimerG_startCounter' not in generated
pwm=(R/'motor_pwm/drill_pwm.c').read_text()
needle='    if(duty>1000u){drill_pwm_stop();return 0;}'
assert needle in pwm
pwm=pwm.replace(needle,needle+'\n    if(duty==selected_duty && duty!=0u)return 1; /* Same duty renewal must not restart the timer. */')
pwm=pwm.replace('compare=PERIOD_COUNTS-((PERIOD_COUNTS*(uint32_t)duty)/1000u);',
                'compare=(PERIOD_COUNTS-1u)-((PERIOD_COUNTS*(uint32_t)duty)/1000u); /* DOWN: high=(LOAD-CC)/(LOAD+1). */')
(H/'drill_pwm.c').write_text(pwm,encoding='utf8');(H/'drill_pwm.h').write_bytes((R/'motor_pwm/drill_pwm.h').read_bytes())
flags=['-march=thumbv6m','-mcpu=cortex-m0plus','-mfloat-abi=soft','-mlittle-endian','-mthumb','-DDEMO_GIMBAL_ONLY=1',
 '-DDEMO_YAW_BOUND_CDEG=9000','-DDEMO_PITCH_BOUND_CDEG=9000','-O2','-g','-Wall','-Wextra','-Werror','@'+str(G/'device.opt'),
 '-I'+str(G),'-I'+str(S),'-I'+str(H),'-I'+str(R/'firmware'),'-I'+str(SDK/'source'),'-I'+str(SDK/'source/third_party/CMSIS/Core/Include')]
sources=[S/'free_control_main.c',S/'free_control.c',H/'motor_control.c',H/'drill_pwm.c',R/'firmware/demo_core.c',G/'ti_msp_dl_config.c',
 SDK/'source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c']
objects=[]
for f in sources:
    obj=B/(f.stem+'.o');objects.append(obj);run([CC/'bin/tiarmclang.exe','-c',*flags,f,'-o',obj])
run([CC/'bin/tiarmclang.exe',*flags,*objects,'-Wl,-m'+str(B/'motor_probe.map'),'-Wl,-i'+str(SDK/'source'),'-Wl,-i'+str(CC/'lib'),
 '-Wl,--rom_model','-Wl,--warn_sections','-Wl,-l'+str(G/'device_linker.cmd'),'-Wl,-l'+str(G/'device.cmd.genlibs'),'-Wl,-llibc.a','-o',B/'motor_probe.out'])
run([CC/'bin/tiarmhex.exe','--byte','--memwidth=8','--romwidth=8','--intel','-o',B/'motor_probe.hex',B/'motor_probe.out'])
files=[*sources[:-1],S/'free_control.h',H/'motor_control.h',H/'drill_pwm.h',H/'motor.syscfg',Path(__file__),G/'ti_msp_dl_config.h',G/'device.opt',G/'device_linker.cmd',G/'device.cmd.genlibs',B/'motor_probe.out',B/'motor_probe.map',B/'motor_probe.hex']
manifest={'task_id':'DEEPEYE-PHYSICAL-CODE-20261025','task_version':8,'work_id':'variable-motor-software-link-20261103-v1','built_at':stamp,
 'firmware_signature':'0x4d545234','baseline_signature':'0x46524338','baseline_image_sha256':'0377c98ccd6ba1054b6dc1c1bcb2492256585b105bd85a09f3cfc4254f8e2c35',
 'bounds_deg':{'yaw':[-90,90],'pitch':[-45,68]},'saved_reference_words':[0x47524331,1,2088,1961],
 'motor_pin':'PA12','pwm_frequency_hz':20000,'motor_opcode':5,'duty_bound_permille':[0,750],'running_duty_bound_permille':[250,750],'lease_bound_ms':[100,500],
 'boot_motor_duty':0,'gimbal_diagnostics_bytes':172,'motor_diagnostics_bytes':16,
 'normal_pose_protocol':'op1to4 unchanged; motor-onlyop5 never moves gimbal',
 'candidate_only':True,'mcu_flashed':False,'motor_hardware_tested':False,'no_feedback_no_rpm':True,
 'files':[{'path':str(f.relative_to(R)),'sha256':sha(f)} for f in files]}
(E/('manifest-'+stamp+'.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
(E/'latest-build.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print('MTR4 candidate built offline; bootOFF, finite motor-only leases; accepted V8 sources unchanged.')
