# Local verification record

Executed on 2026-10-26, macOS ARM64, Apple Clang, Python 3, Icarus Verilog.

Command: `python3 tests/regression.py --build-dir /private/tmp/flowforge-regression`

| Check | Result |
| --- | ---: |
| FIR width/tap configurations | 12 |
| Malformed specifications rejected | 14 |
| Additional range/missing-file diagnostics | 2 |
| C++ outputs compared with independent Python oracle | 6,144 |
| RTL outputs checked across baseline and optimized forms | 12,288 |
| Explicit multiply operators across baseline source configurations | 87 |
| Explicit multiply operators across optimized source configurations | 57 |
| Source multiply operators removed | 30 |

The C++ executable used AddressSanitizer and UndefinedBehaviorSanitizer. RTL checks
included valid gaps, held outputs and a reset in the middle of each stream. No
sanitizer failures or numerical mismatches were observed in this regression.

Counts are deterministic validation workload totals. Source-operation elimination
is not measured FPGA resource reduction: synthesis tools can perform equivalent
constant optimizations. No timing, frequency, FPGA speedup, board execution,
silicon validation, Quartus build or physical-design result is claimed.
