"""Synthetic-only R04 ADC evaluator; no I/O, callbacks, hardware, commands, or physical measurement."""
from hashlib import sha256
import json

SCHEMA = "deepeye.r04_adc_pair.v1"
MODE = "SYNTHETIC_FIXTURE"
MAX_JSON_BYTES, MAX_RECORDS = 65536, 16
MAX_U63 = (1 << 63) - 1
TOP = ("schema", "mode", "calibration", "digital_receipt", "baseline_before", "after", "now_qpc_ns")
CTX = ("tag", "epoch", "boot_id", "source_id", "clock_id")
CAL = ("calibration_id", "full_scale_code", "a0_offset_code", "a3_offset_code", "qpc_hz", "clock_id")
RECEIPT = ("spi_complete", "digital_complete_qpc", "context")
RECORD = ("sample_id", "acquisition_qpc", "source_qpc", "context", "channel_indices", "channels", "quality", "quality_eligible")

class _Refused(Exception): code = "REFUSED"
class _Unavailable(Exception): code = "UNAVAILABLE"

def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _bad(_token):
    raise _Refused("FLOAT_OR_NONFINITE_NUMBER")

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out: raise _Refused("DUPLICATE_JSON_KEY")
        out[key] = value
    return out

def _obj(value, keys, where):
    if type(value) is not dict or set(value) != set(keys):
        raise _Refused(where + ":EXACT_OBJECT_SCHEMA_REQUIRED")
    return value

def _arr(value, limit, where):
    if type(value) is not list or len(value) > limit:
        raise _Refused(where + ":BOUNDED_LIST_REQUIRED")
    return value

def _u(value, limit, where):
    if type(value) is not int or value < 0 or value > limit:
        raise _Refused(where + ":UNSIGNED_INTEGER_REQUIRED")
    return value

def _ctx(value):
    if type(value) is not dict or not set(CTX).issubset(value) or len(value) > 32:
        raise _Refused("context:COMPLETE_BOUNDED_OBJECT_REQUIRED")
    context = value
    for key in ("tag", "epoch"): _u(context[key], MAX_U63, "context." + key)
    for key in ("boot_id", "source_id", "clock_id"):
        _text(context[key], "context." + key)
    budget = [512]
    def plain(x, depth=0):
        budget[0] -= 1
        if depth > 8 or budget[0] < 0: raise _Refused("context:RESOURCE_BOUND")
        if type(x) is dict:
            if len(x) > 32: raise _Refused("context:OBJECT_BOUND")
            for k, v in x.items(): _text(k, "context key"); plain(v, depth+1)
        elif type(x) is list:
            if len(x) > 32: raise _Refused("context:ARRAY_BOUND")
            for v in x: plain(v, depth+1)
        elif type(x) is str: _text(x, "context text")
        elif type(x) is int: _u(x, MAX_U63, "context integer")
        elif type(x) not in (bool, type(None)): raise _Refused("context:PLAIN_JSON_REQUIRED")
    plain(context)
    return context

def _text(value, where):
    if type(value) is not str or not 1 <= len(value) <= 1024: raise _Refused(where+":BOUNDED_ORIGINAL_TEXT_REQUIRED")
    try: value.encode("utf-8")
    except UnicodeError as exc: raise _Refused(where+":INVALID_UNICODE") from exc
    return value

def _cal(value):
    c = _obj(value, CAL, "calibration")
    ident = c["calibration_id"]
    if type(ident) is not str or not 0 < len(ident) <= 128: raise _Refused("calibration_id:BOUNDED_STRING_REQUIRED")
    try: ident.encode("utf-8")
    except UnicodeError as exc: raise _Refused("calibration_id:INVALID_UNICODE") from exc
    fs = _u(c["full_scale_code"], 65535, "full_scale_code")
    if fs < 1: raise _Refused("full_scale_code:POSITIVE_REQUIRED")
    for key in ("a0_offset_code", "a3_offset_code"):
        if type(c[key]) is not int or not -65535 <= c[key] <= 65535:
            raise _Refused(key + ":SIGNED_INTEGER_REQUIRED")
    hz = _u(c["qpc_hz"], MAX_U63, "qpc_hz")
    if hz != 1_000_000_000: raise _Refused("qpc_hz:ORIGINAL_NANOSECOND_CLOCK_REQUIRED")
    return ident, fs, c["a0_offset_code"], c["a3_offset_code"], hz, _text(c["clock_id"], "calibration.clock_id")

def _receipt(value):
    r = _obj(value, RECEIPT, "digital_receipt")
    if type(r["spi_complete"]) is not bool: raise _Refused("spi_complete:BOOLEAN_REQUIRED")
    return r["spi_complete"], _u(r["digital_complete_qpc"], MAX_U63, "digital_complete_qpc"), _ctx(r["context"])

