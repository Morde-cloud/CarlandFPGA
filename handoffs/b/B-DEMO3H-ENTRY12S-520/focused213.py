"""One synthetic boundary-only check of pinned current A12s reuse. No actor/board."""
from pathlib import Path
import ast,copy,hashlib,importlib,importlib.util,json,sys,types
R=Path(sys.argv[1]);O=Path(sys.argv[2]);O.mkdir(exist_ok=False)
sys.path.insert(0,str(R))
F=importlib.import_module('competition.deepeye.simulation.authority.demo30h_ai_em3_profile_v2')
def module(label,p):
 s=importlib.util.spec_from_file_location(label,p);m=importlib.util.module_from_spec(s);sys.modules[label]=m;s.loader.exec_module(m);return m
rows=[]
def check(n,c):
 assert c,n
 rows.append(dict(name=n,passed=True))
def refuses(n,fn):
 try:fn()
 except (ValueError,TypeError):check(n,True)
 else:raise AssertionError(n+' accepted')
p12=F.selected_profile(12_000_000_000,navigation_profile=F.NAV_ENTRY_C0_12S_V3)
check('new12s selector and real hardware prospective3s',p12.max_source_age_ns==12_000_000_000 and p12.prospective_command_max_ns==3_000_000_000)
refuses('new12s +1ns factory',lambda:F.selected_profile(12_000_000_001,navigation_profile=F.NAV_ENTRY_C0_12S_V3))
for name,nav,limit in [('strict5',None,5_000_000_000),('navfast5',F.NAV_FAST_V1,5_000_000_000),('entry8',F.NAV_ENTRY_C0_V1,8_000_000_000)]:
 check(name+' factory bound',F.selected_profile(limit,navigation_profile=nav).max_source_age_ns==limit)
 refuses(name+' +1ns factory',lambda nav=nav,limit=limit:F.selected_profile(limit+1,navigation_profile=nav))
# Extract only the exact policy class/guards, not the original authority runtime.
name='competition.deepeye.simulation.authority.g05_csr_channels_v1';g=types.ModuleType(name);g.__package__=name.rsplit('.',1)[0];sys.modules[name]=g
tree=ast.parse((R/'competition/deepeye/simulation/authority/g05_csr_channels_v1.py').read_bytes());nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ('_need','_uint','G05CsrPolicy')]
exec('from dataclasses import dataclass\n_MAX_NS=(1<<63)-1',g.__dict__);exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact_policy_ast','exec'),g.__dict__)
g.G05CsrPolicy(12_000_000_000,12_000_000_000,0,0,p12).check();check('exact policy12s source and health',True)
refuses('policy12s+1 health',lambda:g.G05CsrPolicy(12_000_000_000,12_000_000_001,0,0,p12).check())
refuses('non-descriptor policy remains5s',lambda:g.G05CsrPolicy(5_000_000_001,1,0,0).check())
V=importlib.import_module(F.__name__+'.verifier_c0_demo_v5')
pose=dict(position_m=[0,0,0],orientation_xyzw=[0,0,0,1]);obs=dict(sample_id='a'*64,counts=[3099,2006,2084,None],quality=7,missing_feature_mask=8,adc_qpc_ns=1_000_000_000,em_qpc_ns=1_000_000_000,adc_pose=copy.deepcopy(pose),em_pose=copy.deepcopy(pose))
public=dict(schema_version=1,projection_id='g05_csr_em3_demo_view_v2',enabled=True,now_qpc_ns=13_000_000_000,pose=pose,goal_m=[0,0,10],observation=obs,history=[],executed_actions=[],engineering_profile=dict(V.ENTRY_C0_ENGINEERING_PROFILE))
report=V.quality_report(public);check('verifier12s exact admitted without100ms quality',report['demo_age_accepted'] and report['original100ms_quality'] is False and report['target100ms_met'] is False)
fresh=copy.deepcopy(public);fresh['observation'].update(quality=15,missing_feature_mask=0,counts=[3099,2006,2084,0]);fresh['now_qpc_ns']=1_100_000_000
check('original100ms exact quality bound',V.quality_report(fresh)['target100ms_met'] is True)
check('original100ms +1ns remains false',V.quality_report(fresh,observed_now_qpc_ns=1_100_000_001)['target100ms_met'] is False)
check('verifier +1ns expires',not V.quality_report(public,observed_now_qpc_ns=13_000_000_001)['demo_age_accepted'])
refuses('strict verifier cannot select12s',lambda:V.selected_verifier(12_000_000_000))
check('fixed age normalization5000 and originalquality100ms',V.AGE_NORMALIZATION_MS==5000 and V.ORIGINAL_QUALITY_AGE_NS==100_000_000)
def request(core,age,engineering=None):
 binding=dict(run_id='synthetic213',build_sha256='a'*64,boot_sha256='b'*64,session=1,config_epoch=1,clock_domain='synthetic',source_id=4,source_mode='twin_fixture',profile_id=core.PROFILE,producer_sha256=core.PRODUCER_SHA256,topology_id=1)
 sample=dict(binding=copy.deepcopy(binding),sample_id='sample1',trigger_id='trigger1',sequence=1,board_frame_sha256='c'*64,source_record_sha256='d'*64,adc_tick_ms=1000,em_tick_ms=1000,em_origin_sample_id='sample1',counts=[3099,2006,2084,None],quality=7,missing_feature_mask=8,adc_pose=copy.deepcopy(pose),em_pose=copy.deepcopy(pose),cause_action_id=None)
 return dict(schema_version=1,enabled=True,binding=binding,now_tick_ms=1000+age,pose=copy.deepcopy(pose),goal_m=[0,0,10],observation=sample,history=[],executed_actions=[],engineering_profile=copy.deepcopy(engineering or core.ENTRY_C0_ENGINEERING_PROFILE))
