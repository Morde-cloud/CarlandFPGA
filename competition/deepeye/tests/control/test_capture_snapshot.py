'''Unit tests for the candidate control capture/snapshot foundation (candidate only).

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-CONTROL-SNAPSHOT-FOUNDATION-20261015-01-v1
Correction: B-CONTROL-INGRESS-STOP-CORRECTION-20261016-02-v1

Run from the worktree root:
  python -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_capture_snapshot.py -v

These are design-time software checks for the B-side candidate control model.
They model no RTL, no CDC/RDC, no AXI/WSTRB behavior and no clock-domain
details; they freeze no public register bits and make no board, timing,
ABI or acceptance claim. No test here can make hardware ENABLE eligible.
'''

import itertools
import json
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'control'))

import capture_snapshot_reference as ctl  # noqa: E402

VECTORS_PATH = _DEEPEYE / 'golden' / 'control' / 'snapshot_vectors.json'
INVENTORY_PATH = _DEEPEYE / 'golden' / 'control' / 'register_candidate_inventory.json'

with open(VECTORS_PATH, encoding='utf-8') as _handle:
    VECTORS = json.load(_handle)
with open(INVENTORY_PATH, encoding='utf-8') as _handle:
    INVENTORY = json.load(_handle)

OFFSETS = (0x00, 0x04, 0x08, 0x0c, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24,
           0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c, 0x40, 0x44, 0x48, 0x4c,
           0x50, 0x54, 0x58, 0x5c, 0x60, 0x64, 0x68, 0x6c, 0x70)

NAMES = ('identification', 'abi_version', 'control', 'status',
         'shadow_configuration', 'apply_request', 'sample_rate', 'error_bound',
         'profile', 'queue_status', 'overflow_merge', 'reserved', 'applied_yaw',
         'applied_speed', 'applied_request', 'session', 'sample_tick_word0',
         'sample_tick_word1', 'capture_period0', 'capture_period1',
         'capture_sequence', 'capture_quality', 'gain', 'measured_ratio',
         'applied_pitch', 'pitch_capture_period', 'speed_capture_period',
         'motion_profile_id', 'last_observed_sequence')


def decode_bruteforce(channel, high_ticks):
    '''Independent nearest-legal decode by exhaustive scan (test-side oracle).'''
    if channel in ('yaw', 'pitch'):
        low, high, step, base = -15000, 15000, 16, 10000
    else:
        low, high, step, base = 0, 20, 1000, 50000
    best_rank = None
    best = None
    for code in range(low, high + 1):
        expected = base + step * (code - low)
        rank = (abs(high_ticks - expected), code)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = (code, expected)
    return best[0], best[1], high_ticks - best[1]


def run_vector_op(model, registers, reads, step):
    '''Test-side vector interpreter, written independently of the module CLI.'''
    op = step['op']
    if op == 'begin_session':
        model.begin_session(step['session'])
        return None
    if op == 'begin_epoch':
        model.begin_epoch(step['control_epoch'])
        return None
    if op == 'apply_request':
        model.apply_request(step['request_seq'])
        return None
    if op == 'submit':
        evidence = ctl.ChannelEvidence.create(
            channel=step['channel'], session=step['session'],
            control_epoch=step['control_epoch'], request_seq=step['request_seq'],
            batch_seq=step['batch_seq'], period_ticks=step['period_ticks'],
            high_ticks=step['high_ticks'])
        return model.submit_evidence(evidence)
    if op == 'publish':
        return list(model.publish_snapshot().batch_key.as_tuple())
    if op == 'eligibility':
        return model.eligibility
    if op == 'latest_published':
        snapshot = model.latest_published()
        return None if snapshot is None else list(snapshot.batch_key.as_tuple())
    if op == 'pending_channels':
        return list(model.pending_channels)
    if op == 'stop':
        model.stop(reason=step.get('reason', 'vector-stop'))
        return None
    if op == 'reset':
        model.reset(reason=step.get('reason', 'vector-reset'), scope=step.get('scope', 'fixture'))
        return None
    if op == 'set_fault':
        model.set_fault(step['bit'])
        return None
    if op == 'clear_fault':
        model.clear_fault()
        return None
    if op == 'enable':
        model.enable()
        return None
    if op == 'frozen_read':
        read = model.begin_frozen_read()
        reads[step['label']] = read
        return {'had_snapshot': read.words is not None}
    if op == 'frozen_coherent':
        return reads[step['label']].coherent
    if op == 'frozen_words':
        read = reads[step['label']]
        return None if read.words is None else list(read.words)
    if op == 'validate_words':
        return model.words_consistent(step['words'])
    if op == 'shadow_write':
        registers.write(step['offset'], step['value'],
                        write_strobes=step.get('write_strobes', 0xF))
        return None
    if op == 'shadow_read':
        return registers.read(step['offset'])
    if op == 'reg_count':
        return len(registers.addresses())
    if op == 'stopped':
        return model.stopped
    if op == 'enabled':
        return model.enabled
    raise AssertionError('unknown vector op: ' + repr(op))


def run_vector_scenario(scenario):
    '''Execute one scenario with the test-side interpreter.'''
    model = ctl.CaptureSnapshotModel()
    registers = ctl.CandidateRegisterFile()
    reads = {}
    outcomes = []
    for step in scenario['steps']:
        try:
            outcomes.append({'error': None, 'outcome': 'ok',
                             'value': run_vector_op(model, registers, reads, step)})
        except ctl.ControlCandidateError as exc:
            outcomes.append({'error': type(exc).__name__, 'outcome': 'error', 'value': None})
    return outcomes


