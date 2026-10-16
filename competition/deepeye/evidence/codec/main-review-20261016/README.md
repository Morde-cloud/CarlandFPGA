# B inner-codec candidate review

Only the pure uint16 inner block codec and corrected per-block byte accounting are reviewed here. The complete TRACE payload (tick/mask/index/sequence/channel metadata and <=32-byte accounting), A ABI acceptance and C independent interoperability remain incomplete. R03/B01 and simulation/synthesis/implementation/board/system remain not_run. H01-H15 contract requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; design1011259415a0916054eb580687612580bc1e5f09.

The original `integer-foundation-01` aggregate byte counts are rejected because they rounded the sum of all bits once, omitting per-block padding. Those original logs remain unchanged. `byte-accounting-correction-02` supersedes only that evidence and its verifier/documentation. Core codec and encoded vectors are byte-identical. The old tiny-witness assertion mistake in the main's reproduction is explicitly recorded; the valid witness uses two 17-bit constant blocks (6 stored bytes, not5).

Run from repository root with Python3.12.9 (stdlib only):
`python -B -X utf8 competition/deepeye/evidence/codec/main-review-20261016/independent_review.py --output-root YOUR_EMPTY_EVIDENCE_DIRECTORY`

The source corpus is a separately prepared 12-case/440-sample input corpus, not claimed sensor measurements. The review reruns49 baseline tests, uses an independent nearest-integer quantizer and bitstring packer for983040 scalar checks/4540 exact encoded blocks, checks malformed inputs/block restart, and independently sums actual block lengths. Five million-profile byte totals were separately recomputed by B main from the immutable core and same seeded source stream before correction.

The final handoff is a software-review request, not a board request or a request to enable TRACE. All Control/Assets files in the working directory are excluded from this codec-only commit.