C=module('synthetic_core213',R/'competition/deepeye/ai_pc/demo30h_owned_em3_package_v5/em3_core.py')
a=C.recommend(request(C,12000));check('core12s boundary not expired',a['reason']!='original_sample_expired')
check('core +1ms STOP',C.recommend(request(C,12001))['reason']=='original_sample_expired')
check('missingC3 stays null with explicit penalty',a['observation']['counts'][3] is None and a['missing_feature_mask']==8 and not a['c3_observed'] and a['risk']>=.25)
q=request(C,0);q['observation'].update(quality=0x1000,missing_feature_mask=15,counts=[None]*4,em_tick_ms=None,em_origin_sample_id=None,em_pose=None);check('fault STOP',C.recommend(q)['reason']=='invalid_faulted_or_saturated')
q=request(C,0);q['observation'].update(quality=15,missing_feature_mask=0,counts=[3099,2006,2084,2000]);check('contact STOP',C.recommend(q)['reason']=='contact_vibration_risk')
for version,cap in [(3,8000),(2,5000)]:
 c=module('legacy_core213_'+str(version),R/f'competition/deepeye/ai_pc/demo30h_owned_em3_package_v{version}/em3_core.py');ep=getattr(c,'ENTRY_C0_ENGINEERING_PROFILE',None) if version==3 else c.STRICT_ENGINEERING_PROFILE
 check('oldcore'+str(version)+' bound not age-expired',c.recommend(request(c,cap,ep))['reason']!='original_sample_expired')
 check('oldcore'+str(version)+' +1ms STOP',c.recommend(request(c,cap+1,ep))['reason']=='original_sample_expired')
pins=json.loads((R/'competition/deepeye/ai_pc/demo30h_owned_em3_package_v5/package-manifest.json').read_bytes())
for n,h in pins['files'].items():check('package5 hash '+n,hashlib.sha256((R/'competition/deepeye/ai_pc/demo30h_owned_em3_package_v5'/n).read_bytes()).hexdigest()==h)
result=dict(status='PASS',cases=len(rows),checks=rows,A_tested_source='cde27d48201fa698cb475ca81ef61b6a2e0406c9',scope='Synthetic pure core/factory/verifier plus AST-extracted original policy guard; no original lifecycle, CPU9/actor16 qualification, hardware or acceptance',actual_AI_or_motion_claim=False)
(O/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