class VectorDocumentTests(unittest.TestCase):
    '''The emitted artifacts must match the pinned sources and claims rules.'''

    def test_inventory_offsets_and_names_exact(self):
        registers = INVENTORY['registers']
        self.assertEqual(len(registers), 29)
        self.assertEqual(tuple(item['offset'] for item in registers), OFFSETS)
        self.assertEqual(tuple(item['name'] for item in registers), NAMES)
        self.assertTrue(all(item['width_bits'] == 32 for item in registers))

    def test_inventory_unknown_fields_null_with_reason(self):
        for item in INVENTORY['registers']:
            self.assertIsNone(item['bitfields'], item['offset_hex'])
            self.assertIsNone(item['reset_value'], item['offset_hex'])
            self.assertTrue(item['unknown_reason'], item['offset_hex'])
            if item['offset'] == ctl.RESERVED_OFFSET:
                self.assertEqual(item['access'], 'no_access')
            else:
                self.assertIsNone(item['access'], item['offset_hex'])

    def test_inventory_reserved_no_access(self):
        reserved = [item for item in INVENTORY['registers']
                    if item['offset'] == ctl.RESERVED_OFFSET]
        self.assertEqual(len(reserved), 1)
        self.assertEqual(reserved[0]['name'], 'reserved')
        self.assertEqual(reserved[0]['access'], 'no_access')
        self.assertEqual(reserved[0]['implementation_status'], 'no_access')

    def test_inventory_source_hashes_match_pinned_inputs(self):
        crosswalk = INVENTORY['crosswalk']
        self.assertEqual(crosswalk['source_sha256'],
                         ctl.SOURCE_SHA256['inputs/a/competition/deepeye/docs/registers.csv'])
        self.assertEqual(crosswalk['source_commit'], ctl.A_PINNED_COMMIT)
        self.assertEqual(INVENTORY['input_manifest_sha256'], ctl.INPUT_MANIFEST_SHA256)
        self.assertEqual(INVENTORY['contract']['requirements_sha256'],
                         ctl.REQUIREMENTS_SHA256)
        self.assertEqual(INVENTORY['contract']['requirements_ids'], list(ctl.REQUIREMENTS_IDS))

    def test_inventory_missing_dependencies_explicit(self):
        dependencies = INVENTORY['missing_dependencies']
        self.assertGreaterEqual(len(dependencies), 7)
        joined = ' '.join(dependencies).lower()
        for needle in ('wstrb', 'sample-tick', 'cdc', 'capture diagnostic',
                       'hwh', 'calibrated'):
            self.assertIn(needle, joined)

    def test_inventory_no_enable_or_stage_claims(self):
        self.assertFalse(INVENTORY['hardware_enable_eligible'])
        for stage, status in INVENTORY['stages'].items():
            self.assertEqual(status, 'not_run', stage)

    def test_vectors_document_flags(self):
        self.assertTrue(VECTORS['candidate_only'])
        self.assertFalse(VECTORS['hardware_enable_eligible'])
        self.assertEqual(VECTORS['work_id'], ctl.WORK_ID)
        self.assertEqual(VECTORS['correction_work_id'], ctl.CORRECTION_WORK_ID)
        self.assertEqual(VECTORS['contract']['requirements_sha256'], ctl.REQUIREMENTS_SHA256)
        self.assertTrue(VECTORS['negative_scenario_ids'])
        for stage, status in VECTORS['stages'].items():
            self.assertEqual(status, 'not_run', stage)
        for identifier in ('stop-late-capture-refused', 'epoch-retires-request',
                           'frozen-new-cycle-revokes-freshness'):
            self.assertIn(identifier, VECTORS['negative_scenario_ids'])

    def test_scenario_vectors_with_independent_executor(self):
        for scenario in VECTORS['capture_scenarios']:
            outcomes = run_vector_scenario(scenario)
            for index, step in enumerate(scenario['steps']):
                expect = step.get('expect')
                if expect is None:
                    continue
                actual = outcomes[index]
                trace = {
                    'expected': expect,
                    'actual': actual,
                    'scenario': scenario['id'],
                    'step_index': index,
                    'step': step,
                }
                self.assertEqual(actual['outcome'], expect['outcome'],
                                 json.dumps(trace, sort_keys=True))
                if expect['outcome'] == 'error':
                    self.assertEqual(actual['error'], expect.get('error'),
                                     json.dumps(trace, sort_keys=True))
                elif 'value' in expect:
                    self.assertEqual(actual['value'], expect['value'],
                                     json.dumps(trace, sort_keys=True))

    def test_pwm_vectors_match_bruteforce_oracle_and_module(self):
        for vector in VECTORS['pwm_vectors']:
            expect = vector['expect']
            code, expected_ticks, delta = decode_bruteforce(
                vector['channel'], vector['high_ticks'])
            trace = json.dumps({'vector': vector['id'], 'expect': expect},
                               sort_keys=True)
            self.assertEqual(code, expect['decoded_code'], trace)
            self.assertEqual(expected_ticks, expect['expected_high_ticks'], trace)
            self.assertEqual(delta, expect['delta_ticks'], trace)
            within = abs(delta) <= 2
            period_ok = abs(vector['period_ticks'] - 2000000) <= 2
            self.assertEqual(expect['accepted'], within and period_ok, trace)
            self.assertEqual(
                ctl.classify_high_count(vector['channel'], vector['high_ticks'],
                                        vector['period_ticks']),
                expect, trace)


class PwmMathTests(unittest.TestCase):
    '''Candidate PWM integer math and the proposed +/-2 vs +/-3 boundary.'''

    def test_angle_formula_edges(self):
        self.assertEqual(ctl.angle_high_ticks(-15000), 10000)
        self.assertEqual(ctl.angle_high_ticks(-14999), 10016)
        self.assertEqual(ctl.angle_high_ticks(0), 250000)
        self.assertEqual(ctl.angle_high_ticks(15000), 490000)

    def test_angle_formula_full_scan_bounds(self):
        highs = [ctl.angle_high_ticks(q) for q in range(-15000, 15001)]
        self.assertEqual(min(highs), 10000)
        self.assertEqual(max(highs), 490000)
        self.assertTrue(all(b - a == 16 for a, b in zip(highs, highs[1:])))

    def test_speed_formula(self):
        self.assertEqual(ctl.speed_high_ticks(0), 50000)
        self.assertEqual(ctl.speed_high_ticks(13), 63000)
        self.assertEqual(ctl.speed_high_ticks(20), 70000)

    def test_angle_boundary_plus2_accepted_minus3_rejected(self):
        for anchor in (-15000, 0, 15000):
            base = ctl.angle_high_ticks(anchor)
            accepted = ctl.classify_high_count('yaw', base + 2)
            rejected = ctl.classify_high_count('yaw', base - 3)
            self.assertTrue(accepted['accepted'], (anchor, base + 2))
            self.assertEqual(accepted['delta_ticks'], 2)
            self.assertFalse(rejected['accepted'], (anchor, base - 3))
            self.assertEqual(rejected['delta_ticks'], -3)

    def test_speed_boundary_plus2_accepted_minus3_rejected(self):
        for anchor in (0, 20):
            base = ctl.speed_high_ticks(anchor)
            self.assertTrue(ctl.classify_high_count('speed', base + 2)['accepted'])
            self.assertFalse(ctl.classify_high_count('speed', base - 3)['accepted'])

    def test_period_boundary_candidate_only(self):
        self.assertTrue(ctl.period_valid(1999998))
        self.assertTrue(ctl.period_valid(2000000))
        self.assertTrue(ctl.period_valid(2000002))
        self.assertFalse(ctl.period_valid(1999997))
        self.assertFalse(ctl.period_valid(2000003))

    def test_half_code_tie_is_rejected_and_below_half_code(self):
        half_code_high = ctl.angle_high_ticks(0) + 8
        result = ctl.classify_high_count('yaw', half_code_high)
        self.assertEqual(result['decoded_code'], 0)
        self.assertEqual(result['delta_ticks'], 8)
        self.assertFalse(result['accepted'])
        self.assertLess(ctl.CAPTURE_TOLERANCE_TICKS, 8)

    def test_classify_flags_are_candidate_only(self):
        result = ctl.classify_high_count('pitch', 250002)
        self.assertTrue(result['candidate_only'])
        self.assertFalse(result['hardware_enable_eligible'])
        self.assertEqual(result['mode'], 'angle')

    def test_pwm_api_typed_limits(self):
        for bad in (True, False, 1.0, '0', None):
            with self.assertRaises(ctl.ValidationError):
                ctl.angle_high_ticks(bad)
            with self.assertRaises(ctl.ValidationError):
                ctl.speed_high_ticks(bad)
        with self.assertRaises(ctl.ValidationError):
            ctl.angle_high_ticks(15001)
        with self.assertRaises(ctl.ValidationError):
            ctl.angle_high_ticks(-15001)
        with self.assertRaises(ctl.ValidationError):
            ctl.speed_high_ticks(21)
        with self.assertRaises(ctl.ValidationError):
            ctl.speed_high_ticks(-1)
        with self.assertRaises(ctl.ValidationError):
            ctl.classify_high_count('yaww', 250000)


