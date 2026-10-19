The main long fixture uses a 2,000,000 clock-interval period and raw high counts
10,000 / 490,000 / 70,000 to exercise three distinct edges and one complete
frame. These are candidate electrical-count extrema, not a valid combined
motion command. In particular no curvature/profile/TTL/authority validation is
provided by this generator or test. The test assumes no physical clock rate,
does not prove 20 ms on a board, and does not measure capture or pin precision.

The follow-on period 37 and widths 37 / 0 / 17 deliberately exercise generic
integer boundary behavior. They are internal fixture counts, not public BOOT
or motion-profile values. Full-period high output and zero-high output are
legal primitive inputs; a future authority/capture integration may reject
such values under its separately frozen physical contract.

Operation B-DEEPEYE-PWM-ATOMIC-20261020-12; H01-H15 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