def _record(value, where):
    r = _obj(value, RECORD, where)
    _u(r["sample_id"], MAX_U63, where + ".sample_id")
    _u(r["acquisition_qpc"], MAX_U63, where + ".acquisition_qpc")
    _u(r["source_qpc"], MAX_U63, where + ".source_qpc")
    _ctx(r["context"])
    indices = _arr(r["channel_indices"], 4, where + ".channel_indices")
    if any(type(i) is not int for i in indices) or indices != [0, 1, 2, 3]:
        raise _Refused(where + ":CHANNEL_INDICES_0_TO_3_REQUIRED")
    channels = _arr(r["channels"], 4, where + ".channels")
    if len(channels) != 4: raise _Refused(where + ":FOUR_RAW_CHANNELS_REQUIRED")
    for channel in channels: _u(channel, 65535, where + ".channel")
    _u(r["quality"], 255, where + ".quality")
    if type(r["quality_eligible"]) is not bool: raise _Refused(where+":EXPLICIT_QUALITY_ELIGIBILITY_REQUIRED")
    return r

def _ledger(before, after):
    entries, chunks = [], []
    for phase, records in (("baseline_before", before), ("after", after)):
        for record in records:
            raw = _canon(record)
            entries.append({"phase": phase, "sample_id": record["sample_id"], "canonical_json": raw,
                            "canonical_length_bytes": len(raw.encode("ascii")),
                            "sha256": sha256(raw.encode("ascii")).hexdigest()})
            chunks.append(phase + "\n" + raw)
    digest = sha256("\n".join(chunks).encode("ascii")).hexdigest() if chunks else None
    return entries, digest

def _out(status, reason, ledger=None, ledger_sha=None, receipt_sha=None, **extra):
    result = {"status": status, "mode": MODE, "synthetic": True, "reason": reason,
              "input_authentication": "not_established", "r04_status": "UNSATISFIED",
              "ratio_numerator": None, "ratio_denominator": None,
              "baseline_ratio_numerator": None, "baseline_ratio_denominator": None,
              "measured_gain_actual": None, "physical_acceptance": False,
              "adc_voltage_measured": False, "real_adc_or_calibration_available": False,
              "eight_level_measurement_available": False, "five_percent_acceptance": False,
              "settling_validated": False, "commands_emitted": False,
              "record_ledger": ledger or [], "ledger_sha256": ledger_sha, "receipt_sha256": receipt_sha}
    result.update(extra)
    return result

def production_entry():
    result = _out("INPUT_UNAVAILABLE", "ROOT_BOOT_CALIBRATION_ADC_AND_CALLBACK_NOT_PROVIDED")
    result.update({"mode": "PRODUCTION", "synthetic": False})
    return result

def _parse(text):
    if type(text) is not str: raise _Refused("INPUT_NOT_PLAIN_JSON_TEXT")
    try:
        if len(text.encode("utf-8")) > MAX_JSON_BYTES: raise _Refused("INPUT_BYTES_EXCEEDED")
        return json.loads(text, object_pairs_hook=_pairs, parse_float=_bad, parse_constant=_bad)
    except _Refused:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise _Refused("INVALID_JSON") from exc

def _measure(record, fs, a0_offset, a3_offset, target_window=False):
    if not record["quality_eligible"]: raise _Unavailable("QUALITY_INELIGIBLE")
    raw0, raw3 = record["channels"][0], record["channels"][3]
    if raw0 >= fs or raw3 >= fs: raise _Unavailable("RAW_SATURATED_AT_FIXTURE_FULL_SCALE")
    a0, a3 = raw0 - a0_offset, raw3 - a3_offset
    if a3 <= 0: raise _Unavailable("A3_DENOMINATOR_NONPOSITIVE")
    if a0 <= 0: raise _Unavailable("A0_NONPOSITIVE")
    if target_window and not (20 * fs <= 100 * raw0 <= 80 * fs):
        raise _Unavailable("A0_AFTER_OUTSIDE_20_80_PERCENT_FIXTURE_RANGE")
    return a0, a3