class EvidenceTests(unittest.TestCase):
    '''ChannelEvidence and BatchKey validation and immutability.'''

    def make(self, channel='yaw', high=250000, period=2000000, batch_seq=1):
        return ctl.ChannelEvidence.create(channel=channel, session=100,
                                          control_epoch=1, request_seq=7,
                                          batch_seq=batch_seq,
                                          period_ticks=period, high_ticks=high)

    def test_create_valid_flags(self):
        evidence = self.make(high=250002)
        self.assertTrue(evidence.valid)
        self.assertTrue(evidence.within_candidate_tolerance)
        self.assertTrue(evidence.period_valid)
        self.assertEqual(evidence.decoded_code, 0)
        self.assertEqual(evidence.delta_ticks, 2)
        self.assertEqual(evidence.batch_key.as_tuple(), (100, 1, 7, 1))

    def test_invalid_when_period_or_high_off(self):
        self.assertFalse(self.make(period=2000003).valid)
        self.assertFalse(self.make(high=250003).valid)
        self.assertTrue(self.make(period=2000002, high=249998).valid)

    def test_bool_and_wrong_types_rejected(self):
        with self.assertRaises(ctl.ValidationError):
            ctl.ChannelEvidence.create(channel='yaw', session=True,
                                       control_epoch=1, request_seq=7,
                                       batch_seq=1, period_ticks=2000000,
                                       high_ticks=250000)
        with self.assertRaises(ctl.ValidationError):
            ctl.ChannelEvidence.create(channel='yaw', session=100,
                                       control_epoch=1, request_seq=7,
                                       batch_seq=1, period_ticks=2000000,
                                       high_ticks=False)
        with self.assertRaises(ctl.ValidationError):
            self.make(period=2000000.0)
        with self.assertRaises(ctl.ValidationError):
            ctl.ChannelEvidence.create(channel='yaww', session=100,
                                       control_epoch=1, request_seq=7,
                                       batch_seq=1, period_ticks=2000000,
                                       high_ticks=250000)

    def test_public_constructor_rejects_caller_authored_derived_fields(self):
        good = {
            'batch_key': ctl.BatchKey(100, 1, 7, 1), 'channel': 'yaw',
            'decoded_code': 0, 'delta_ticks': 0, 'expected_high_ticks': 250000,
            'high_ticks': 250000, 'mode': 'angle', 'period_ticks': 2000000,
            'period_valid': True, 'valid': True,
            'within_candidate_tolerance': True,
        }
        evidence = ctl.ChannelEvidence(**good)
        self.assertEqual(evidence.as_dict(), self.make().as_dict())
        for field, bad in (('decoded_code', 999999), ('expected_high_ticks', 0),
                           ('delta_ticks', 12000), ('mode', 'speed'),
                           ('within_candidate_tolerance', False),
                           ('period_valid', False), ('valid', False),
                           ('decoded_code', True)):
            broken = dict(good)
            broken[field] = bad
            with self.assertRaises(ctl.ValidationError, msg=field):
                ctl.ChannelEvidence(**broken)

    def test_construct02_impossible_codes_never_construct(self):
        for channel in ('yaw', 'pitch', 'speed'):
            with self.assertRaises(ctl.ValidationError, msg=channel):
                ctl.ChannelEvidence(
                    channel=channel, batch_key=ctl.BatchKey(1, 0, 1, 1),
                    period_ticks=0, high_ticks=0,
                    mode='angle' if channel != 'speed' else 'speed',
                    decoded_code=999999, expected_high_ticks=0, delta_ticks=0,
                    within_candidate_tolerance=True, period_valid=True,
                    valid=True)

    def test_public_constructor_requires_exact_batch_key(self):
        with self.assertRaises(ctl.ValidationError):
            ctl.ChannelEvidence(
                channel='yaw', batch_key=(100, 1, 7, 1), period_ticks=2000000,
                high_ticks=250000, mode='angle', decoded_code=0,
                expected_high_ticks=250000, delta_ticks=0,
                within_candidate_tolerance=True, period_valid=True, valid=True)

    def test_batch_key_ranges(self):
        with self.assertRaises(ctl.ValidationError):
            ctl.BatchKey(4294967296, 1, 7, 1)
        with self.assertRaises(ctl.ValidationError):
            ctl.BatchKey(100, 256, 7, 1)
        with self.assertRaises(ctl.ValidationError):
            ctl.BatchKey(100, 1, 65536, 1)
        with self.assertRaises(ctl.ValidationError):
            ctl.BatchKey(100, 1, 7, -1)
        with self.assertRaises(ctl.ValidationError):
            ctl.BatchKey(100, True, 7, 1)

    def test_records_are_immutable(self):
        evidence = self.make()
        with self.assertRaises(AttributeError):
            evidence.high_ticks = 0
        with self.assertRaises(AttributeError):
            evidence.batch_key.session = 1
        key = ctl.BatchKey(100, 1, 7, 1)
        self.assertEqual(key, ctl.BatchKey(100, 1, 7, 1))
        self.assertNotEqual(key, ctl.BatchKey(100, 1, 7, 2))
        with self.assertRaises(AttributeError):
            key.control_epoch = 2
        model = ready_model()
        full_batch(model, 1)
        snapshot = model.publish_snapshot()
        with self.assertRaises(AttributeError):
            snapshot.yaw_q = 1
        self.assertEqual(snapshot.yaw_q, 0)

