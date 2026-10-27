# FlowForge

A C++17 compiler and reference runtime for a small FIR-filter language, with
Verilog/SystemVerilog RTL generation and Python-driven differential simulation.
Connects software tools, compiler flows, digital logic and DSP algorithms in an
FPGA-oriented development workflow. Standard C++ library and Python library only.

## Run

Install Clang, Python 3 and Icarus Verilog (`iverilog` and `vvp`).

```sh
make
./flowforge compile examples/voice.fir build/voice
python3 tests/regression.py --build-dir build/regression
```

The regression compiles the C++ tool with AddressSanitizer and
UndefinedBehaviorSanitizer, compares its runtime model against an independent
Python oracle, then simulates both baseline and optimized generated RTL.

## Language and outputs

```text
fir voice_filter
width 12
taps 1 0 -1 2 -3 0 1 4
```

`width` is 8–16 signed input bits. `taps` contains 1–16 signed int8 coefficients.
The compiler validates identifiers, duplicate directives, widths, coefficients and
unsupported syntax, then lowers the validated program into `ir.json` and
`filter.sv`. Errors include line numbers where relevant.

The default optimization removes zero-coefficient terms and replaces multiplies by
1/-1 with add/subtract terms. `--baseline` retains explicit multiply operators.
These are source-level operation counts, not measured LUT/DSP use or device speed.

`./flowforge model examples/voice.fir samples.txt` evaluates one integer sample per
line and prints the FIR output. Input violations fail with a diagnostic.

## RTL contract

Synchronous active-high reset clears history and output. On each rising clock edge
with `in_valid=1`, the output becomes the FIR result and `out_valid=1`. Invalid input
cycles do not advance filter history, hold the output value and deassert validity.
The accumulator is signed 64-bit, output signed 32-bit. Given the language bounds,
the mathematical sum fits 32 bits; no saturation or wraparound is needed.

Regression cases cover negative/extreme inputs, 1/8/16/4 taps, zero coefficients,
valid gaps, reset during a stream, malformed programs and sample-range rejection.
See [engineering notes](docs/ENGINEERING.md) and [validation results](docs/VALIDATION.md).

## Scope and limitations

This project is a compiler-to-RTL simulation flow, not a deployed FPGA accelerator.
No Quartus synthesis, placement/routing, timing closure, bitstream generation,
physical board testing, chip layout, firmware or assembler is implemented. Generated
RTL is intended for later synthesis exploration but has only been tested with
Icarus simulation here. No silicon performance, hardware-resource reduction or
power savings are claimed. Real FPGA use requires target constraints, synthesis,
timing analysis and board validation.

The CI template in `ci/github-actions.yml` is inactive; a repository owner with
workflow permissions can move it into `.github/workflows/` to enable checks.