def _evaluate(document):
    top = _obj(document, TOP, "root")
    if top["schema"] != SCHEMA or top["mode"] != MODE:
        raise _Refused("SCHEMA_OR_EXPLICIT_SYNTHETIC_MODE_REQUIRED")
    before_raw = _arr(top["baseline_before"], MAX_RECORDS, "baseline_before")
    after_raw = _arr(top["after"], MAX_RECORDS, "after")
    if len(before_raw) + len(after_raw) > MAX_RECORDS: raise _Refused("RECORD_CAPACITY_EXCEEDED")
    cal = None if top["calibration"] is None else _cal(top["calibration"])
    receipt = None if top["digital_receipt"] is None else _receipt(top["digital_receipt"])
    before = [_record(x, "baseline_before") for x in before_raw]
    after = [_record(x, "after") for x in after_raw]
    now = None if top["now_qpc_ns"] is None else _u(top["now_qpc_ns"], MAX_U63, "now_qpc_ns")
    ledger, ledger_sha = _ledger(before, after)
    receipt_sha = sha256(_canon(top["digital_receipt"]).encode("ascii")).hexdigest() if receipt is not None else None
    all_records = before + after
    context = receipt[2] if receipt is not None else (all_records[0]["context"] if all_records else None)
    ids = set()
    for record in all_records:
        if record["sample_id"] in ids: raise _Refused("DUPLICATE_SAMPLE_ID")
        ids.add(record["sample_id"])
        if record["context"] != context: raise _Refused("TRANSACTION_CONTEXT_MISMATCH")
        if record["source_qpc"] > record["acquisition_qpc"]: raise _Refused("SOURCE_QPC_AFTER_ACQUISITION_QPC")
        if now is not None and record["acquisition_qpc"] > now: raise _Refused("ACQUISITION_AFTER_ORIGINAL_NOW")
    for phase, records in (("baseline_before", before), ("after", after)):
        prev_acq = prev_source = None
        for record in records:
            if prev_acq is not None and (record["acquisition_qpc"] <= prev_acq or record["source_qpc"] < prev_source):
                raise _Refused("TIMESTAMP_REGRESSION_OR_WRAP")
            prev_acq, prev_source = record["acquisition_qpc"], record["source_qpc"]
            if receipt is not None and phase == "baseline_before" and (prev_acq >= receipt[1] or prev_source >= receipt[1]):
                raise _Refused("BEFORE_NOT_BEFORE_DIGITAL_COMPLETE")
            if receipt is not None and phase == "after" and (prev_acq <= receipt[1] or prev_source <= receipt[1]):
                raise _Refused("AFTER_NOT_AFTER_DIGITAL_COMPLETE")
    if before and after and before[-1]["acquisition_qpc"] >= after[0]["acquisition_qpc"]: raise _Refused("BASELINE_AFTER_ORDER")
    if cal is not None and context is not None and cal[5] != context["clock_id"]: raise _Refused("CALIBRATION_CLOCK_MISMATCH")
    if not before or not after:
        return _out("UNAVAILABLE", "BOTH_SAMPLE_SETS_REQUIRED", ledger, ledger_sha, receipt_sha)
    if receipt is None:
        return _out("UNAVAILABLE", "DIGITAL_RECEIPT_UNAVAILABLE", ledger, ledger_sha, receipt_sha)
    complete, digital_qpc, context = receipt
    if not complete:
        return _out("UNAVAILABLE", "DIGITAL_SPI_NOT_COMPLETE", ledger, ledger_sha, receipt_sha)
    if cal is None:
        return _out("UNAVAILABLE", "CALIBRATION_UNAVAILABLE", ledger, ledger_sha, receipt_sha)
    if now is None:
        return _out("UNAVAILABLE", "ORIGINAL_NOW_QPC_UNAVAILABLE", ledger, ledger_sha, receipt_sha)
    calibration_id, fs, a0_offset, a3_offset, qpc_hz, clock_id = cal
    if clock_id != context["clock_id"]: raise _Refused("CALIBRATION_CLOCK_MISMATCH")
    freshness_limit = qpc_hz // 10
    for record in before + after:
        if now - record["source_qpc"] > freshness_limit:
            return _out("UNAVAILABLE", "SOURCE_STALE_BEYOND_100MS", ledger, ledger_sha, receipt_sha)
    try:
        baseline_values = [_measure(x, fs, a0_offset, a3_offset) for x in before]
        after_values = [_measure(x, fs, a0_offset, a3_offset, target_window=True) for x in after]
    except _Unavailable as exc:
        return _out("UNAVAILABLE", str(exc), ledger, ledger_sha, receipt_sha)
    baseline_numerator, baseline_denominator = baseline_values[-1]
    numerator, denominator = after_values[0]
    return _out("SYNTHETIC_RATIO_AVAILABLE", "EXACT_INTEGER_RATIO_FROM_EXPLICIT_FIXTURE",
                ledger, ledger_sha, receipt_sha, ratio_numerator=numerator,
                ratio_denominator=denominator, baseline_ratio_numerator=baseline_numerator,
                baseline_ratio_denominator=baseline_denominator,
                baseline_selected_sample_id=before[-1]["sample_id"],
                after_selected_sample_id=after[0]["sample_id"],
                selection_rule="last_baseline_before_and_first_after",
                sample_count_total=len(before) + len(after), digital_complete_qpc=digital_qpc,
                qpc_hz=qpc_hz, calibration_id=calibration_id, fixture_full_scale_code=fs,
                range_20_80_relative_to_fixture_full_scale=True,
                baseline_independent=True, baseline_command_gain_used=False,
                synthetic_structural_consistency=True,
                ratio_scope="synthetic_corrected_code_ratio_not_analog_gain",
                a0_after_raw=after[0]["channels"][0], a3_after_raw=after[0]["channels"][3],
                a0_after_corrected=numerator, a3_after_corrected=denominator)

def evaluate_synthetic_fixture(payload_text):
    try:
        document = _parse(payload_text)
        result = _evaluate(document)
        original_bytes = _canon(document).encode("ascii")
        result.update(input_canonical_json=original_bytes.decode("ascii"), input_canonical_length_bytes=len(original_bytes),
                      input_canonical_sha256=sha256(original_bytes).hexdigest(),
                      record_ledger_canonical_bytes=sum(r["canonical_length_bytes"] for r in result["record_ledger"]))
        return result
    except _Refused as exc:
        return _out("REFUSED", str(exc))
    except _Unavailable as exc:
        return _out("UNAVAILABLE", str(exc))