HIGH = {'yaw': 250000, 'pitch': 250000, 'speed': 50000}


def ready_model(session=100, epoch=1, request_seq=7):
    '''Model with an enabled session, epoch and applied request.'''
    model = ctl.CaptureSnapshotModel()
    model.begin_session(session)
    model.enable()
    model.begin_epoch(epoch)
    model.apply_request(request_seq)
    return model


def submit(model, channel, batch_seq, high, session=100, request_seq=7,
           epoch=1, period=2000000):
    evidence = ctl.ChannelEvidence.create(
        channel=channel, session=session, control_epoch=epoch,
        request_seq=request_seq, batch_seq=batch_seq,
        period_ticks=period, high_ticks=high)
    return model.submit_evidence(evidence)


def full_batch(model, batch_seq, session=100, request_seq=7):
    for channel in ('yaw', 'pitch', 'speed'):
        submit(model, channel, batch_seq, HIGH[channel],
               session=session, request_seq=request_seq)


class ModelCoreTests(unittest.TestCase):
    '''Batch binding, atomic publication, reset/STOP/fault transitions.'''

    def test_defaults_and_no_eligibility(self):
        model = ctl.CaptureSnapshotModel()
        self.assertIsNone(model.session)
        self.assertTrue(model.stopped)
        self.assertFalse(model.enabled)
        self.assertFalse(model.eligibility)
        self.assertTrue(model.needs_new_session)
        self.assertEqual(model.pending_channels, ())
        self.assertIsNone(model.latest_published())
        self.assertFalse(model.hardware_enable_eligible)

    def test_happy_path_publish(self):
        model = ready_model()
        full_batch(model, 1)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 1))
        self.assertEqual((snapshot.yaw_q, snapshot.pitch_q, snapshot.speed_code),
                         (0, 0, 0))
        self.assertEqual(snapshot.capture_quality_bits, 15)
        self.assertEqual(snapshot.phase_code, 3)
        self.assertFalse(snapshot.hardware_enable_eligible)
        self.assertTrue(model.eligibility)
        self.assertIsNot(model.latest_published(), snapshot)
        self.assertEqual(model.latest_published().as_dict(), snapshot.as_dict())
        self.assertEqual(snapshot.word_view(), (100, 1, 7, 1, 15000, 15000, 0, 15))
        self.assertEqual(model.pending_channels, ())

    def test_every_channel_permutation_publishes_one_batch(self):
        for order in itertools.permutations(('yaw', 'pitch', 'speed')):
            model = ready_model()
            for channel in order:
                self.assertEqual(submit(model, channel, 1, HIGH[channel]), 'stored')
            snapshot = model.publish_snapshot()
            self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 1), order)
            self.assertTrue(model.eligibility, order)

    def test_missing_channel_blocks_publish(self):
        model = ready_model()
        submit(model, 'yaw', 1, 250000)
        submit(model, 'pitch', 1, 250000)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        self.assertFalse(model.eligibility)
        self.assertEqual(model.pending_channels, ('pitch', 'yaw'))

    def test_newer_batch_never_merges_old_channel(self):
        model = ready_model()
        submit(model, 'yaw', 1, 250000)
        submit(model, 'pitch', 1, 250000)
        self.assertEqual(submit(model, 'yaw', 2, 490000), 'stored')
        self.assertEqual(model.pending_channels, ('yaw',))
        self.assertEqual(model.pending_key.as_tuple(), (100, 1, 7, 2))
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        submit(model, 'pitch', 2, 249984)
        submit(model, 'speed', 2, 70000)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 2))
        self.assertEqual(snapshot.yaw_q, 15000)
        self.assertEqual(snapshot.speed_code, 20)

    def test_wrong_bindings_rejected_without_state_change(self):
        model = ready_model()
        submit(model, 'yaw', 1, 250000)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'pitch', 1, 250000, session=99)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'pitch', 1, 250000, epoch=2)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'pitch', 1, 250000, request_seq=8)
        with self.assertRaises(ctl.SequenceViolationError):
            submit(model, 'pitch', 0, 250000)
        self.assertEqual(model.pending_channels, ('yaw',))
        self.assertEqual(model.pending_key.as_tuple(), (100, 1, 7, 1))

    def test_identical_duplicate_idempotent_before_and_after_publish(self):
        model = ready_model()
        self.assertEqual(submit(model, 'yaw', 1, 250000), 'stored')
        self.assertEqual(submit(model, 'yaw', 1, 250000), 'duplicate_ignored')
        submit(model, 'pitch', 1, 250000)
        submit(model, 'speed', 1, 50000)
        model.publish_snapshot()
        self.assertTrue(model.eligibility)
        self.assertEqual(submit(model, 'yaw', 1, 250000), 'duplicate_ignored')
        self.assertTrue(model.eligibility)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()

    def test_conflict_before_publish_poisons_batch(self):
        model = ready_model()
        submit(model, 'yaw', 1, 250000)
        with self.assertRaises(ctl.BatchConflictError):
            submit(model, 'yaw', 1, 250016)
        self.assertTrue(model.pending_poisoned)
        submit(model, 'pitch', 1, 250000)
        submit(model, 'speed', 1, 50000)
        self.assertEqual(model.pending_channels, ('pitch', 'speed', 'yaw'))
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        self.assertFalse(model.eligibility)

    def test_conflict_after_publish_revokes_but_never_mutates_object(self):
        model = ready_model()
        full_batch(model, 1)
        snapshot = model.publish_snapshot()
        self.assertTrue(model.eligibility)
        with self.assertRaises(ctl.BatchConflictError):
            submit(model, 'yaw', 1, 250016)
        self.assertFalse(model.eligibility)
        self.assertIsNot(model.latest_published(), snapshot)
        self.assertEqual(model.latest_published().as_dict(), snapshot.as_dict())
        self.assertEqual(snapshot.yaw_q, 0)
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 1))
        self.assertTrue(model.words_consistent(list(snapshot.word_view())))

    def test_invalid_channel_revokes_eligibility_and_new_cycle_recovers(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        self.assertTrue(model.eligibility)
        self.assertEqual(submit(model, 'yaw', 2, 250000, period=0), 'invalid_stored')
        self.assertFalse(model.eligibility)
        submit(model, 'pitch', 2, 250000)
        submit(model, 'speed', 2, 50000)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        full_batch(model, 3)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 3))
        self.assertTrue(model.eligibility)

    def test_apply_clears_eligibility_and_never_relabels(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        model.apply_request(8)
        self.assertFalse(model.eligibility)
        self.assertEqual(model.latest_published().batch_key.as_tuple(), (100, 1, 7, 1))
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'yaw', 1, 250000, request_seq=7)
        full_batch(model, 2, request_seq=8)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 8, 2))
        self.assertTrue(model.eligibility)

    def test_apply_requires_enable_and_refuses_replay(self):
        model = ctl.CaptureSnapshotModel()
        model.begin_session(5)
        with self.assertRaises(ctl.StopDominanceError):
            model.apply_request(1)
        model.enable()
        model.apply_request(1)
        with self.assertRaises(ctl.SequenceViolationError):
            model.apply_request(1)
        with self.assertRaises(ctl.SequenceViolationError):
            model.apply_request(0)
        model.apply_request(2)
        self.assertEqual(model.request_seq, 2)

    def test_stop_dominates_apply_then_enable_recovers(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        model.stop(reason='test-stop')
        self.assertFalse(model.eligibility)
        self.assertTrue(model.stopped)
        self.assertFalse(model.enabled)
        with self.assertRaises(ctl.StopDominanceError):
            model.apply_request(8)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        model.clear_fault()
        model.enable()
        model.apply_request(8)
        full_batch(model, 2, request_seq=8)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 8, 2))
        self.assertTrue(model.eligibility)

    def test_stop_mid_batch_clears_pending_and_refuses_stale_cycle(self):
        model = ready_model()
        submit(model, 'yaw', 1, 250000)
        model.stop(reason='mid-batch')
        self.assertEqual(model.pending_channels, ())
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'pitch', 1, 250000)
        self.assertIsNone(model.request_seq)
        self.assertFalse(model.eligibility)

    def test_reset_scopes_invalidate_and_require_new_session(self):
        for scope in ('fixture', 'authority', 'capture'):
            model = ready_model()
            full_batch(model, 1)
            model.publish_snapshot()
            model.reset(reason='scope-' + scope, scope=scope)
            self.assertFalse(model.eligibility, scope)
            self.assertIsNone(model.session, scope)
            self.assertTrue(model.stopped, scope)
            self.assertEqual(
                model.latest_published().batch_key.as_tuple(), (100, 1, 7, 1), scope)
            with self.assertRaises(ctl.SequenceViolationError):
                model.begin_session(100)
            with self.assertRaises(ctl.SessionStateError):
                submit(model, 'yaw', 1, 250000)
            model.begin_session(101)
            model.enable()
            model.begin_epoch(1)
            model.apply_request(8)
            full_batch(model, 1, session=101, request_seq=8)
            snapshot = model.publish_snapshot()
            self.assertEqual(snapshot.batch_key.as_tuple(), (101, 1, 8, 1), scope)
            self.assertTrue(model.eligibility, scope)

    def test_reset_scope_validated(self):
        model = ctl.CaptureSnapshotModel()
        with self.assertRaises(ctl.ValidationError):
            model.reset(scope='hardware')
        with self.assertRaises(ctl.ValidationError):
            model.reset(scope=True)
        with self.assertRaises(ctl.ValidationError):
            model.reset(reason=5)
        model.reset(reason='ok', scope='fixture')

    def test_reset_before_session_and_evidence_without_session(self):
        model = ctl.CaptureSnapshotModel()
        model.reset(reason='early-reset', scope='fixture')
        self.assertFalse(model.eligibility)
        with self.assertRaises(ctl.SessionStateError):
            submit(model, 'yaw', 1, 250000)
        with self.assertRaises(ctl.SessionStateError):
            model.apply_request(1)
        with self.assertRaises(ctl.SessionStateError):
            model.publish_snapshot()

    def test_fault_forces_stop_and_new_handshake(self):
        model = ready_model()
        model.set_fault(2)
        self.assertEqual(model.faults, 4)
        self.assertTrue(model.stopped)
        self.assertFalse(model.enabled)
        self.assertIsNone(model.session)
        with self.assertRaises(ctl.SessionStateError):
            model.apply_request(8)
        with self.assertRaises(ctl.FaultStateError):
            model.enable()
        model.clear_fault()
        self.assertEqual(model.faults, 0)
        self.assertFalse(model.enabled)
        model.enable()
        self.assertTrue(model.enabled)
        model.begin_session(101)
        self.assertFalse(model.enabled)
        model.enable()
        model.begin_epoch(1)
        model.apply_request(8)
        full_batch(model, 1, session=101, request_seq=8)
        self.assertTrue(model.publish_snapshot().batch_key.as_tuple() == (101, 1, 8, 1))

    def test_clear_fault_never_enables_and_requires_stopped(self):
        model = ctl.CaptureSnapshotModel()
        model.begin_session(1)
        model.clear_fault()
        self.assertFalse(model.enabled)
        model.enable()
        self.assertTrue(model.enabled)
        with self.assertRaises(ctl.StateError):
            model.clear_fault()
        model.set_fault(0)
        self.assertFalse(model.enabled)
        self.assertEqual(model.faults, 1)

    def test_stop_retires_request_and_late_capture_stays_refused(self):
        model = ctl.CaptureSnapshotModel()
        model.begin_session(1)
        model.begin_epoch(0)
        model.enable()
        model.apply_request(1)
        model.stop(reason='main-stop01')
        self.assertTrue(model.stopped)
        self.assertFalse(model.enabled)
        self.assertIsNone(model.request_seq)
        for channel in ('yaw', 'pitch', 'speed'):
            with self.assertRaises(ctl.ForeignEvidenceError, msg=channel):
                submit(model, channel, 1, HIGH[channel], session=1,
                       request_seq=1, epoch=0)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        self.assertFalse(model.eligibility)
        self.assertEqual(model.pending_channels, ())
        model.enable()
        for channel in ('yaw', 'pitch', 'speed'):
            with self.assertRaises(ctl.ForeignEvidenceError, msg=channel):
                submit(model, channel, 1, HIGH[channel], session=1,
                       request_seq=1, epoch=0)
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        self.assertFalse(model.eligibility)
        model.apply_request(2)
        for channel in ('yaw', 'pitch', 'speed'):
            submit(model, channel, 1, HIGH[channel], session=1,
                   request_seq=2, epoch=0)
        snapshot = model.publish_snapshot()
        self.assertEqual(snapshot.batch_key.as_tuple(), (1, 0, 2, 1))
        self.assertTrue(model.eligibility)

    def test_epoch_and_session_never_reuse_retired_request(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        model.begin_epoch(2)
        self.assertIsNone(model.request_seq)
        self.assertFalse(model.eligibility)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'yaw', 2, 250000, epoch=2)
        with self.assertRaises(ctl.SequenceViolationError):
            model.apply_request(7)
        model.apply_request(8)
        for channel in ('yaw', 'pitch', 'speed'):
            submit(model, channel, 2, HIGH[channel], epoch=2, request_seq=8)
        self.assertEqual(model.publish_snapshot().batch_key.as_tuple(),
                         (100, 2, 8, 2))
        model.begin_session(101)
        self.assertIsNone(model.request_seq)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'yaw', 1, 250000, session=101, request_seq=8, epoch=2)
        self.assertFalse(model.eligibility)

    def test_stop_with_complete_pending_batch_blocks_publication(self):
        model = ready_model()
        full_batch(model, 1)
        model.stop(reason='stop-with-complete-pending')
        self.assertEqual(model.pending_channels, ())
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        model.enable()
        with self.assertRaises(ctl.PublishNotReadyError):
            model.publish_snapshot()
        self.assertFalse(model.eligibility)
        self.assertIsNone(model.latest_published())

    def test_ingestion_is_detached_from_caller_records(self):
        model = ready_model()
        records = [ctl.ChannelEvidence.create(
            channel=channel, session=100, control_epoch=1, request_seq=7,
            batch_seq=1, period_ticks=2000000, high_ticks=HIGH[channel])
            for channel in ('yaw', 'pitch', 'speed')]
        for record in records:
            self.assertEqual(model.submit_evidence(record), 'stored')
        object.__setattr__(records[0], 'decoded_code', 12000)
        object.__setattr__(records[0].batch_key, 'request_seq', 2)
        snapshot = model.publish_snapshot()
        self.assertEqual(model.request_seq, 7)
        self.assertEqual(snapshot.yaw_q, 0)
        self.assertEqual(snapshot.batch_key.as_tuple(), (100, 1, 7, 1))
        before = snapshot.word_view()
        object.__setattr__(records[0].batch_key, 'session', 9)
        self.assertEqual(snapshot.word_view(), before)
        self.assertEqual(model.latest_published().word_view(), before)
        self.assertTrue(model.words_consistent(list(before)))
        self.assertIsNot(snapshot.batch_key, records[0].batch_key)

    def test_tampered_or_foreign_records_rejected_at_ingestion(self):
        model = ready_model()
        record = ctl.ChannelEvidence.create(
            channel='yaw', session=100, control_epoch=1, request_seq=7,
            batch_seq=1, period_ticks=2000000, high_ticks=250000)
        object.__setattr__(record, 'high_ticks', 250016)
        with self.assertRaises(ctl.ValidationError):
            model.submit_evidence(record)
        self.assertEqual(model.pending_channels, ())
        self.assertIsNone(model.pending_key)
        object.__setattr__(record, 'high_ticks', 250000)
        object.__setattr__(record, 'batch_key', (100, 1, 7, 1))
        with self.assertRaises(ctl.ValidationError):
            model.submit_evidence(record)

        class SneakyEvidence(ctl.ChannelEvidence):
            '''Subclass must not bypass the exact-type ingestion boundary.'''

        sneaky = SneakyEvidence.create(
            channel='yaw', session=100, control_epoch=1, request_seq=7,
            batch_seq=1, period_ticks=2000000, high_ticks=250000)
        with self.assertRaises(ctl.ValidationError):
            model.submit_evidence(sneaky)
        self.assertEqual(model.pending_channels, ())

    def test_detached_pending_key_and_held_alias_cannot_rewrite_model(self):
        model = ready_model()
        record = ctl.ChannelEvidence.create(
            channel='yaw', session=100, control_epoch=1, request_seq=7,
            batch_seq=1, period_ticks=2000000, high_ticks=250000)
        model.submit_evidence(record)
        first = model.pending_key
        second = model.pending_key
        self.assertIsNot(first, second)
        self.assertIsNot(first, record.batch_key)
        object.__setattr__(first, 'request_seq', 2)
        self.assertEqual(model.pending_key.as_tuple(), (100, 1, 7, 1))
        self.assertEqual(model.request_seq, 7)

