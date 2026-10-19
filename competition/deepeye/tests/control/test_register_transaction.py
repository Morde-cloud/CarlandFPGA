'''Portable offline tests for the B07 register transaction reference.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-REGISTER-TRANSACTION-20261019-10-v1
Contract: DEEPEYE-HUMAN-LOCK-20261014 revision 1 (H01-H15)
Requirements SHA256:
    c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804

Run from the worktree root:
  python -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_register_transaction.py -v

These are offline software tests only.  They use no board, controller,
service, credential, network, private deployment path or hardware image.
Every domain/context is an explicitly named software fixture and cannot make
hardware ENABLE or real movement eligible.
'''

import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'control'))

import register_transaction_reference as ref  # noqa: E402

BOOT_A = 'ab' * 32
BOOT_B = 'cd' * 32
BOOT_C = 'ef' * 32


def make_domain(**overrides):
    value = {
        'fixture_id': 'fixture-alpha',
        'identity': 0x12345678,
        'rate_codes': [1, 2, 3],
        'sensor_profiles': [1, 2],
        'motion_profiles': [1, 2],
        'apply_blocks': [3, 4],
        'queue_capacity': 8,
        'clock_id': 'fixture-clock',
    }
    value.update(overrides)
    return value


def make_context(**overrides):
    value = {
        'session': 1,
        'boot_digest': BOOT_A,
        'config_epoch': 0,
        'control_epoch': 0,
        'request_seq': 0,
    }
    value.update(overrides)
    return value


def make_values(**overrides):
    value = {
        'yaw_q': -15000,
        'pitch_q': 15000,
        'speed_code': 20,
        'wire_capture_seq': 0,
        'sample_tick': 0x0123456789abcdef,
        'yaw_period': 2000000,
        'pitch_period': 1000,
        'speed_period': 500,
        'quality': 0x0f,
        'gain_code': 4,
        'ratio_q8_8': 0x0180,
        'ratio_valid': True,
        'motion_profile': 1,
        'last_observed_sequence': 65535,
    }
    value.update(overrides)
    return value


def model_with_domain():
    return ref.RegisterTransactionModel(make_domain())


def model_with_context():
    model = model_with_domain()
    model.set_context(make_context())
    return model


def stage_config(model, block=3, threshold=100, rate=1,
                 error_bound=2, profile=1):
    model.write(0x10, (block << 16) | threshold)
    model.write(0x18, rate)
    model.write(0x1c, error_bound)
    model.write(0x20, profile)


def apply_config(model, seq=0):
    model.write(0x14, seq)


def ready_model(seq=0, block=3):
    model = model_with_context()
    model.set_cdc(True, False)
    model.set_fixture_gates(True, True)
    stage_config(model, block=block)
    apply_config(model, seq=seq)
    model.block_boundary(block)
    return model


def capture(model, batch_seq=0, **overrides):
    ticket = model.begin_capture(batch_seq)
    values = make_values(**overrides)
    model.complete_capture(ticket, values)
    return values


def latch(model, batch_seq=0, **overrides):
    values = capture(model, batch_seq=batch_seq, **overrides)
    model.write(0x08, 0x08)
    return values


