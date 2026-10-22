"""Proposed main-owned classifier repair, evaluated before taking author ownership.

Inserted as ordinary definitions in the scoped runner only after terminal receipt.
Uses that runner's parse_stats, _identity_reasons, _result and constants.
"""

def _lines(text):
    result=[]
    for raw in text.splitlines():
        s=raw.strip()
        result.append(s[2:] if s.startswith('# ') else s)
    return result

def _strict_diagnostics(stdout,stderr,own=None):
    reasons=[];summaries=[];fatals=[]
    for origin,text in [('stdout',stdout),('stderr',stderr)]:
        for s in _lines(text):
            summary=re.fullmatch(r'Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)',s,flags=re.ASCII)
            if summary:
                if origin!='stdout':reasons.append('diagnostic summary on stderr')
                summaries.append(tuple(map(int,summary.groups())));continue
            if own and s=='** Fatal: '+own:
                if origin!='stdout':reasons.append('own fatal on stderr')
                fatals.append(s);continue
            # Structured rows are validated separately; errors=0 is a stats key.
            if s.startswith('SAMPLE_SCAN_STATS '):continue
            if re.search(r'\b(?:error|errors|warning|warnings|fatal)\b',s,flags=re.I|re.ASCII):reasons.append('unexpected diagnostic: '+s)
    if summaries!=[(int(own is not None),0)]:reasons.append('nonunique/inconsistent error-warning summary')
    if own and len(fatals)!=1:reasons.append('own fatal not exact and unique')
    return reasons

def _structured_rows(stdout,stderr):
    rows={'SAMPLE_SCAN_PASS':[],'SAMPLE_SCAN_STATS':[],'SAMPLE_SCAN_MISMATCH':[],'GUARD_CONTROL_ALIVE':[]};bad=[]
    for origin,text in [('stdout',stdout),('stderr',stderr)]:
        for line in _lines(text):
            for key in rows:
                if key not in line:continue
                if origin!='stdout':bad.append('structured marker on stderr')
                exact=line==key if key in ['SAMPLE_SCAN_PASS','GUARD_CONTROL_ALIVE'] else line.startswith(key+' ')
                if not exact:bad.append('malformed structured marker: '+line)
                else:rows[key].append(line)
    return rows,bad

def classify_compile(vlog_exit,stdout,stderr):
    reasons=_strict_diagnostics(stdout,stderr)
    if type(vlog_exit) is not int or vlog_exit!=0:reasons.append('compile exit must be0')
    return _result(not reasons,reasons)

def classify_simulation_output(vsim_exit,stdout,stderr,expected_case,expected_stats,*,check_identities=True):
    rows,reasons=_structured_rows(stdout,stderr);reasons+=_strict_diagnostics(stdout,stderr)
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('simulation exit must be0')
    if len(rows['SAMPLE_SCAN_PASS'])!=1:reasons.append('pass marker not unique')
    if len(rows['SAMPLE_SCAN_STATS'])!=1:reasons.append('stats not unique')
    if rows['SAMPLE_SCAN_MISMATCH'] or rows['GUARD_CONTROL_ALIVE']:reasons.append('unexpected failure/guard marker')
    stats=None
    try:
        stats=parse_stats(stdout)
        if stats['case']!=expected_case:reasons.append('wrong case')
        if stats['errors']!=0 or stats['checks']<=0 or stats['windows']<=0:reasons.append('failed/empty testbench')
        for key,value in expected_stats.items():
            if stats.get(key)!=value:reasons.append('inconsistent stats '+key)
        if check_identities:reasons+=_identity_reasons(stats)
    except (ValueError,KeyError,TypeError) as exc:reasons.append('invalid stats: '+str(exc))
    return _result(not reasons,reasons,stats=stats)

def classify_guard_output(vlog_exit,vlog_stdout,vlog_stderr,vsim_exit,stdout,stderr,expected_family,expected_message):
    reasons=classify_compile(vlog_exit,vlog_stdout,vlog_stderr)['reasons'];rows,bad=_structured_rows(stdout,stderr);reasons+=bad
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('guard process must exit0 on verified run-all/quit-f route')
    healthy=expected_family=='HEALTHY'
    if healthy:
        reasons+=_strict_diagnostics(stdout,stderr)
        if len(rows['GUARD_CONTROL_ALIVE'])!=1:reasons.append('healthy control marker not unique')
    else:
        if expected_message!=FATAL_MESSAGES.get(expected_family) or not expected_message:reasons.append('unknown fatal contract')
        reasons+=_strict_diagnostics(stdout,stderr,expected_message)
        if rows['GUARD_CONTROL_ALIVE']:reasons.append('guard body unexpectedly ran')
    if rows['SAMPLE_SCAN_PASS'] or rows['SAMPLE_SCAN_STATS'] or rows['SAMPLE_SCAN_MISMATCH']:reasons.append('unexpected normal/mismatch marker in guard')
    return _result(not reasons,reasons,classification='guard_healthy' if healthy else 'dut_guard_rejected')

def classify_mutant_output(vlog_exit,vlog_stdout,vlog_stderr,vsim_exit,stdout,stderr,expected_case,required_mismatches):
    reasons=classify_compile(vlog_exit,vlog_stdout,vlog_stderr)['reasons'];rows,bad=_structured_rows(stdout,stderr);reasons+=bad
    reasons+=_strict_diagnostics(stdout,stderr,'tb_sample_scan_capture: case failed')
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('mutant process must complete verified route exit0')
    if rows['SAMPLE_SCAN_PASS'] or rows['GUARD_CONTROL_ALIVE']:reasons.append('unexpected positive marker')
    if len(rows['SAMPLE_SCAN_STATS'])!=1:reasons.append('mutant stats not unique')
    stats=None;observed=[]
    try:
        stats=parse_stats(stdout)
        if stats['case']!=expected_case or stats['errors']<=0 or stats['checks']<=0 or stats['windows']<=0:reasons.append('invalid mutant stats')
        if stats['errors']!=len(rows['SAMPLE_SCAN_MISMATCH']):reasons.append('mismatch count differs from errors')
    except (ValueError,KeyError,TypeError) as exc:reasons.append('invalid mutant stats: '+str(exc))
    for s in rows['SAMPLE_SCAN_MISMATCH']:
        m=re.fullmatch(r'SAMPLE_SCAN_MISMATCH field=([A-Za-z_][A-Za-z0-9_]*) expected=([0-9]+) actual=([0-9]+)',s,flags=re.ASCII)
        if not m:reasons.append('nonnumeric/malformed mutant mismatch');continue
        field,e,a=m.groups();e=int(e);a=int(a)
        if e==a:reasons.append('equal values do not prove mismatch')
        observed.append((field,e,a))
    if not required_mismatches or any(tuple(x) not in observed for x in required_mismatches):reasons.append('required concrete mismatch absent')
    return _result(not reasons,reasons,stats=stats,mismatches=observed,classification='mutant_rejected')

def aggregate_results(selected_names,results):
    reasons=[]
    if not selected_names or len(set(selected_names))!=len(selected_names):reasons.append('empty or duplicate selection')
    missing=[n for n in selected_names if n not in results];unexpected=[n for n in results if n not in selected_names]
    failed=[n for n in selected_names if n in results and results[n].get('ok') is not True]
    if missing or unexpected or failed:reasons.append('missing/extra/nonpassing selected results')
    return _result(not reasons,reasons,selected=selected_names,missing=missing,unexpected=unexpected,failed=failed)