class SequenceTests(unittest.TestCase):
    '''Monotonic non-wrapping candidate sequences with bounded state.'''

    def test_session_replay_regression_overflow_refused(self):
        model = ctl.CaptureSnapshotModel()
        model.begin_session(ctl.UINT32_MAX)
        with self.assertRaises(ctl.SequenceViolationError):
            model.begin_session(ctl.UINT32_MAX)
        with self.assertRaises(ctl.SequenceViolationError):
            model.begin_session(0)
        with self.assertRaises(ctl.ValidationError):
            model.begin_session(4294967296)

    def test_epoch_replay_regression_and_wrap_refused(self):
        model = ctl.CaptureSnapshotModel()
        model.begin_session(1)
        model.enable()
        model.begin_epoch(10)
        model.begin_epoch(11)
        with self.assertRaises(ctl.SequenceViolationError):
            model.begin_epoch(11)
        with self.assertRaises(ctl.SequenceViolationError):
            model.begin_epoch(10)
        with self.assertRaises(ctl.SequenceViolationError):
            model.begin_epoch(13)
        with self.assertRaises(ctl.ValidationError):
            model.begin_epoch(256)
        wrap = ctl.CaptureSnapshotModel()
        wrap.begin_session(2)
        wrap.enable()
        wrap.begin_epoch(255)
        with self.assertRaises(ctl.SequenceViolationError):
            wrap.begin_epoch(0)
        with self.assertRaises(ctl.ValidationError):
            wrap.begin_epoch(256)
        with self.assertRaises(ctl.SequenceViolationError):
            wrap.begin_epoch(255)

    def test_request_replay_regression_overflow_refused(self):
        model = ready_model()
        with self.assertRaises(ctl.SequenceViolationError):
            model.apply_request(7)
        with self.assertRaises(ctl.SequenceViolationError):
            model.apply_request(6)
        with self.assertRaises(ctl.ValidationError):
            model.apply_request(65536)
        model.apply_request(8)
        top = ctl.CaptureSnapshotModel()
        top.begin_session(1)
        top.enable()
        top.apply_request(ctl.UINT16_MAX)
        with self.assertRaises(ctl.SequenceViolationError):
            top.apply_request(0)
        with self.assertRaises(ctl.SequenceViolationError):
            top.apply_request(ctl.UINT16_MAX)
        with self.assertRaises(ctl.ValidationError):
            top.apply_request(65536)

    def test_batch_replay_regression_and_wrap_refused(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        self.assertEqual(submit(model, 'yaw', 1, 250000), 'duplicate_ignored')
        with self.assertRaises(ctl.SequenceViolationError):
            submit(model, 'yaw', 0, 250000)
        top = ready_model()
        full_batch(top, ctl.UINT32_MAX)
        top.publish_snapshot()
        self.assertEqual(submit(top, 'yaw', ctl.UINT32_MAX, 250000), 'duplicate_ignored')
        with self.assertRaises(ctl.SequenceViolationError):
            submit(top, 'yaw', 0, 250000)
        with self.assertRaises(ctl.ValidationError):
            submit(top, 'yaw', 4294967296, 250000)

    def test_bounded_state_after_many_cycles(self):
        model = ready_model()
        for batch_seq in range(1, 41):
            full_batch(model, batch_seq)
            model.publish_snapshot()
        self.assertEqual(model.pending_channels, ())
        self.assertEqual(model.published_count, 40)
        self.assertEqual(model.history_len, ctl.HISTORY_LIMIT)
        self.assertEqual(model.last_batch_seq, 40)
        latest = model.latest_published()
        self.assertEqual(latest.batch_key.batch_seq, 40)
        self.assertTrue(model.words_consistent(list(latest.word_view())))
        evicted = (100, 1, 7, 1, 15000, 15000, 0, 15)
        self.assertFalse(model.words_consistent(list(evicted)))


class FrozenReadTests(unittest.TestCase):
    '''Atomic multiword reads; torn mixes detected; invalid bytes retained as INVALID.

    Chosen coherence semantics: coherent tracks captured eligibility. Any
    revocation (STOP, reset, fault, conflict, new session, new epoch, new
    applied request, new capture cycle including invalid evidence) turns
    outstanding latches incoherent while their bytes stay readable as stale
    history; shadow register writes never disturb a latch, and a fresh latch
    from a new publication is coherent again.
    '''

    WORDS = (100, 1, 7, 1, 15000, 15000, 0, 15)

    def published_model(self):
        model = ready_model()
        full_batch(model, 1)
        model.publish_snapshot()
        return model

    def test_latch_atomic_against_shadow_writes(self):
        model = self.published_model()
        registers = ctl.CandidateRegisterFile()
        read = model.begin_frozen_read()
        self.assertEqual(read.words, self.WORDS)
        self.assertTrue(read.coherent)
        registers.write(0x50, 12345)
        registers.write(0x08, 7)
        self.assertEqual(read.words, self.WORDS)
        self.assertTrue(read.coherent)

    def test_old_latch_survives_new_cycle_as_bytes_not_freshness(self):
        model = self.published_model()
        first = model.begin_frozen_read()
        self.assertTrue(first.coherent)
        model.apply_request(8)
        self.assertFalse(model.eligibility)
        self.assertFalse(first.coherent)
        self.assertEqual(first.words, self.WORDS)
        full_batch(model, 2, request_seq=8)
        model.publish_snapshot()
        second = model.begin_frozen_read()
        self.assertEqual(first.words, self.WORDS)
        self.assertFalse(first.coherent)
        self.assertEqual(second.words, (100, 1, 8, 2, 15000, 15000, 0, 15))
        self.assertTrue(second.coherent)
        self.assertNotEqual(first.words, second.words)

    def test_new_session_and_new_epoch_revoke_latch_freshness(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        model.begin_epoch(2)
        self.assertFalse(model.eligibility)
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)
        model.begin_session(101)
        self.assertFalse(model.eligibility)
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)

    def test_new_cycle_evidence_revokes_latch_freshness(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        self.assertTrue(read.coherent)
        self.assertEqual(submit(model, 'yaw', 2, 250000), 'stored')
        self.assertFalse(model.eligibility)
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)
        self.assertFalse(model.begin_frozen_read().coherent)

    def test_invalid_channel_evidence_revokes_latch_freshness(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        self.assertEqual(submit(model, 'yaw', 2, 250000, period=1999997),
                         'invalid_stored')
        self.assertFalse(model.eligibility)
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)

    def test_stop_then_enable_never_restores_freshness_or_eligibility(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        model.stop(reason='stop-before-enable')
        model.enable()
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)
        self.assertFalse(model.begin_frozen_read().coherent)
        with self.assertRaises(ctl.ForeignEvidenceError):
            submit(model, 'yaw', 2, 250000)
        self.assertFalse(model.eligibility)

    def test_stop_invalidates_latch_but_retains_bytes(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        model.stop(reason='stop-after-latch')
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)
        fresh = model.begin_frozen_read()
        self.assertEqual(fresh.words, self.WORDS)
        self.assertFalse(fresh.coherent)

    def test_reset_invalidates_latch_but_retains_bytes(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        model.reset(reason='reset-after-latch', scope='fixture')
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)

    def test_conflict_invalidates_latch_but_retains_bytes(self):
        model = self.published_model()
        read = model.begin_frozen_read()
        with self.assertRaises(ctl.BatchConflictError):
            submit(model, 'yaw', 1, 250016)
        self.assertFalse(read.coherent)
        self.assertEqual(read.words, self.WORDS)

    def test_read_without_snapshot_is_invalid(self):
        model = ready_model()
        read = model.begin_frozen_read()
        self.assertIsNone(read.words)
        self.assertIsNone(read.batch_key)
        self.assertFalse(read.latched_current)
        self.assertFalse(read.coherent)

    def test_words_consistency_detects_torn_mixed_and_typed(self):
        model = self.published_model()
        model.apply_request(8)
        full_batch(model, 2, request_seq=8)
        model.publish_snapshot()
        good_old = [100, 1, 7, 1, 15000, 15000, 0, 15]
        good_new = [100, 1, 8, 2, 15000, 15000, 0, 15]
        self.assertTrue(model.words_consistent(good_old))
        self.assertTrue(model.words_consistent(good_new))
        self.assertFalse(model.words_consistent([100, 1, 7, 2, 15000, 15000, 0, 15]))
        self.assertFalse(model.words_consistent([100, 1, 7, 1, 15000, 15000, 15, 0]))
        self.assertFalse(model.words_consistent(good_old[:-1]))
        self.assertFalse(model.words_consistent(good_old + [0]))
        self.assertFalse(model.words_consistent([100, 1, 7, 1, 15000, 15000, 0, True]))
        self.assertFalse(model.words_consistent([100, 1, 7, 1, 15000, 15000, 0, None]))
        self.assertFalse(model.words_consistent(None))

    def test_words_consistency_uses_a_caller_side_copy(self):
        model = self.published_model()
        words = [100, 1, 7, 1, 15000, 15000, 0, 15]
        self.assertTrue(model.words_consistent(words))
        words[7] = 14
        self.assertFalse(model.words_consistent(words))
        self.assertTrue(model.words_consistent([100, 1, 7, 1, 15000, 15000, 0, 15]))


