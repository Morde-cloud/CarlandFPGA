'''Safety tests: numeric API inputs must be exact built-in ints.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-CODEC-EXACT-INTEGER-BOUNDARY-20261017-01-v1

Regression tests for the E0 numeric-correctness defect reproduced by the B
director (codec-scalar-reproduction.json): an int subclass could override
arithmetic and corrupt encode/decode results, e.g.
encode_block([100, ForgedDifference(200)], 0) decoded to [100, 100] and
encode_block([ForgedAnchor(1234)], 0) decoded to [0].  The correction accepts
only exact built-in ints for numeric API inputs and rejects bool, IntEnum and
every int subclass by type before any overloaded operator of the value can
run.

These are design-time software checks for the B-side candidate inner codec.
They define no TRACE byte layout and make no board, timing, interoperability
or acceptance claim.

Run from the worktree root:
  python -B -m unittest discover -s competition/deepeye/tests/codec -v
'''

import enum
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'codec'))

import codec_reference as codec  # noqa: E402


class PassiveInt(int):
    '''Int subclass with stock int operators; still not an exact built-in int.'''


class Kind(enum.IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    SIXTEEN = 16
    SEVENTEEN = 17
    HUNDRED = 100
    THREE_HUNDRED = 300


class ArithmeticTrap(int):
    '''Every arithmetic call proves validation ran after the operator.'''

    def _trap(self, *args):
        raise AssertionError('arithmetic operator reached on ArithmeticTrap')

    __add__ = __radd__ = __sub__ = __rsub__ = _trap
    __mul__ = __rmul__ = __floordiv__ = __rfloordiv__ = _trap
    __mod__ = __rmod__ = __lshift__ = __rlshift__ = _trap
    __rshift__ = __rrshift__ = __and__ = __rand__ = _trap
    __or__ = __ror__ = __xor__ = __rxor__ = _trap
    __neg__ = __pos__ = __invert__ = __abs__ = _trap
    __index__ = __int__ = _trap
    __hash__ = int.__hash__


class ComparisonTrap(int):
    '''Every comparison/truth call proves validation ran after the operator.'''

    def _trap(self, *args):
        raise AssertionError('comparison operator reached on ComparisonTrap')

    __lt__ = __le__ = __gt__ = __ge__ = __eq__ = __ne__ = _trap
    __bool__ = _trap
    __hash__ = int.__hash__


def _base_fixture():
    '''encode_block([100, 100], 0): rice k=0, 17 valid bits, payload 006480.'''
    return codec.encode_block([100, 100], 0)


def _fixture_with(**overrides):
    fixture = _base_fixture()
    fixture.update(overrides)
    return fixture


class ReproducedE0CorruptionTests(unittest.TestCase):
    '''The two exact B-director reproductions, now required to be rejected.'''

    def test_forged_residual_sub_is_rejected(self):
        class ForgedDifference(int):
            def __sub__(self, other):
                return 0

        with self.assertRaises(codec.CodecError):
            codec.encode_block([100, ForgedDifference(200)], 0)

    def test_forged_anchor_rshift_is_rejected(self):
        class ForgedAnchor(int):
            def __rshift__(self, other):
                return 0

        with self.assertRaises(codec.CodecError):
            codec.encode_block([ForgedAnchor(1234)], 0)

    def test_forged_residual_operator_never_runs(self):
        class ForgedDifference(int):
            def __sub__(self, other):
                raise AssertionError('__sub__ reached on the residual sample')

        with self.assertRaises(codec.CodecError) as caught:
            codec.encode_block([100, ForgedDifference(200)], 0)
        self.assertIn('must be an int', str(caught.exception))

    def test_forged_anchor_operator_never_runs(self):
        class ForgedAnchor(int):
            def __rshift__(self, other):
                raise AssertionError('__rshift__ reached on the anchor sample')

        with self.assertRaises(codec.CodecError) as caught:
            codec.encode_block([ForgedAnchor(1234)], 0)
        self.assertIn('must be an int', str(caught.exception))

    def test_ordinary_values_keep_the_same_encoded_bytes(self):
        self.assertEqual(_base_fixture(), {
            'mode': 'rice', 'e': 0, 'k': 0, 'sample_count': 2,
            'valid_bit_count': 17, 'payload_hex': '006480'})
        self.assertEqual(codec.decode_block(_base_fixture()), [100, 100])


class RejectionCoverageMixin:
    def assert_all_rejected(self, cases):
        for label, call in cases.items():
            with self.subTest(label):
                with self.assertRaises(codec.CodecError):
                    call()


class PassiveSubclassRejectionTests(RejectionCoverageMixin, unittest.TestCase):
    def test_passive_int_subclass_rejected_across_the_api(self):
        self.assert_all_rejected({
            'check_samples': lambda: codec.check_samples([PassiveInt(300)]),
            'check_sample_sequence':
                lambda: codec.check_sample_sequence([PassiveInt(300)]),
            'encode_block_anchor': lambda: codec.encode_block([PassiveInt(300)], 0),
            'encode_block_residual':
                lambda: codec.encode_block([100, PassiveInt(200)], 0),
            'encode_blocks': lambda: codec.encode_blocks([0, PassiveInt(1)], 0),
            'split_blocks_sample': lambda: codec.split_blocks([PassiveInt(1)], 1),
            'check_e': lambda: codec.check_e(PassiveInt(2)),
            'zigzag': lambda: codec.zigzag(PassiveInt(-1)),
            'unzigzag': lambda: codec.unzigzag(PassiveInt(4)),
            'quantize_x': lambda: codec.quantize(PassiveInt(100), 0, 0),
            'quantize_previous': lambda: codec.quantize(0, PassiveInt(100), 0),
            'quantize_e': lambda: codec.quantize(0, 0, PassiveInt(2)),
            'reconstruct_previous': lambda: codec.reconstruct(PassiveInt(0), 0, 0),
            'reconstruct_q': lambda: codec.reconstruct(0, PassiveInt(0), 0),
            'reconstruct_e': lambda: codec.reconstruct(0, 0, PassiveInt(2)),
            'select_body_encoding':
                lambda: codec.select_body_encoding([PassiveInt(2)]),
            'block_len': lambda: codec.split_blocks([0, 1], PassiveInt(1)),
            'encode_blocks_e': lambda: codec.encode_blocks([0, 1], PassiveInt(0)),
            'decode_block_e': lambda: codec.decode_block(_fixture_with(e=PassiveInt(0))),
            'decode_block_k': lambda: codec.decode_block(_fixture_with(k=PassiveInt(0))),
            'decode_block_sample_count':
                lambda: codec.decode_block(_fixture_with(sample_count=PassiveInt(2))),
            'decode_block_valid_bit_count':
                lambda: codec.decode_block(_fixture_with(valid_bit_count=PassiveInt(17))),
            'decode_blocks': lambda: codec.decode_blocks([_fixture_with(e=PassiveInt(0))]),
        })


class IntEnumRejectionTests(RejectionCoverageMixin, unittest.TestCase):
    def test_int_enum_rejected_across_the_api(self):
        self.assert_all_rejected({
            'check_samples': lambda: codec.check_samples([Kind.THREE_HUNDRED]),
            'check_sample_sequence':
                lambda: codec.check_sample_sequence([Kind.THREE_HUNDRED]),
            'encode_block_anchor': lambda: codec.encode_block([Kind.HUNDRED], 0),
            'encode_block_residual':
                lambda: codec.encode_block([100, Kind.HUNDRED], 0),
            'encode_blocks': lambda: codec.encode_blocks([0, Kind.ONE], 0),
            'split_blocks_sample': lambda: codec.split_blocks([Kind.ONE], 1),
            'check_e': lambda: codec.check_e(Kind.TWO),
            'zigzag': lambda: codec.zigzag(Kind.ONE),
            'unzigzag': lambda: codec.unzigzag(Kind.TWO),
            'quantize_x': lambda: codec.quantize(Kind.HUNDRED, 0, 0),
            'quantize_previous': lambda: codec.quantize(0, Kind.HUNDRED, 0),
            'quantize_e': lambda: codec.quantize(0, 0, Kind.TWO),
            'reconstruct_previous': lambda: codec.reconstruct(Kind.ZERO, 0, 0),
            'reconstruct_q': lambda: codec.reconstruct(0, Kind.ZERO, 0),
            'reconstruct_e': lambda: codec.reconstruct(0, 0, Kind.TWO),
            'select_body_encoding': lambda: codec.select_body_encoding([Kind.TWO]),
            'block_len': lambda: codec.split_blocks([0, 1], Kind.ONE),
            'encode_blocks_e': lambda: codec.encode_blocks([0, 1], Kind.ZERO),
            'decode_block_e': lambda: codec.decode_block(_fixture_with(e=Kind.ZERO)),
            'decode_block_k': lambda: codec.decode_block(_fixture_with(k=Kind.ZERO)),
            'decode_block_sample_count':
                lambda: codec.decode_block(_fixture_with(sample_count=Kind.TWO)),
            'decode_block_valid_bit_count':
                lambda: codec.decode_block(_fixture_with(valid_bit_count=Kind.SEVENTEEN)),
            'decode_blocks': lambda: codec.decode_blocks([_fixture_with(e=Kind.ZERO)]),
        })


class BoolRejectionTests(RejectionCoverageMixin, unittest.TestCase):
    def test_bool_rejected_across_the_api(self):
        self.assert_all_rejected({
            'check_samples': lambda: codec.check_samples([True]),
            'check_sample_sequence': lambda: codec.check_sample_sequence([False]),
            'encode_block_anchor': lambda: codec.encode_block([True], 0),
            'encode_block_residual': lambda: codec.encode_block([100, True], 0),
            'encode_blocks': lambda: codec.encode_blocks([0, True], 0),
            'split_blocks_sample': lambda: codec.split_blocks([True], 1),
            'check_e': lambda: codec.check_e(True),
            'zigzag': lambda: codec.zigzag(True),
            'unzigzag': lambda: codec.unzigzag(True),
            'quantize_x': lambda: codec.quantize(True, 0, 0),
            'quantize_previous': lambda: codec.quantize(0, True, 0),
            'quantize_e': lambda: codec.quantize(0, 0, True),
            'reconstruct_previous': lambda: codec.reconstruct(True, 0, 0),
            'reconstruct_q': lambda: codec.reconstruct(0, True, 0),
            'reconstruct_e': lambda: codec.reconstruct(0, 0, True),
            'select_body_encoding': lambda: codec.select_body_encoding([True]),
            'block_len': lambda: codec.split_blocks([0, 1], True),
            'encode_blocks_e': lambda: codec.encode_blocks([0, 1], True),
            'decode_block_e': lambda: codec.decode_block(_fixture_with(e=True)),
            'decode_block_k': lambda: codec.decode_block(_fixture_with(k=True)),
            'decode_block_sample_count':
                lambda: codec.decode_block(_fixture_with(sample_count=True)),
            'decode_block_valid_bit_count':
                lambda: codec.decode_block(_fixture_with(valid_bit_count=True)),
            'decode_blocks': lambda: codec.decode_blocks([_fixture_with(e=True)]),
        })


class OperatorTrapTests(unittest.TestCase):
    '''Prove rejection happens before any overloaded operator can run.'''

    def test_arithmetic_trap_rejected_before_any_arithmetic(self):
        cases = {
            'check_samples': lambda: codec.check_samples([ArithmeticTrap(300)]),
            'encode_block_anchor': lambda: codec.encode_block([ArithmeticTrap(5)], 0),
            'encode_block_residual':
                lambda: codec.encode_block([100, ArithmeticTrap(200)], 0),
            'encode_blocks_e': lambda: codec.encode_blocks([0, 1], ArithmeticTrap(0)),
            'quantize_x': lambda: codec.quantize(ArithmeticTrap(100), 0, 0),
            'quantize_previous': lambda: codec.quantize(0, ArithmeticTrap(100), 0),
            'quantize_e': lambda: codec.quantize(0, 0, ArithmeticTrap(0)),
            'reconstruct_previous': lambda: codec.reconstruct(ArithmeticTrap(0), 0, 0),
            'reconstruct_q': lambda: codec.reconstruct(0, ArithmeticTrap(0), 0),
            'reconstruct_e': lambda: codec.reconstruct(0, 0, ArithmeticTrap(0)),
            'select_body_encoding':
                lambda: codec.select_body_encoding([ArithmeticTrap(2)]),
        }
        for label, call in cases.items():
            with self.subTest(label):
                with self.assertRaises(codec.CodecError) as caught:
                    call()
                self.assertIn('must be an int', str(caught.exception))

    def test_comparison_trap_rejected_before_any_comparison(self):
        cases = {
            'encode_block_anchor': lambda: codec.encode_block([ComparisonTrap(5)], 0),
            'zigzag': lambda: codec.zigzag(ComparisonTrap(5)),
            'unzigzag': lambda: codec.unzigzag(ComparisonTrap(4)),
            'select_body_encoding':
                lambda: codec.select_body_encoding([ComparisonTrap(2)]),
            'block_len': lambda: codec.split_blocks([0, 1], ComparisonTrap(1)),
            'decode_block_k': lambda: codec.decode_block(_fixture_with(k=ComparisonTrap(0))),
            'decode_block_sample_count':
                lambda: codec.decode_block(_fixture_with(sample_count=ComparisonTrap(2))),
            'decode_block_valid_bit_count':
                lambda: codec.decode_block(
                    _fixture_with(valid_bit_count=ComparisonTrap(17))),
        }
        for label, call in cases.items():
            with self.subTest(label):
                with self.assertRaises(codec.CodecError) as caught:
                    call()
                self.assertIn('must be an int', str(caught.exception))


class StrictHelperTests(unittest.TestCase):
    def test_require_int_accepts_exact_builtin_ints(self):
        for value in (0, 1, -1, 65535, 2 ** 63):
            self.assertIs(codec._require_int(value, 'x'), value)

    def test_require_int_rejects_bool_subclasses_enums_and_non_ints(self):
        for bad in (True, False, PassiveInt(5), Kind.TWO, ComparisonTrap(5),
                    5.0, 5.5, '5', None, b'5'):
            with self.subTest(repr(bad)):
                with self.assertRaises(codec.CodecError):
                    codec._require_int(bad, 'x')


class ValidBuiltinBoundaryControls(unittest.TestCase):
    '''Exact built-in ints keep the previous domain, clamping and bytes.'''

    def test_samples_at_uint16_boundaries_roundtrip(self):
        for samples in ([0], [65535], [0, 65535], [65535, 0, 65535]):
            fixture = codec.encode_block(samples, 0)
            self.assertEqual(codec.decode_block(fixture), samples)
        self.assertEqual(codec.check_samples([0] * 128), [0] * 128)
        self.assertEqual(codec.check_sample_sequence([0, 65535]), [0, 65535])

    def test_block_len_boundaries(self):
        self.assertEqual(codec.split_blocks([0, 1, 2], 1), [[0], [1], [2]])
        self.assertEqual(codec.split_blocks([0, 1, 2], 128), [[0, 1, 2]])
        self.assertEqual(len(codec.split_blocks([0] * 129, 128)), 2)

    def test_e_boundaries_and_zigzag_helpers(self):
        for e in (0, 1, 2, 4, 8):
            self.assertEqual(codec.check_e(e), e)
        self.assertEqual(codec.zigzag(0), 0)
        self.assertEqual(codec.zigzag(-1), 1)
        self.assertEqual(codec.zigzag(3), 6)
        self.assertEqual(codec.unzigzag(0), 0)
        self.assertEqual(codec.unzigzag(6), 3)
        self.assertEqual(codec.unzigzag(7), -4)

    def test_quantize_and_reconstruct_builtin_values(self):
        self.assertEqual(codec.quantize(10, 0, 0), 10)
        self.assertEqual(codec.quantize(0, 10, 1), -3)
        self.assertEqual(codec.quantize(0, 10, 2), -2)
        self.assertEqual(codec.reconstruct(10, -3, 1), 1)
        self.assertEqual(codec.reconstruct(65535, 1, 8), 65535)
        self.assertEqual(codec.reconstruct(0, -1, 8), 0)

    def test_fixture_numeric_field_boundaries(self):
        anchor_only = codec.encode_block([7], 0)
        self.assertEqual(codec.decode_block(anchor_only), [7])
        self.assertEqual(anchor_only['sample_count'], 1)
        self.assertEqual(anchor_only['valid_bit_count'], 16)
        k15 = {'mode': 'rice', 'e': 0, 'k': 15, 'sample_count': 2,
               'valid_bit_count': 32, 'payload_hex': '27108000'}
        self.assertEqual(codec.decode_block(k15), [10000, 10000])
        k0 = _base_fixture()
        self.assertEqual(k0['k'], 0)
        self.assertEqual(codec.decode_blocks([anchor_only, k0]), [7, 100, 100])

    def test_select_body_encoding_and_block_apis(self):
        selection = codec.select_body_encoding([2, 2])
        self.assertEqual(selection['mode'], 'rice')
        self.assertEqual(selection['k'], 0)
        self.assertEqual(selection['body_bits'], 6)
        fixtures = codec.encode_blocks([0, 1, 2, 3, 4], 0, 2)
        self.assertEqual(codec.decode_blocks(fixtures), [0, 1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