class Base(unittest.TestCase):
    def assertCode(self, code, func, *args, **kwargs):
        with self.assertRaises(ref.RegisterTransactionError) as caught:
            func(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception


class TestAuthorityAndConstructor(Base):
    def test_authority_is_always_false(self):
        model = model_with_context()
        self.assertFalse(model.hardware_enable_eligible)
        self.assertFalse(model.movement_authorized)
        info = model.inspect()
        self.assertTrue(info['software_fixture'])
        self.assertFalse(info['hardware_enable_eligible'])
        self.assertFalse(info['movement_authorized'])
        with self.assertRaises(AttributeError):
            model.hardware_enable_eligible = True
        with self.assertRaises(AttributeError):
            model.movement_authorized = True

    def test_no_default_domain(self):
        model = ref.RegisterTransactionModel()
        self.assertCode('domain', model.read, 0x00)
        self.assertEqual(model.read(0x04), 3)
        self.assertIsNone(model.inspect()['domain'])

    def test_domain_validation(self):
        broken = make_domain()
        del broken['clock_id']
        self.assertCode('domain', ref.RegisterTransactionModel, broken)
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(extra=1))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(identity=True))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(rate_codes=[]))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(rate_codes=(1, 1)))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(rate_codes=(1, 256)))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(fixture_id=''))
        self.assertCode('domain', ref.RegisterTransactionModel,
                        make_domain(queue_capacity=65536))

    def test_domain_is_detached(self):
        rates = [1, 2]
        profiles = [1]
        domain = make_domain(rate_codes=rates, sensor_profiles=profiles,
                             motion_profiles=[1], apply_blocks=[3])
        model = ref.RegisterTransactionModel(domain)
        rates[:] = [9]
        profiles[:] = [9]
        info = model.inspect()
        self.assertEqual(info['domain']['rate_codes'], (1, 2))
        self.assertEqual(info['domain']['sensor_profiles'], (1,))
        model.set_context(make_context())
        model.write(0x18, 1)
        self.assertEqual(model.read(0x18), 1)
        self.assertCode('domain', model.write, 0x18, 9)

    def test_context_validation_and_no_mutation(self):
        model = model_with_context()
        before = model.inspect()
        broken = make_context()
        del broken['control_epoch']
        self.assertCode('context', model.set_context, broken)
        self.assertCode('context', model.set_context,
                        make_context(extra=1))
        self.assertCode('context', model.set_context,
                        make_context(boot_digest=BOOT_A.upper()))
        self.assertCode('context', model.set_context,
                        make_context(boot_digest='ab'))
        self.assertCode('context', model.set_context,
                        make_context(session=True))
        self.assertCode('context', model.set_context,
                        make_context(config_epoch=256))
        after = model.inspect()
        self.assertEqual(before['context'], after['context'])
        self.assertEqual(before['generation'], after['generation'])

    def test_context_is_detached(self):
        model = model_with_domain()
        supplied = make_context()
        model.set_context(supplied)
        supplied['session'] = 99
        supplied['request_seq'] = 99
        self.assertEqual(model.inspect()['context']['session'], 1)
        self.assertEqual(model.inspect()['context']['request_seq'], 0)

    def test_identical_context_is_noop(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        before = model.inspect()
        model.set_context(make_context())
        after = model.inspect()
        self.assertEqual(before['generation'], after['generation'])
        self.assertEqual(after['configuration']['pending']['seq'], 0)
        self.assertTrue(after['configuration']['pending'])

    def test_context_rollback_rejects_without_mutation(self):
        model = model_with_context()
        model.set_context(make_context(control_epoch=1, request_seq=0))
        stage_config(model)
        apply_config(model, 0)
        before = model.inspect()
        self.assertCode('context', model.set_context,
                        make_context(control_epoch=0, request_seq=0))
        after = model.inspect()
        self.assertEqual(before['generation'], after['generation'])
        self.assertEqual(before['configuration']['pending'],
                         after['configuration']['pending'])

    def test_request_restart_requires_control_epoch_increase(self):
        model = model_with_context()
        model.set_context(make_context(control_epoch=1, request_seq=5))
        self.assertCode('context', model.set_context,
                        make_context(control_epoch=1, request_seq=4))
        model.set_context(make_context(control_epoch=2, request_seq=0))
        self.assertEqual(model.inspect()['context']['request_seq'], 0)

    def test_pair_reuse_rejected(self):
        model = model_with_context()
        model.set_context(make_context(session=2, boot_digest=BOOT_B))
        model.set_context(make_context(session=2, boot_digest=BOOT_B))
        self.assertCode('context', model.set_context,
                        make_context(session=1, boot_digest=BOOT_A))
        model.set_context(make_context(session=1, boot_digest=BOOT_B))
        self.assertCode('context', model.set_context,
                        make_context(session=2, boot_digest=BOOT_B))

    def test_pair_capacity_and_reset_resume(self):
        model = model_with_context()
        for session in range(2, 65):
            model.set_context(make_context(session=session))
        info = model.inspect()
        self.assertEqual(info['anti_reuse']['used_pair_count'], 64)
        self.assertCode('context', model.set_context,
                        make_context(session=65))
        model.reset()
        last = model.inspect()['anti_reuse']['last_pair']
        model.set_context(make_context(session=last['session'],
                                       boot_digest=last['boot_digest']))
        self.assertCode('context', model.set_context,
                        make_context(session=1, boot_digest=BOOT_A))


class TestBusAndQueue(Base):
    def test_initial_status_and_abi(self):
        model = ref.RegisterTransactionModel()
        self.assertEqual(model.read(0x04), 3)
        self.assertEqual(model.read(0x0c), 0x00000001)

    def test_reserved_word_has_no_access(self):
        model = model_with_context()
        self.assertCode('access', model.read, 0x2c)
        self.assertCode('access', model.write, 0x2c, 0, 0)

    def test_address_validation(self):
        model = model_with_context()
        for addr in (-4, 0x02, 0x74, 0x100):
            self.assertCode('address', model.read, addr)
            self.assertCode('address', model.write, addr, 0)
        self.assertCode('address', model.read, True)
        self.assertCode('address', model.write, True, 0)

    def test_read_only_writes_reject_even_zero_strobe(self):
        model = model_with_context()
        offsets = (0x00, 0x04, 0x0c, 0x24, 0x28, 0x30, 0x34, 0x38,
                   0x3c, 0x40, 0x44, 0x48, 0x4c, 0x50, 0x54, 0x58,
                   0x5c, 0x60, 0x64, 0x68, 0x6c, 0x70)
        for offset in offsets:
            self.assertCode('access', model.write, offset, 0, 0)

    def test_write_only_reads_return_zero(self):
        model = model_with_context()
        self.assertEqual(model.read(0x08), 0)
        self.assertEqual(model.read(0x14), 0)

    def test_zero_strobe_is_noop_and_does_not_initialize(self):
        model = model_with_context()
        for offset in (0x10, 0x18, 0x1c, 0x20):
            model.write(offset, 0xffffffff, 0)
            self.assertEqual(model.read(offset), 0)
        model.write(0x08, 0xffffffff, 0)
        model.write(0x14, 0xffffffff, 0)
        info = model.inspect()
        self.assertFalse(any(info['configuration']['shadow_initialized'].values()))
        self.assertFalse(info['configuration']['dirty'])
        self.assertFalse(info['state']['stopped'] is False)

    def test_type_strict_arguments(self):
        model = model_with_context()
        self.assertCode('argument', model.write, 0x1c, True)
        self.assertCode('argument', model.write, 0x1c, -1)
        self.assertCode('argument', model.write, 0x1c, 1 << 32)
        self.assertCode('argument', model.write, 0x1c, 0, True)
        self.assertCode('argument', model.write, 0x1c, 0, 16)
        self.assertCode('argument', model.write, 0x1c, 0, -1)

    def test_identity_and_abi_reads(self):
        model = model_with_context()
        self.assertEqual(model.read(0x00), 0x12345678)
        self.assertEqual(model.read(0x04), 3)

    def test_unconfigured_queue_and_missing_binding(self):
        model = model_with_context()
        self.assertEqual(model.read(0x24), 0)
        self.assertEqual(model.read(0x28), 0)
        queue = model.inspect()['queue']
        self.assertFalse(queue['configured'])
        self.assertIsNotNone(queue['missing_binding'])
        self.assertCode('domain', ref.RegisterTransactionModel().set_queue, 0)

    def test_queue_saturation_and_reset(self):
        model = model_with_context()
        model.set_queue(3, 7, 9)
        self.assertEqual(model.read(0x24), 0x00080003)
        self.assertEqual(model.read(0x28), 0x00090007)
        model.set_queue(0, 65534, 65534)
        self.assertEqual(model.read(0x28), 0xffffffff)
        model.set_queue(0, 2, 2)
        self.assertEqual(model.read(0x28), 0xffffffff)
        self.assertCode('queue', model.set_queue, 9)
        self.assertCode('argument', model.set_queue, 0, 65536)
        model.reset()
        self.assertEqual(model.read(0x24), 0)
        self.assertEqual(model.read(0x28), 0)
        self.assertFalse(model.inspect()['queue']['configured'])


class TestShadowAndConfig(Base):
    def test_shadow_byte_mask_and_atomic_invalid_e(self):
        model = model_with_context()
        model.write(0x1c, 0xffffff02, 1)
        self.assertEqual(model.read(0x1c), 2)
        self.assertCode('shadow', model.write, 0x1c, 3, 1)
        self.assertEqual(model.read(0x1c), 2)

    def test_shadow_reserved_bits_rejected(self):
        model = model_with_context()
        self.assertCode('reserved', model.write, 0x10, 0x01000000)
        self.assertCode('reserved', model.write, 0x18, 0x00000100)
        self.assertCode('reserved', model.write, 0x1c, 0x00000100)
        self.assertCode('reserved', model.write, 0x20, 0x00000100)
        self.assertEqual(model.read(0x10), 0)
        self.assertEqual(model.read(0x18), 0)
        self.assertEqual(model.read(0x1c), 0)
        self.assertEqual(model.read(0x20), 0)

    def test_shadow_domain_membership(self):
        model = model_with_context()
        self.assertCode('domain', model.write, 0x18, 9)
        self.assertCode('domain', model.write, 0x20, 9)
        self.assertCode('domain', model.write, 0x10, 9 << 16)
        for error_bound in (0, 1, 2, 4, 8):
            model.write(0x1c, error_bound)
            self.assertEqual(model.read(0x1c), error_bound)
        self.assertCode('shadow', model.write, 0x1c, 3)

    def test_shadow_domain_required(self):
        model = ref.RegisterTransactionModel()
        self.assertCode('domain', model.write, 0x10, 0)
        self.assertCode('domain', model.write, 0x18, 0)
        self.assertCode('domain', model.write, 0x20, 0)
        model.write(0x1c, 2)
        self.assertEqual(model.read(0x1c), 2)

    def test_shadow_initialization_and_dirty(self):
        model = model_with_context()
        self.assertFalse(model.inspect()['configuration']['dirty'])
        model.write(0x10, (3 << 16) | 100)
        self.assertTrue(model.inspect()['configuration']['dirty'])
        self.assertTrue(
            model.inspect()['configuration']['shadow_initialized'][0x10])
        stage_config(model)
        apply_config(model, 0)
        model.block_boundary(3)
        info = model.inspect()
        self.assertIsNotNone(info['configuration']['active'])
        self.assertFalse(info['configuration']['dirty'])
        model.write(0x1c, 1)
        self.assertTrue(model.inspect()['configuration']['dirty'])

    def test_apply_requires_all_shadow_registers(self):
        model = model_with_context()
        model.write(0x10, (3 << 16) | 100)
        model.write(0x18, 1)
        model.write(0x1c, 2)
        self.assertCode('shadow', model.write, 0x14, 0)
        self.assertFalse(model.read(0x0c) & (1 << 8))

    def test_apply_strobe_and_reserved(self):
        model = model_with_context()
        stage_config(model)
        self.assertCode('strobe', model.write, 0x14, 0, 1)
        self.assertCode('reserved', model.write, 0x14, 0x00010000)
        self.assertFalse(model.read(0x0c) & (1 << 8))

    def test_apply_sequence_zero_and_duplicate(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        self.assertTrue(model.read(0x0c) & (1 << 8))
        self.assertEqual(model.inspect()['configuration']['pending']['seq'], 0)
        generation = model.inspect()['generation']
        apply_config(model, 0)
        self.assertEqual(model.inspect()['generation'], generation)
        self.assertEqual(model.inspect()['configuration']['pending']['seq'], 0)

    def test_apply_conflict_and_staging_after_accept(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        model.write(0x1c, 1)
        self.assertCode('apply', apply_config, model, 1)
        model.block_boundary(3)
        active = model.inspect()['configuration']['active']
        self.assertEqual(active['error_bound'], 2)
        self.assertTrue(model.inspect()['configuration']['dirty'])

    def test_block_boundary_wrong_block_is_noop(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        model.block_boundary(4)
        self.assertTrue(model.read(0x0c) & (1 << 8))
        model.block_boundary(3)
        self.assertFalse(model.read(0x0c) & (1 << 8))

    def test_boundary_publishes_once_and_increments_epoch(self):
        model = ready_model()
        info = model.inspect()
        self.assertEqual(info['context']['config_epoch'], 1)
        self.assertIsNotNone(info['configuration']['active'])
        model.block_boundary(3)
        self.assertEqual(model.inspect()['context']['config_epoch'], 1)

    def test_apply_completed_duplicate_is_noop(self):
        model = ready_model(seq=5)
        generation = model.inspect()['generation']
        apply_config(model, 5)
        info = model.inspect()
        self.assertEqual(info['context']['config_epoch'], 1)
        self.assertFalse(info['configuration']['pending'])
        self.assertEqual(info['generation'], generation)

    def test_older_and_conflicting_sequences_rejected(self):
        model = ready_model(seq=5)
        stage_config(model, error_bound=1)
        self.assertCode('apply', apply_config, model, 4)
        self.assertCode('apply', apply_config, model, 5)
        apply_config(model, 6)
        self.assertTrue(model.read(0x0c) & (1 << 8))

    def test_stop_revokes_pending_and_high_water(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        model.write(0x08, 0x01)
        self.assertFalse(model.read(0x0c) & (1 << 8))
        self.assertEqual(
            model.inspect()['configuration']['last_request']['status'],
            'revoked')
        model.block_boundary(3)
        self.assertIsNone(model.inspect()['configuration']['active'])
        self.assertCode('apply', apply_config, model, 0)
        apply_config(model, 1)
        self.assertTrue(model.read(0x0c) & (1 << 8))

    def test_context_change_discards_pending(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        model.set_context(make_context(control_epoch=1, request_seq=0))
        self.assertFalse(model.read(0x0c) & (1 << 8))
        self.assertEqual(
            model.inspect()['configuration']['last_request']['status'],
            'revoked')
        model.block_boundary(3)
        self.assertIsNone(model.inspect()['configuration']['active'])
        self.assertCode('apply', apply_config, model, 0)
        apply_config(model, 1)

    def test_epoch_255_rejects_apply(self):
        model = ref.RegisterTransactionModel(make_domain())
        model.set_context(make_context(config_epoch=255))
        stage_config(model)
        self.assertCode('apply', apply_config, model, 0)

    def test_reset_prevents_config_replay(self):
        model = ready_model(seq=5)
        model.reset()
        model.set_context(make_context(config_epoch=1))
        stage_config(model)
        self.assertCode('apply', apply_config, model, 5)
        apply_config(model, 6)
        self.assertTrue(model.read(0x0c) & (1 << 8))


class TestControlAndEnable(Base):
    def test_stop_dominates_enable(self):
        model = ready_model()
        model.write(0x08, 0x04)
        self.assertTrue(model.inspect()['state']['enabled'])
        model.write(0x08, 0x05)
        info = model.inspect()
        self.assertTrue(info['state']['stopped'])
        self.assertFalse(info['state']['enabled'])

    def test_stop_side_effects_precede_reserved_error(self):
        model = ready_model()
        model.write(0x08, 0x04)
        generation = model.inspect()['generation']
        self.assertCode('reserved', model.write, 0x08, 0x21, 1)
        info = model.inspect()
        self.assertTrue(info['state']['stopped'])
        self.assertFalse(info['state']['enabled'])
        self.assertGreater(info['generation'], generation)

    def test_stop_byte_mask_ignores_unstrobed_bytes(self):
        model = ready_model()
        model.write(0x08, 0xffffff01, 1)
        self.assertTrue(model.inspect()['state']['stopped'])

    def test_reserved_bits_reject_without_stop(self):
        model = ready_model()
        model.write(0x08, 0x04)
        self.assertCode('reserved', model.write, 0x08, 0x20)
        self.assertTrue(model.inspect()['state']['enabled'])

    def test_command_combinations_rejected(self):
        model = ready_model()
        model.write(0x08, 0x04)
        self.assertCode('command', model.write, 0x08, 0x06)
        self.assertTrue(model.inspect()['state']['enabled'])
        self.assertCode('command', model.write, 0x08, 0x18)
        self.assertCode('command', model.write, 0x08, 0x04, 1)

    def test_zero_command_is_noop(self):
        model = ready_model()
        before = model.read(0x0c)
        model.write(0x08, 0)
        self.assertEqual(model.read(0x0c), before)

    def test_enable_gate_matrix(self):
        model = model_with_context()
        stage_config(model)
        apply_config(model, 0)
        model.block_boundary(3)
        self.assertCode('state', model.write, 0x08, 0x04)
        model.set_fixture_gates(True, True)
        self.assertCode('state', model.write, 0x08, 0x04)
        model.set_cdc(True, False)
        model.write(0x08, 0x04)
        self.assertTrue(model.inspect()['state']['enabled'])

    def test_clear_fault_requires_recovery_and_stopped(self):
        model = ready_model()
        model.raise_fault(4)
        model.set_fixture_gates(True, False)
        self.assertCode('state', model.write, 0x08, 0x02)
        model.set_fixture_gates(True, True)
        model.write(0x08, 0x02)
        self.assertFalse(model.inspect()['state']['fault_latched'])
        self.assertTrue(model.inspect()['state']['stopped'])
        model.write(0x08, 0x04)
        self.assertCode('state', model.write, 0x08, 0x02)

    def test_fault_revokes_snapshot_and_blocks_enable(self):
        model = ready_model()
        model.write(0x08, 0x04)
        capture(model)
        model.write(0x08, 0x08)
        model.raise_fault(0x81)
        info = model.inspect()
        self.assertTrue(info['state']['fault_latched'])
        self.assertEqual(info['state']['fault_flags'], 0x81)
        self.assertTrue(info['state']['stopped'])
        self.assertFalse(info['state']['enabled'])
        self.assertFalse(info['snapshot']['coherent'])
        self.assertCode('state', model.write, 0x08, 0x04)
        model.write(0x08, 0x02)
        model.write(0x08, 0x04)
        self.assertTrue(model.inspect()['state']['enabled'])


class TestCapturePublication(Base):
    def test_begin_capture_preconditions_and_batch_domain(self):
        self.assertCode('domain', ref.RegisterTransactionModel().begin_capture,
                        0)
        self.assertCode('context', model_with_domain().begin_capture, 0)
        no_config = model_with_context()
        no_config.set_cdc(True, False)
        self.assertCode('state', no_config.begin_capture, 0)
        pending_only = model_with_context()
        pending_only.set_cdc(True, False)
        stage_config(pending_only)
        apply_config(pending_only, 0)
        self.assertCode('state', pending_only.begin_capture, 0)
        model = ready_model()
        model.set_cdc(True, True)
        self.assertCode('state', model.begin_capture, 0)
        model.set_cdc(True, False)
        for bad in (-1, 1 << 32, True):
            self.assertCode('argument', model.begin_capture, bad)
        ticket = model.begin_capture(0)
        self.assertIsInstance(ticket, ref.CaptureTicket)

    def test_batch_sequence_strictly_increases_and_advances_generation(self):
        model = ready_model()
        start = model.inspect()['generation']
        first = model.begin_capture(5)
        after_first = model.inspect()
        self.assertEqual(after_first['generation'], start + 1)
        self.assertEqual(after_first['capture']['batch_seq_high'], 5)
        self.assertCode('capture', model.begin_capture, 5)
        self.assertCode('capture', model.begin_capture, 4)
        second = model.begin_capture(6)
        self.assertEqual(model.inspect()['generation'], start + 2)
        self.assertCode('ticket', model.complete_capture, first,
                        make_values())
        model.complete_capture(second, make_values())
        self.assertTrue(model.inspect()['snapshot']['publication_valid'])

    def test_ticket_is_opaque_one_shot_and_model_bound(self):
        model = ready_model()
        ticket = model.begin_capture(0)
        self.assertEqual(
            model.inspect()['capture']['pending_ticket_count'], 1)
        self.assertEqual(repr(ticket), '<CaptureTicket opaque>')
        model.complete_capture(ticket, make_values())
        self.assertEqual(
            model.inspect()['capture']['pending_ticket_count'], 0)
        self.assertCode('ticket', model.complete_capture, ticket,
                        make_values())
        foreign = ready_model().begin_capture(0)
        self.assertCode('ticket', model.complete_capture, foreign,
                        make_values())
        fabricated = ref.CaptureTicket(object(), 'deadbeef')
        self.assertCode('ticket', model.complete_capture, fabricated,
                        make_values())
        self.assertCode('ticket', model.complete_capture, object(),
                        make_values())
        self.assertTrue(model.inspect()['snapshot']['publication_valid'])

    def test_ticket_cannot_survive_context_or_capture_cycle(self):
        model = ready_model()
        stale = model.begin_capture(0)
        model.set_context(make_context(config_epoch=1, control_epoch=1,
                                       request_seq=0))
        self.assertCode('ticket', model.complete_capture, stale,
                        make_values())
        superseded = model.begin_capture(1)
        replacement = model.begin_capture(2)
        self.assertCode('ticket', model.complete_capture, superseded,
                        make_values())
        model.complete_capture(replacement, make_values())
        self.assertTrue(model.inspect()['snapshot']['publication_valid'])


class TestCaptureValidation(Base):
    def test_values_validation_is_exact_and_atomic(self):
        model = ready_model()
        capture(model)
        bank_before = dict(model.inspect()['snapshot']['bank'])
        cases = (
            {'yaw_q': 15001},
            {'pitch_q': -15001},
            {'speed_code': 21},
            {'wire_capture_seq': 1 << 16},
            {'sample_tick': -1},
            {'quality': 0x10},
            {'gain_code': 3},
            {'ratio_valid': 1},
            {'last_observed_sequence': 1 << 16},
        )
        batch = 1
        for override in cases:
            ticket = model.begin_capture(batch)
            batch += 1
            self.assertCode('capture', model.complete_capture, ticket,
                            make_values(**override))
            info = model.inspect()['snapshot']
            self.assertEqual(info['bank'], bank_before)
            self.assertFalse(info['publication_valid'])
        ticket = model.begin_capture(batch)
        self.assertCode('domain', model.complete_capture, ticket,
                        make_values(motion_profile=9))
        unknown = dict(make_values(), session=1)
        ticket = model.begin_capture(100)
        self.assertCode('capture', model.complete_capture, ticket, unknown)
        missing = make_values()
        del missing['quality']
        ticket = model.begin_capture(101)
        self.assertCode('capture', model.complete_capture, ticket, missing)
        ticket = model.begin_capture(102)
        self.assertCode('capture', model.complete_capture, ticket,
                        [('yaw_q', 0)])
        ticket = model.begin_capture(103)
        self.assertCode('capture', model.complete_capture, ticket,
                        make_values(yaw_q=True))
        ticket = model.begin_capture(104)
        self.assertCode('capture', model.complete_capture, ticket,
                        make_values(gain_code=3))
        self.assertCode('ticket', model.complete_capture, ticket,
                        make_values())

    def test_quality_period_gates_and_ratio_validity(self):
        model = ready_model()
        gate_cases = (
            {'quality': 0x01, 'yaw_period': 0},
            {'quality': 0x02, 'pitch_period': 0},
            {'quality': 0x04, 'speed_period': 0},
            {'quality': 0x08, 'yaw_period': 0},
            {'quality': 0x08, 'pitch_period': 0},
            {'quality': 0x08, 'speed_period': 0},
        )
        batch = 0
        for override in gate_cases:
            ticket = model.begin_capture(batch)
            batch += 1
            self.assertCode('capture', model.complete_capture, ticket,
                            make_values(**override))
        ticket = model.begin_capture(batch)
        model.complete_capture(ticket, make_values(
            quality=0, yaw_period=0, pitch_period=0, speed_period=0,
            ratio_q8_8=0, ratio_valid=True, wire_capture_seq=10))
        model.write(0x08, 0x08)
        snap = model.read_snapshot()
        self.assertEqual(snap['words'][0x5c], 0)
        self.assertTrue(snap['ratio_valid'])
        self.assertTrue(snap['gain_ratio_valid'])
        self.assertTrue(model.read(0x0c) & (1 << 9))
        model.write(0x08, 0x10)
        ticket = model.begin_capture(batch + 1)
        model.complete_capture(ticket, make_values(
            quality=0, yaw_period=0, pitch_period=0, speed_period=0,
            ratio_q8_8=0x0180, ratio_valid=False, wire_capture_seq=11))
        model.write(0x08, 0x08)
        snap = model.read_snapshot()
        self.assertEqual(snap['words'][0x5c], 0x0180)
        self.assertFalse(snap['ratio_valid'])
        self.assertFalse(snap['gain_ratio_valid'])
        self.assertFalse(model.read(0x0c) & (1 << 9))

    def test_wire_sequence_and_sample_tick_high_water(self):
        model = ready_model()
        capture(model, batch_seq=0, wire_capture_seq=5, sample_tick=100)
        ticket = model.begin_capture(1)
        self.assertCode('capture', model.complete_capture, ticket,
                        make_values(wire_capture_seq=5, sample_tick=100))
        ticket = model.begin_capture(2)
        self.assertCode('capture', model.complete_capture, ticket,
                        make_values(wire_capture_seq=6, sample_tick=99))
        ticket = model.begin_capture(3)
        model.complete_capture(ticket,
                               make_values(wire_capture_seq=6,
                                           sample_tick=100))
        info = model.inspect()['capture']
        self.assertEqual(info['wire_seq_high'], 6)
        self.assertEqual(info['sample_tick_high'], 100)
        self.assertTrue(model.inspect()['snapshot']['publication_valid'])


class TestSnapshotPublication(Base):
    def test_publication_bank_and_stamp_come_from_bound_context(self):
        context = make_context(session=0x0abc, boot_digest=BOOT_C,
                               control_epoch=0xab, request_seq=0x1234)
        model = ref.RegisterTransactionModel(make_domain())
        model.set_context(context)
        model.set_cdc(True, False)
        model.set_fixture_gates(True, True)
        stage_config(model)
        apply_config(model, 7)
        model.block_boundary(3)
        values = make_values(
            yaw_q=-15000, pitch_q=-1, speed_code=20,
            wire_capture_seq=0xffff, sample_tick=0x0123456789abcdef,
            yaw_period=2000000, pitch_period=123, speed_period=456,
            quality=0x0f, gain_code=4, ratio_q8_8=0x0180,
            ratio_valid=True, motion_profile=2,
            last_observed_sequence=0xffff)
        ticket = model.begin_capture(1)
        model.complete_capture(ticket, values)
        expected = {
            0x30: 0xffffc568, 0x34: 20, 0x38: 0x0eab1234,
            0x3c: 0x0abc, 0x40: 0x89abcdef, 0x44: 0x01234567,
            0x48: 0x001e8480, 0x4c: 0, 0x50: 0xffff, 0x54: 0x0f,
            0x58: 4, 0x5c: 0x0180, 0x60: 0xffffffff, 0x64: 123,
            0x68: 456, 0x6c: 2, 0x70: 0xffff,
        }
        for offset, word in expected.items():
            self.assertEqual(model.read(offset), word)
        info = model.inspect()['snapshot']
        self.assertTrue(info['publication_valid'])
        self.assertFalse(info['latched'])
        self.assertFalse(info['coherent'])
        self.assertTrue(info['available'])
        self.assertTrue(model.read(0x0c) & (1 << 4))
        # B07 bit9 describes the coherent latched bank, not an unlatched offer.
        self.assertFalse(model.read(0x0c) & (1 << 9))
        model.write(0x08, 0x08)
        self.assertTrue(model.read(0x0c) & (1 << 9))
        snap = model.read_snapshot()
        self.assertTrue(snap['software_fixture'])
        self.assertFalse(snap['hardware_enable_eligible'])
        self.assertFalse(snap['movement_authorized'])
        self.assertEqual(snap['batch_seq'], 1)
        self.assertEqual(snap['words'], expected)
        self.assertEqual(snap['decoded'], {
            'yaw_q': -15000, 'pitch_q': -1, 'speed_code': 20,
            'request_seq': 0x1234, 'control_epoch': 0xab,
            'request_type': 0x0e, 'session': 0x0abc,
            'sample_tick': 0x0123456789abcdef,
            'yaw_period': 2000000, 'wire_capture_seq': 0xffff,
            'quality': 0x0f, 'gain_code': 4, 'ratio_q8_8': 0x0180,
            'pitch_period': 123, 'speed_period': 456,
            'motion_profile': 2, 'last_observed_sequence': 0xffff,
        })
        self.assertEqual(snap['context']['session'], 0x0abc)
        self.assertEqual(snap['context']['request_seq'], 0x1234)
        self.assertEqual(snap['context']['config_epoch'], 1)
        latch_info = model.inspect()['snapshot']['latch']
        self.assertEqual(latch_info['batch_seq'], 1)
        self.assertEqual(latch_info['words'], expected)
        self.assertTrue(latch_info['ratio_valid'])
        self.assertEqual(latch_info['context']['session'], 0x0abc)
        status = model.read(0x0c)
        for bit in (2, 3, 4, 9):
            self.assertTrue(status & (1 << bit))

    def test_latch_requires_publication_and_eligible_cdc(self):
        model = ready_model()
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        capture(model)
        model.set_cdc(True, True)
        self.assertFalse(model.inspect()['snapshot']['publication_valid'])
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        model.set_cdc(True, False)
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        capture(model, batch_seq=1, wire_capture_seq=1)
        model.write(0x08, 0x08)
        self.assertTrue(model.inspect()['snapshot']['coherent'])

    def test_second_latch_revokes_and_preserves_historical_bank(self):
        model = ready_model()
        latch(model, batch_seq=0, wire_capture_seq=3)
        bank = dict(model.inspect()['snapshot']['bank'])
        self.assertTrue(model.read(0x0c) & (1 << 3))
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        status = model.read(0x0c)
        self.assertTrue(status & (1 << 2))
        self.assertFalse(status & (1 << 3))
        self.assertFalse(status & (1 << 4))
        self.assertFalse(status & (1 << 9))
        self.assertEqual(model.inspect()['snapshot']['bank'], bank)
        self.assertEqual(model.read(0x30), bank[0x30])
        self.assertCode('snapshot', model.read_snapshot)
        model.write(0x08, 0x10)
        status = model.read(0x0c)
        self.assertFalse(status & (1 << 2))
        self.assertFalse(status & (1 << 3))
        self.assertFalse(status & (1 << 4))
        self.assertCode('snapshot', model.write, 0x08, 0x08)

    def test_new_capture_revokes_latch_and_requires_release(self):
        model = ready_model()
        latch(model, batch_seq=0, wire_capture_seq=4, yaw_q=1000)
        first_bank = dict(model.inspect()['snapshot']['bank'])
        generation = model.inspect()['generation']
        ticket = model.begin_capture(1)
        self.assertEqual(model.inspect()['generation'], generation + 1)
        info = model.inspect()['snapshot']
        self.assertFalse(info['coherent'])
        self.assertFalse(info['gain_ratio_valid'])
        self.assertFalse(info['available'])
        self.assertTrue(model.read(0x0c) & (1 << 2))
        self.assertEqual(model.inspect()['snapshot']['bank'], first_bank)
        self.assertCode('snapshot', model.read_snapshot)
        model.complete_capture(ticket, make_values(wire_capture_seq=5,
                                                   yaw_q=2000))
        second_bank = dict(model.inspect()['snapshot']['bank'])
        self.assertTrue(model.read(0x0c) & (1 << 4))
        self.assertFalse(model.read(0x0c) & (1 << 3))
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        self.assertFalse(model.inspect()['snapshot']['publication_valid'])
        self.assertEqual(model.inspect()['snapshot']['bank'], second_bank)
        model.write(0x08, 0x10)
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        ticket = model.begin_capture(2)
        model.complete_capture(ticket, make_values(wire_capture_seq=6,
                                                   yaw_q=3000))
        model.write(0x08, 0x08)
        self.assertEqual(model.read_snapshot()['decoded']['yaw_q'], 3000)

    def test_specified_revocation_causes_clear_coherence(self):
        def stop(model):
            model.write(0x08, 0x01)

        def fault(model):
            model.raise_fault(0x81)

        def context_change(model):
            model.set_context(make_context(config_epoch=1,
                                           control_epoch=1,
                                           request_seq=0))

        def cdc_busy(model):
            model.set_cdc(True, True)

        def new_request(model):
            stage_config(model, error_bound=1)
            apply_config(model, 1)

        actions = (
            ('stop', stop),
            ('fault', fault),
            ('context', context_change),
            ('cdc', cdc_busy),
            ('new_request', new_request),
        )
        for name, action in actions:
            with self.subTest(cause=name):
                model = ready_model()
                latch(model, batch_seq=0, wire_capture_seq=2, yaw_q=777)
                bank = dict(model.inspect()['snapshot']['bank'])
                action(model)
                info = model.inspect()['snapshot']
                self.assertFalse(info['coherent'])
                self.assertFalse(info['gain_ratio_valid'])
                self.assertFalse(info['available'])
                self.assertTrue(model.read(0x0c) & (1 << 2))
                self.assertEqual(model.inspect()['snapshot']['bank'], bank)
                self.assertEqual(model.read(0x30), bank[0x30])
                self.assertCode('snapshot', model.read_snapshot)

    def test_interleave_revocation_rejects_whole_snapshot(self):
        def stop(model):
            model.write(0x08, 0x01)

        def fault(model):
            model.raise_fault(0x82)

        def context_change(model):
            model.set_context(make_context(config_epoch=1,
                                           control_epoch=1,
                                           request_seq=0))

        def cdc_busy(model):
            model.set_cdc(True, True)

        def new_capture(model):
            model.begin_capture(1)

        actions = (
            ('stop', stop),
            ('fault', fault),
            ('context', context_change),
            ('cdc', cdc_busy),
            ('new_capture', new_capture),
        )
        for name, action in actions:
            for offset in (0x30, 0x70):
                with self.subTest(cause=name, offset=offset):
                    model = ready_model()
                    latch(model, batch_seq=0, wire_capture_seq=2)
                    fired = []

                    def interleave(read_offset, current):
                        if read_offset == offset and not fired:
                            fired.append(read_offset)
                            action(current)

                    self.assertCode('snapshot', model.read_snapshot,
                                    interleave)
                    self.assertEqual(fired, [offset])

    def test_benign_interleave_returns_complete_detached_snapshot(self):
        model = ready_model()
        latch(model, batch_seq=0, wire_capture_seq=2)
        seen = []
        snap = model.read_snapshot(
            lambda offset, current: seen.append(offset))
        self.assertEqual(seen, list(range(0x30, 0x74, 4)))
        self.assertEqual(len(snap['words']), 17)
        self.assertEqual(sorted(snap['words']),
                         list(range(0x30, 0x74, 4)))

    def test_snapshot_and_inspect_results_are_detached(self):
        model = ready_model()
        latch(model, batch_seq=0, wire_capture_seq=2, yaw_q=-123)
        first = model.read_snapshot()
        first['words'][0x30] = 0
        first['decoded']['yaw_q'] = 0
        first['context']['session'] = 999
        second = model.read_snapshot()
        self.assertEqual(second['decoded']['yaw_q'], -123)
        self.assertNotEqual(second['words'][0x30], 0)
        self.assertEqual(second['context']['session'], 1)
        info = model.inspect()
        info['snapshot']['bank'][0x30] = 0
        info['configuration']['shadow'][0x10] = 0xffffffff
        fresh = model.inspect()
        self.assertNotEqual(fresh['snapshot']['bank'][0x30], 0)
        self.assertEqual(fresh['configuration']['shadow'][0x10],
                         model.read(0x10))

    def test_latched_words_survive_unrelated_fixture_updates(self):
        model = ready_model()
        latch(model, batch_seq=0, wire_capture_seq=2)
        before = model.read_snapshot()
        model.set_fixture_gates(True, True)
        model.set_queue(0, 1, 1)
        model.write(0x1c, 1)
        after = model.read_snapshot()
        self.assertEqual(before['words'], after['words'])
        self.assertEqual(before['decoded'], after['decoded'])
        status = model.read(0x0c)
        self.assertTrue(status & (1 << 7))
        self.assertTrue(status & (1 << 3))
        self.assertTrue(status & (1 << 9))

    def test_status_bits_track_publication_latch_and_release(self):
        model = ready_model()
        status = model.read(0x0c)
        for bit in (2, 3, 4, 9):
            self.assertFalse(status & (1 << bit))
        capture(model, ratio_valid=True)
        status = model.read(0x0c)
        self.assertTrue(status & (1 << 4))
        self.assertFalse(status & (1 << 9))
        self.assertFalse(status & (1 << 2))
        self.assertFalse(status & (1 << 3))
        model.write(0x08, 0x08)
        status = model.read(0x0c)
        for bit in (2, 3, 4, 9):
            self.assertTrue(status & (1 << bit))
        model.write(0x08, 0x10)
        status = model.read(0x0c)
        for bit in (2, 3, 4, 9):
            self.assertFalse(status & (1 << bit))
        self.assertEqual(status & 0xff00f800, 0)

    def test_reset_clears_snapshot_bank_and_ticket(self):
        model = ready_model()
        ticket = model.begin_capture(0)
        model.complete_capture(ticket, make_values(wire_capture_seq=2))
        model.write(0x08, 0x08)
        self.assertTrue(model.inspect()['snapshot']['coherent'])
        model.reset()
        info = model.inspect()['snapshot']
        self.assertFalse(info['publication_valid'])
        self.assertFalse(info['latched'])
        self.assertFalse(info['coherent'])
        self.assertFalse(info['available'])
        self.assertEqual(set(info['bank'].values()), {0})
        self.assertEqual(model.read(0x30), 0)
        self.assertCode('snapshot', model.read_snapshot)
        self.assertEqual(model.read(0x0c), 0x00000001)
        model = ready_model()
        stale = model.begin_capture(0)
        model.reset()
        model.set_context(make_context(config_epoch=1))
        model.set_cdc(True, False)
        stage_config(model)
        apply_config(model, 6)
        model.block_boundary(3)
        self.assertCode('ticket', model.complete_capture, stale,
                        make_values())

    def test_capture_cycle_revokes_generation_bound_pending_config(self):
        model = ready_model(seq=0)
        stage_config(model, error_bound=1)
        apply_config(model, 1)
        self.assertTrue(model.read(0x0c) & (1 << 8))
        model.begin_capture(0)
        self.assertFalse(model.read(0x0c) & (1 << 8))
        self.assertEqual(
            model.inspect()['configuration']['last_request']['status'],
            'revoked')
        model.block_boundary(3)
        after = model.inspect()
        self.assertEqual(after['configuration']['active']['error_bound'], 2)
        self.assertTrue(after['configuration']['dirty'])
        self.assertCode('apply', apply_config, model, 1)
        apply_config(model, 2)
        self.assertTrue(model.read(0x0c) & (1 << 8))


class TestFixtureInputs(Base):
    def test_fixture_setters_are_type_strict_and_reset_clears_gates(self):
        model = ready_model()
        self.assertCode('argument', model.set_fixture_gates, 1, True)
        self.assertCode('argument', model.set_fixture_gates, True, 1)
        self.assertCode('argument', model.set_cdc, True, 1)
        self.assertCode('argument', model.set_queue, True)
        self.assertCode('argument', model.raise_fault, 256)
        self.assertCode('argument', model.block_boundary, True)
        model.set_fixture_gates(True, True)
        model.set_cdc(True, False)
        model.set_queue(1, 1, 1)
        model.reset()
        info = model.inspect()
        self.assertFalse(info['fixture_gates']['enable'])
        self.assertFalse(info['fixture_gates']['recovery'])
        self.assertFalse(info['cdc']['online'])
        self.assertFalse(info['cdc']['busy'])
        self.assertFalse(info['queue']['configured'])
        self.assertEqual(model.read(0x24), 0)

    def test_reset_advances_generation_monotonically(self):
        model = ready_model()
        before = model.inspect()['generation']
        model.reset()
        after = model.inspect()['generation']
        self.assertEqual(after, before + 1)
        model.reset()
        self.assertEqual(model.inspect()['generation'], after + 1)

    def test_stale_pending_cannot_publish_at_boundary(self):
        model = ready_model(seq=0)
        capture(model, batch_seq=0)
        model.write(0x08, 0x08)
        self.assertTrue(model.inspect()['snapshot']['coherent'])
        stage_config(model, error_bound=1)
        apply_config(model, 1)
        self.assertTrue(model.read(0x0c) & (1 << 8))
        self.assertCode('snapshot', model.write, 0x08, 0x08)
        self.assertCode('apply', model.block_boundary, 3)
        info = model.inspect()
        self.assertFalse(model.read(0x0c) & (1 << 8))
        self.assertEqual(info['configuration']['last_request']['status'],
                         'revoked')
        self.assertEqual(info['configuration']['active']['error_bound'], 2)


class TestSourcePins(Base):
    def test_source_pins_and_authority_constants(self):
        info = model_with_context().inspect()
        self.assertEqual(
            info['source']['requirements_sha256'],
            'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804')
        self.assertEqual(
            info['source']['lock_commit'],
            'f5989cd5defce561f9ba98e6b18fc2682945f0a2')
        self.assertEqual(
            info['source']['design_commit'],
            '1011259415a0916054eb580687612580bc1e5f09')
        self.assertEqual(
            info['source']['base_commit'],
            '433db2a82854a669778eb8c3cd35c309623a087e')
        self.assertEqual(
            info['source']['owner_decision_sha256'],
            '5cb049b28da33eea74e8a30365962d731b3f2d198065086daab1998ff747e116')
        self.assertEqual(info['task_id'], 'DEEPEYE-IMPLEMENTATION-20261014')
        self.assertEqual(info['task_version'], 1)
        self.assertEqual(info['work_id'],
                         'B-REGISTER-TRANSACTION-20261019-10-v1')
        self.assertEqual(info['operation_id'],
                         'B-DEEPEYE-REGISTER-TRANSACTION-20261019-10')
        self.assertIn('offline software reference', info['stage'])
        self.assertTrue(ref.SOFTWARE_FIXTURE)
        self.assertFalse(ref.HARDWARE_ENABLE_ELIGIBLE)
        self.assertFalse(ref.MOVEMENT_AUTHORIZED)