class RegisterInventoryTests(unittest.TestCase):
    '''Exact 29-offset inventory, reserved no_access, no guessed semantics.'''

    def test_module_inventory_matches_document(self):
        registers = ctl.CandidateRegisterFile()
        self.assertEqual(registers.addresses(), OFFSETS)
        self.assertEqual(registers.names(), NAMES)
        self.assertEqual(registers.addresses(), tuple(INVENTORY['registers'][i]['offset']
                                                      for i in range(len(OFFSETS))))
        for offset in OFFSETS:
            entry = ctl.register_entry(offset)
            self.assertIsNone(entry['bitfields'])
            self.assertIsNone(entry['reset_value'])

    def test_reserved_no_access(self):
        registers = ctl.CandidateRegisterFile()
        with self.assertRaises(ctl.ReservedRegisterAccessError):
            registers.read(0x2c)
        with self.assertRaises(ctl.ReservedRegisterAccessError):
            registers.write(0x2c, 0)

    def test_unknown_offsets_rejected(self):
        registers = ctl.CandidateRegisterFile()
        with self.assertRaises(ctl.ValidationError):
            registers.read(0x100)
        with self.assertRaises(ctl.ValidationError):
            registers.write(0x71, 1)
        with self.assertRaises(ctl.ValidationError):
            registers.read(-1)
        with self.assertRaises(ctl.ValidationError):
            registers.read(True)
        with self.assertRaises(ctl.ValidationError):
            registers.describe(0x100)

    def test_values_unknown_then_roundtrip(self):
        registers = ctl.CandidateRegisterFile()
        self.assertIsNone(registers.read(0x08))
        registers.write(0x08, 0xDEADBEEF)
        self.assertEqual(registers.read(0x08), 0xDEADBEEF)
        registers.write(0x08, ctl.UINT32_MAX)
        self.assertEqual(registers.read(0x08), ctl.UINT32_MAX)
        with self.assertRaises(ctl.ValidationError):
            registers.write(0x08, 4294967296)
        with self.assertRaises(ctl.ValidationError):
            registers.write(0x08, True)

    def test_partial_strobes_refused(self):
        registers = ctl.CandidateRegisterFile()
        for strobes in (0, 1, 7, 8, 14):
            with self.assertRaises(ctl.ValidationError):
                registers.write(0x08, 1, write_strobes=strobes)
        with self.assertRaises(ctl.ValidationError):
            registers.write(0x08, 1, write_strobes=True)
        with self.assertRaises(ctl.ValidationError):
            registers.write(0x08, 1, write_strobes=0x10)
        registers.write(0x08, 1, write_strobes=0xF)
        self.assertEqual(registers.read(0x08), 1)

    def test_describe_contract(self):
        entry = ctl.CandidateRegisterFile().describe(0x08)
        self.assertEqual(entry['name'], 'control')
        self.assertIsNone(entry['bitfields'])
        self.assertIsNone(entry['access'])
        self.assertIn('A freeze', entry['unknown_reason'])
        reserved = ctl.register_entry(0x2c)
        self.assertEqual(reserved['access'], 'no_access')
        self.assertEqual(reserved['name'], 'reserved')
        self.assertEqual(reserved['implementation_status'], 'no_access')


