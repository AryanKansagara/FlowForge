"""Cross-check a C++ FIR compiler/model, Python oracle and generated RTL."""
import argparse
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], text=True, capture_output=True,
                          check=True, timeout=30, **kwargs)

def golden(taps, samples):
    history = [0] * len(taps)
    result = []
    for sample in samples:
        history = [sample] + history[:-1]
        result.append(sum(coefficient * value for coefficient, value in zip(taps, history)))
    return result

def bench(width, taps, samples, expected, module, reset_at):
    # Each cycle includes valid and expected data; invalid cycles hold history/output.
    rows = []
    previous = 0
    for index, (sample, output) in enumerate(zip(samples, expected)):
        if index == reset_at:
            rows.append('rst=1; in_valid=0; @(posedge clk); #1; if(out_valid!==0 || sample_out!==0) $fatal(1,"reset failure"); @(negedge clk); rst=0;')
            previous = 0
        rows.append(f'in_valid=1; sample_in={sample}; @(posedge clk); #1; if(out_valid!==1 || $signed(sample_out)!={output}) $fatal(1,"sample {index} mismatch got=%0d",$signed(sample_out)); @(negedge clk);')
        previous = output
        if index % 7 == 0:
            rows.append(f'in_valid=0; sample_in=0; @(posedge clk); #1; if(out_valid!==0 || $signed(sample_out)!={previous}) $fatal(1,"valid-gap failure"); @(negedge clk);')
    return f'''module tb;
logic clk=0, rst=1, in_valid=0; logic signed [{width-1}:0] sample_in=0;
wire out_valid; wire signed [31:0] sample_out;
{module} dut(.*); always #5 clk=~clk;
initial begin
 repeat(2) @(posedge clk); @(negedge clk); rst=0;
 {' '.join(rows)}
 $display("RTL_PASS samples={len(samples)}"); $finish;
end
initial begin #100000; $fatal(1,"simulation timeout"); end
endmodule
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', type=Path)
    args = parser.parse_args()
    for tool in ('clang++', 'iverilog', 'vvp'):
        if not shutil.which(tool):
            raise SystemExit(f'{tool} is required')
    temporary = tempfile.TemporaryDirectory(prefix='flowforge-') if not args.build_dir else None
    directory = args.build_dir.resolve() if args.build_dir else Path(temporary.name)
    directory.mkdir(parents=True, exist_ok=True)
    executable = directory / 'flowforge'
    run(['clang++', '-std=c++17', '-g', '-Wall', '-Wextra', '-Wpedantic',
         '-fsanitize=address,undefined', '-fno-omit-frame-pointer', ROOT/'src/main.cpp', '-o', executable])
    invalid_specs = [
        '', 'fir bad\nwidth 7\ntaps 1', 'fir bad\nwidth 17\ntaps 1',
        'fir bad\nwidth 8\ntaps', 'fir bad\nwidth 8\ntaps 128',
        'fir bad\nwidth 8\ntaps -129', 'fir bad\nwidth 8\ntaps x',
        'fir bad\nwidth 8\nwidth 9\ntaps 1', 'fir a\nfir b\nwidth 8\ntaps 1',
        'fir bad\nwidth 8\ntaps 1\ntaps 2', 'fir ../../bad\nwidth 8\ntaps 1',
        'fir bad\nwidth 8\ntaps ' + ' '.join(['1']*17),
        'fir bad\nwidth 9999999999999\ntaps 1', 'fir bad\nwidth 8\nunknown 1\ntaps 1',
    ]
    for index, text in enumerate(invalid_specs):
        spec = directory/f'invalid-{index}.fir'; spec.write_text(text)
        result = subprocess.run([executable, 'compile', spec, directory/'invalid'], capture_output=True, text=True, timeout=30)
        if result.returncode != 1 or 'flowforge:' not in result.stderr:
            raise AssertionError(f'invalid specification {index} was not diagnosed safely: {result.stderr}')
    cases = samples_checked = rtl_samples = baseline_ops = optimized_ops = 0
    for width in (8, 12, 16):
        for coefficients in ([1], [1, 0, -1, 2, -3, 0, 1, 4], [-128, 127]*8, [0]*4):
            case = directory/f'w{width}_n{len(coefficients)}_{coefficients[0]}'
            case.mkdir(exist_ok=True)
            spec = case/'input.fir'
            spec.write_text(f'fir filter\nwidth {width}\ntaps ' + ' '.join(map(str, coefficients)) + '\n')
            limit = 1 << (width-1); rng = random.Random(width*100+len(coefficients))
            samples = [0, 1, -1, limit-1, -limit] * 5 + [rng.randrange(-limit, limit) for _ in range(487)]
            reset_at = len(samples)//2
            expected = golden(coefficients, samples[:reset_at]) + golden(coefficients, samples[reset_at:])
            for segment in (samples[:reset_at], samples[reset_at:]):
                path = case/'samples.txt'; path.write_text('\n'.join(map(str, segment)))
                actual = list(map(int, run([executable, 'model', spec, path]).stdout.split()))
                assert actual == golden(coefficients, segment), 'C++/Python model mismatch'
                samples_checked += len(segment)
            for optimize in (False, True):
                out = case/('optimized' if optimize else 'baseline')
                run([executable, 'compile', spec, out] + ([] if optimize else ['--baseline']))
                ir = json.loads((out/'ir.json').read_text())
                assert ir['taps'] == list(coefficients) and ir['input_bits'] == width
                if optimize: optimized_ops += ir['source_multiply_operators']
                else: baseline_ops += ir['source_multiply_operators']
                tb = out/'tb.sv'; tb.write_text(bench(width, coefficients, samples, expected, 'ff_filter', reset_at))
                simulation = out/'simulation'
                run(['iverilog', '-g2012', '-s', 'tb', '-o', simulation, out/'filter.sv', tb])
                result = run(['vvp', simulation])
                assert 'RTL_PASS samples=512' in result.stdout
                rtl_samples += len(samples)
            cases += 1
    # Validate data-path boundaries and missing input diagnostics independently.
    spec = directory/'boundary.fir'; spec.write_text('fir boundary\nwidth 8\ntaps 1\n')
    path = directory/'out-of-range.txt'; path.write_text('128\n')
    result = subprocess.run([executable, 'model', spec, path], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1 and 'outside' in result.stderr
    result = subprocess.run([executable, 'compile', directory/'missing.fir', directory/'missing'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1 and 'cannot open' in result.stderr
    summary = {'configurations': cases, 'invalid_specs_rejected': len(invalid_specs),
               'boundary_error_checks': 2, 'cpp_python_samples': samples_checked,
               'rtl_samples_baseline_and_optimized': rtl_samples,
               'baseline_source_multiply_operators': baseline_ops,
               'optimized_source_multiply_operators': optimized_ops,
               'source_multiply_operators_removed': baseline_ops-optimized_ops}
    print(json.dumps(summary, indent=2))
    if temporary: temporary.cleanup()

if __name__ == '__main__':
    main()
