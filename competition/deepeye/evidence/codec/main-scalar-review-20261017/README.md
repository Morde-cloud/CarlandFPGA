# Exact built-in integer boundary correction

The inner-codec Python API accepted int subclasses with overloaded arithmetic.
Main reproduced E=0 input values [100,200] becoming [100,100] through a residual
operator override, and anchor1234 becoming0 through a shift override. These are
Python numeric-correctness failures, not wire exploits or an arbitrary-code
security isolation claim. Exact built-in ints are now required at numeric API
ingress; bool, IntEnum and int subclasses are rejected before their operators.

The main independent negative control against preserved original source has
87 failing safety cases among108 checks (exit1). The fixed source must reject
all108, with zero overloaded operator calls. Ordinary encoding regression
comparison covers1000 blocks across E=0/1/2/4/8 and250 direct helper controls.
This compares ordinary bytes with the old codec; it is not a replacement for
C's independent binary decoder or the full B01 million-sample requirement.
The existing61 vector file and original unit-test source remain byte-identical.
Raw worker RED/GREEN and main logs are retained; red safety tests are not passed
product acceptance. No wire offsets, bit order, Rice/RAW formula, schedules,
tick/mask fields or public A ABI are changed. Full TRACE/R03 remains incomplete.

From a repository root with Python3.12:

```text
python -B -X utf8 -m unittest discover -s competition/deepeye/tests/codec -v
python -B -X utf8 competition/deepeye/evidence/codec/main-scalar-review-20261017/independent_scalar_review.py --source competition/deepeye/golden/codec/codec_reference.py --original competition/deepeye/evidence/codec/main-scalar-review-20261017/codec-original.py --vectors competition/deepeye/golden/codec/known_vectors.json --output-root YOUR_NEW_DIRECTORY
```

Run the second command with --source also pointing to codec-original.py to
reproduce the old expected rejection (exit1); keep outputs in a different new
directory. Main reviewed only this scoped code change and targeted software
tests. Existing asset/render/control evidence was not rerun or reaccepted.

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09 unchanged. A owns final ABI and
physical board. B01/R03/simulation/synthesis/implementation/board/system are not
accepted by this correction. Historical manifests retain their old source/head.