class TypedBypassTests(unittest.TestCase):
    '''No bool-as-int or non-evidence object may bypass validators.'''

    def test_model_api_rejects_bools_and_foreign_objects(self):
        model = ctl.CaptureSnapshotModel()
        with self.assertRaises(ctl.ValidationError):
            model.begin_session(True)
        with self.assertRaises(ctl.ValidationError):
            model.set_fault(False)
        with self.assertRaises(ctl.ValidationError):
            model.stop(reason=1)
        with self.assertRaises(ctl.ValidationError):
            model.submit_evidence({'channel': 'yaw'})
        with self.assertRaises(ctl.ValidationError):
            model.submit_evidence(None)
        model.begin_session(1)
        model.enable()
        with self.assertRaises(ctl.ValidationError):
            model.apply_request(True)
        with self.assertRaises(ctl.ValidationError):
            model.begin_epoch(False)


class ReaderBoundaryTests(unittest.TestCase):
    '''Main-reproduced scalar and returned-record alias regressions.'''

    def test_overloaded_integer_cannot_forge_period_validity(self):
        class ForgedPeriod(int):
            def __sub__(self, other):
                return 0
        with self.assertRaises(ctl.ValidationError):
            ctl.ChannelEvidence.create('yaw', 1, 0, 1, 1,
                                       ForgedPeriod(0), 250000)

    def test_scalar_subclasses_rejected_at_public_ingress(self):
        class Scalar(int):
            pass
        class Channel(str):
            pass
        for action in (
                lambda: ctl.BatchKey(Scalar(1), 0, 1, 1),
                lambda: ctl.CaptureSnapshotModel().begin_session(Scalar(1)),
                lambda: ctl.ChannelEvidence.create(Channel('yaw'), 1, 0, 1,
                                                   1, 2000000, 250000),
                lambda: ctl.CandidateRegisterFile().write(0x08, Scalar(1))):
            with self.assertRaises(ctl.ValidationError):
                action()

    def test_both_public_snapshot_paths_detach_from_history(self):
        model = ready_model()
        full_batch(model, 1)
        published = model.publish_snapshot()
        expected = published.word_view()
        original_read = model.begin_frozen_read()
        object.__setattr__(published, 'yaw_q', 12345)
        latest = model.latest_published()
        self.assertEqual(latest.word_view(), expected)
        object.__setattr__(latest, 'yaw_q', -12345)
        object.__setattr__(latest, 'high_yaw', 0)
        self.assertEqual(model.latest_published().word_view(), expected)
        self.assertEqual(model.begin_frozen_read().words, expected)
        self.assertEqual(original_read.words, expected)
        self.assertTrue(original_read.coherent)
        self.assertTrue(model.words_consistent(expected))
        self.assertFalse(model.words_consistent(published.word_view()))
        self.assertFalse(model.words_consistent(latest.word_view()))


class ClaimTests(unittest.TestCase):
    '''No path may claim hardware enable eligibility or stage progress.'''

    def test_enable_is_a_software_flag_only(self):
        model = ready_model()
        full_batch(model, 1)
        snapshot = model.publish_snapshot()
        self.assertTrue(model.enabled)
        self.assertFalse(model.hardware_enable_eligible)
        self.assertFalse(snapshot.hardware_enable_eligible)
        self.assertFalse(ctl.classify_high_count('yaw', 250000)['hardware_enable_eligible'])

    def test_documents_make_no_stage_or_enable_claims(self):
        self.assertFalse(INVENTORY['hardware_enable_eligible'])
        self.assertFalse(VECTORS['hardware_enable_eligible'])
        self.assertTrue(all(value == 'not_run' for value in INVENTORY['stages'].values()))
        self.assertTrue(all(value == 'not_run' for value in VECTORS['stages'].values()))
        notes = ' '.join(VECTORS['notes']).lower()
        self.assertIn('candidate-only', notes)
        self.assertIn('no board', notes)
        self.assertIn('candidate', ' '.join(INVENTORY['missing_dependencies']).lower())


if __name__ == '__main__':
    unittest.main()
