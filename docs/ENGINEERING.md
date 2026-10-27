# Compiler and verification design

Pipeline: text specification → validated typed program → optimization selection →
JSON intermediate representation and RTL → C++/Python/RTL differential checks.

The language is intentionally bounded. Up to 16 coefficients of magnitude 128 and
16-bit signed samples imply an absolute sum bounded by 67,108,864, below signed
32-bit range. Explicit 64-bit RTL terms prevent narrow intermediate arithmetic;
baseline and optimized forms are checked against the same mathematical oracle.

The compiler removes only arithmetic known to be redundant from constant
coefficients. This exposes software-level optimization without claiming that a
hardware synthesizer could not perform the same optimizations itself.

Verification uses an independent Python convolution rather than reusing compiler
code. C++ model segments restart at the same midstream reset boundary as the RTL.
Directed extrema plus seeded random inputs make numerical failures reproducible.
The testbench checks output validity, hold behavior and history reset as well as
numeric equality. Every subprocess has a timeout; a missing simulator fails rather
than silently skipping hardware-model checks.

Next steps: inspect synthesis reports in Quartus on a specified device, compare
resource/timing results, add explicit pipeline stages or time-multiplexing, and
validate an actual FPGA board interface. That requires hardware-specific work not
demonstrated by this repository.
