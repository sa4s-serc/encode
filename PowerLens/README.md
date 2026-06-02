# PowerLens

**A novel measurement methodology for sub-millisecond, block-level energy profiling of Python code.**

> **Research Software**: PowerLens is part of the EnCoDe framework, developed for academic research in energy-aware software engineering. This is an unpublished working draft submitted for peer review.

## Overview

PowerLens is the fine-grained energy measurement infrastructure developed as part of the **EnCoDe** (Energy Estimation of Source Code At Design-Time) framework. It addresses a fundamental challenge in software energy measurement: **how to reliably measure the energy consumption of code blocks that execute faster than hardware counter update intervals.**

### The Problem

Standard energy profiling tools rely on Intel RAPL (Running Average Power Limit), which updates at ~1ms granularity. However, many code blocks—individual loops, conditionals, and small functions—execute in microseconds. This mismatch causes:
- **High variance**: >110% coefficient of variation for sub-millisecond workloads
- **Zero readings**: 40-50% of measurements return zero for microsecond-scale blocks
- **No ground truth**: Inability to build datasets for design-time energy modeling

### The Solution

PowerLens overcomes these limitations through four coordinated mechanisms:
1. **Execution Amplification**: Repeats blocks N times to amplify energy signal above noise floor
2. **Temporal Synchronization**: Aligns measurements with RAPL update boundaries
3. **Calibrated Subtraction**: Removes measurement overhead through pre-calibration
4. **Statistical Aggregation**: Ensures reproducibility through multi-trial averaging

This enables reliable energy measurements for blocks as small as a few microseconds, achieving **>90% stability** (coefficient of variation <10%) across the dataset.

## Key Features

- **Sub-millisecond granularity**: Reliable energy measurements for code blocks executing in microseconds
- **Execution amplification**: Amplifies energy signatures by repeating code blocks to make them observable above RAPL's millisecond resolution
- **Temporal synchronization**: Aligns measurements with RAPL counter update boundaries to eliminate contamination from unrelated processes
- **Calibrated subtraction**: Removes measurement overhead through pre-calibrated padding loop energy costs
- **Statistical stability**: Achieves >90% of blocks with <10% variation through multi-trial aggregation and outlier removal
- **SMM interference mitigation**: Waits for System Management Mode execution to avoid measurement noise
- **Dual access modes**: Supports both MSR (root) and powercap (non-root) interfaces
- **Validated accuracy**: Measurements validated against PyRAPL with lower variance and higher stability

## Architecture

PowerLens consists of two main components:

1. **`_powerlens_core.c`**: Low-level C extension module providing:
   - Direct MSR register access (`/dev/cpu/*/msr`) for RAPL energy counters
   - Fallback to powercap interface (`/sys/class/powercap/intel-rapl`)
   - Core measurement primitives: `read_energy_aligned()`, `read_energy_aligned_end()`, `wait_for_smm()`
   - Calibration routine: `calibrate()` for determining energy units and loop overhead
   - Optimized with `-O3` compilation flag for minimal measurement perturbation

2. **`powerlens.py`**: High-level Python API providing:
   - Automatic calibration on import with linear regression for loop energy costs
   - Context managers (`ContextManager`, `TinyBlockContext`) for block measurement
   - Decorators (`@measure_energy`, `@measure_function_energy`) for function instrumentation
   - Statistical aggregation and outlier filtering (IQR method)
   - Utility functions for CPU pinning and frequency control
   - Multiple measurement modes (single execution, repeated execution, amplified execution)

## Requirements

### Hardware
- Intel CPU with RAPL support (Sandy Bridge or newer, tested on Intel i7-6700K)
- Minimum 8 GB RAM (16 GB recommended for large-scale measurements)

### Software
- Linux operating system (tested on Pop!_OS 22.04, Ubuntu 22.04)
- Python 3.6 or higher (tested with Python 3.12)
- GCC compiler with C99 support

### Permissions
- Root access for MSR interface (preferred for lowest overhead)
- OR readable `/sys/class/powercap/intel-rapl` for non-root users

### Enabling MSR Access (Recommended)

```bash
# Load MSR kernel module
sudo modprobe msr

# Verify MSR access
ls /dev/cpu/0/msr
```

For non-root users, the powercap interface should be readable by default on most systems. PowerLens will automatically fall back to powercap if MSR access is unavailable.

### Recommended System Configuration

For best measurement stability:

```bash
# Disable CPU frequency scaling (set to performance mode)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Disable Turbo Boost
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo

# Minimize background processes
# Close unnecessary applications and services
```

PowerLens can automate some of these settings programmatically using the `pin_to_cpu()` and `set_cpu_frequency()` utility functions.

## Installation

```bash
python setup.py build
python setup.py install
```

Or for development:

```bash
python setup.py develop
```

## Usage

### When to Use PowerLens

PowerLens is designed for:
- **Research**: Creating ground-truth energy datasets for machine learning models
- **Fine-grained profiling**: Measuring energy at the code block level (functions, loops, conditionals)
- **Comparative analysis**: Comparing energy efficiency of different implementations
- **Microsecond-scale workloads**: Measuring blocks too fast for standard RAPL tools

PowerLens is **not** designed for:
- Real-time production monitoring (use process-level tools instead)
- Distributed system profiling (single-machine focus)
- Non-Intel platforms (RAPL dependency)

### Basic Context Manager

```python
import powerlens

with powerlens.measure_energy() as measurement:
    # Your code here
    result = sum(range(1000000))

print(f"Energy consumed: {measurement.joules} J")
print(f"Energy consumed: {measurement.millijoules} mJ")
```

### With Time Tracking

```python
with powerlens.measure_energy(track_time=True) as measurement:
    # Your code here
    result = sum(range(1000000))

print(f"Energy: {measurement.joules} J")
print(f"Duration: {measurement.duration_seconds} s")
print(f"Average Power: {measurement.watts} W")
```

### Function Decorator

```python
@powerlens.measure_energy(track_time=True)
def compute_something():
    return sum(range(1000000))

result, measurement = compute_something()
print(f"Result: {result}")
print(f"Energy: {measurement.joules} J")
```

### Measuring Tiny Code Blocks

For code that executes faster than the RAPL update interval (~1ms):

```python
# Measure a very small operation by repeating it
energy = powerlens.measure_tiny_energy(
    lambda: x + y,
    repetitions=10000
)
print(f"Energy per execution: {energy.joules} J")
```

Or using a context manager:

```python
with powerlens.measure_tiny_block(repetitions=10000) as block:
    result = block(lambda: sum(range(100)))

print(f"Energy per execution: {block.joules} J")
```

### Advanced: Function Instrumentation

```python
@powerlens.measure_function_energy(
    block_id="my_function_id",
    block_type="FunctionDef",
    repetitions=1000
)
def my_function(x, y):
    return x + y

result = my_function(10, 20)
# Metrics automatically saved to block_metrics_powerlens_my_function_id.json
```

## How It Works

PowerLens operates through four coordinated mechanisms to achieve reliable sub-millisecond energy measurements:

### 1. Environmental Stabilization
Ensures measurements are isolated from system noise by:
- Setting CPU frequency scaling governor to performance mode
- Disabling Turbo Boost
- Pinning the measurement process to a single CPU core
- Minimizing background processes

This ensures measured energy is attributable to the code block itself, not random system events.

### 2. Execution Amplification
Makes imperceptible energy signals measurable by:
- Wrapping target blocks in a tight loop and executing N times (typically 1000)
- Amplifying total energy to a level clearly above RAPL's millisecond-scale resolution
- Computing per-execution energy as: Ê(b) = E_total(b,N) / N

For example, a block consuming 4×10⁻⁸ J per execution becomes measurable at 0.04 J total when repeated 1000 times.

### 3. Temporal Synchronization
Aligns execution with RAPL sampling windows to eliminate contamination:
- Waits for RAPL counter value to change before starting execution (t₀ = min{t > tₛ | Mᵢ₊₁ > Mᵢ})
- Ensures captured energy is attributable only to the target block
- Prevents "unwanted" energy from unrelated computations

### 4. Calibrated Subtraction
Removes measurement overhead:
- Pre-calibrates the energy cost of padding loops: E_pad(δt)
- Subtracts padding overhead from total measured energy
- Final per-execution energy: E_net(b) = (E_total(b,N) - E_pad(δt)) / N

### 5. Statistical Aggregation
Ensures reproducibility:
- Repeats entire measurement process 10 times
- Filters outliers using Interquartile Range (IQR) method
- Returns mean of stable, non-outlier observations: Ē(b) = (1/|Ω(b)|) Σᵢ∈Ω(b) E_net⁽ⁱ⁾(b)

## API Reference

### Main Functions

- `measure_energy(func=None, track_time=False, calibrate=False)`: Decorator/context manager for energy measurement
- `measure_tiny_energy(func, repetitions=1000, track_time=True)`: Measure very small code blocks
- `measure_tiny_block(repetitions=1000, track_time=True)`: Context manager for tiny blocks
- `measure_function_energy(block_id, block_type='FunctionDef', repetitions=1000)`: Decorator for function instrumentation

### Utility Functions

- `pin_to_cpu(cpu_id=0)`: Pin process to specific CPU core for stable measurements

### Classes

- `powerlensMeasurement`: Holds measurement results with `.joules`, `.millijoules`, and `.watts` properties
- `ContextManager`: Context manager for energy measurement
- `TinyBlockContext`: Context manager for measuring tiny code blocks with repetition

## Technical Details

### Measurement Challenge

Standard RAPL-based tools fail for fine-grained measurements:
- **RAPL update interval**: ~1ms (millisecond granularity)
- **Code block execution time**: Often in microseconds (sub-millisecond)
- **Result**: Workloads under 1ms show >110% coefficient of variation and 4-5 zero readings out of 10 runs

PowerLens solves this through execution amplification and synchronization.

### RAPL Interface

PowerLens accesses RAPL energy counters through:
- **MSR registers** (requires root): Direct access via `/dev/cpu/*/msr` using register 0x611 (MSR_PKG_ENERGY_STATUS)
- **Powercap interface** (non-root): Access via `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`

### Energy Domains

Current implementation focuses on:
- **Package (PKG)**: Total processor package energy (MSR 0x611)

Supported in code but not yet exposed:
- **Core (PP0)**: Core energy (MSR 0x639)
- **Uncore (PP1)**: Uncore/GPU energy (MSR 0x641)
- **DRAM**: Memory energy (MSR 0x619)

### Measurement Precision & Validation

**Precision:**
- RAPL update interval: ~1ms (varies by CPU)
- Energy unit: Typically 61.035 μJ (2⁻¹⁴ J, read from MSR 0x606 bits 8:12)
- Counter width: 32 bits with wraparound handling
- Achievable granularity: Microsecond-scale blocks through amplification

**Validation Results:**
- **Stability**: >90% of blocks exhibit <10% variation across repeated trials
- **Dynamic range**: Six orders of magnitude (2.41×10⁻⁵ J to 6.36×10² J)
- **Accuracy**: Aggregate block measurements match PyRAPL program-level measurements
- **Variance**: Substantially lower variance than standard RAPL readings for small blocks

## Limitations

### Platform Constraints
- **Operating System**: Linux only (tested on Pop!_OS 22.04, Ubuntu-based)
- **CPU Architecture**: Intel CPUs with RAPL support (Sandy Bridge or newer)
- **Python Version**: Python 3.6 or higher (tested with Python 3.12)

### Measurement Scope
- **Energy domains**: Package-level (CPU) measurements; does not include I/O, network, or storage
- **Thread isolation**: Does not isolate single-threaded energy or model inter-thread interactions
- **Input scaling**: Does not model how energy scales with different input sizes or runtime states
- **Distributed systems**: Not designed for distributed execution patterns

### Methodological Assumptions
- **Linear scaling**: Assumes energy scales linearly with repetitions (N)
- **Amplification factor**: Default N=1000 may not be optimal for all block sizes
- **CPU pinning**: Execution pinned to single core for stability; does not capture multi-threading effects
- **RAPL accuracy**: Inherits RAPL's inherent measurement errors (~1-5% typical)

### Practical Considerations
- **Minimum measurable time**: Best suited for blocks that execute in microseconds or longer
- **Measurement overhead**: Each measurement takes several milliseconds due to synchronization and repetition
- **Root access**: MSR interface requires root; falls back to powercap for non-root users
- **System stabilization**: Requires CPU governor control and process pinning for best accuracy

## Experimental Setup & Validation

### Hardware Configuration
- **CPU**: Intel Core i7-6700K (Skylake, 4 cores @ base 4.0 GHz)
- **RAM**: 16 GB DDR4
- **OS**: Pop!_OS 22.04 LTS (64-bit, Linux kernel with MSR support)

### Environment Stabilization
All measurements were conducted under controlled conditions:
- CPU frequency governor set to **performance** (no dynamic scaling)
- Turbo Boost **disabled**
- Process **pinned to CPU core 0**
- Background processes **minimized**
- MSR kernel module loaded for direct RAPL access

### Validation Results
PowerLens was validated on 18,612 Python programs:
- **Stability**: >90% of blocks show coefficient of variation <10%
- **Dynamic range**: Successfully measures from 2.41×10⁻⁵ J (24.1 μJ) to 6.36×10² J (636 J)
- **Accuracy**: Aggregated block measurements match PyRAPL program-level measurements
- **Variance reduction**: Substantially lower variance than raw RAPL for sub-millisecond blocks

### Dataset

PowerLens was used to create a fine-grained energy dataset containing:
- **18,612** Python source files (from HuggingFace `iamtarun/python_code_instructions_18k_alpaca`)
- **14,000+** executable code blocks (FunctionDef, For, While, If, Try, With)
- Energy measurements spanning **six orders of magnitude** 
- **33 static code features** per block:
  - Basic metrics (5): AST node count, depth
  - Complexity metrics (4): Cyclomatic, cognitive complexity
  - Density metrics (5): Operator density, literal density
  - Diversity metrics (6): Operator entropy, vocabulary
  - Structural metrics (3): Branching factor, nesting
  - Code pattern metrics (5): Loop count, conditional count
  - Halstead metrics (5): Program volume, effort

This dataset enables design-time energy estimation through machine learning models trained on the relationship between code structure and energy consumption.

## Comparison with Existing Tools

| Tool | Granularity | Min. Measurable Time | Stability | Platform |
|------|-------------|---------------------|-----------|----------|
| **PowerLens** | Code block (function, loop, conditional) | Microseconds (with amplification) | >90% blocks <10% CV | Intel RAPL (Linux) |
| PyRAPL | Process/function | ~1ms | High variance for <1ms blocks | Intel RAPL (Linux) |
| ALEA | Basic block (embedded) | Microseconds | High (instruction-level) | Embedded systems only |
| perf | Process/thread | ~1ms | Moderate | Linux (various counters) |
| GreenPy | Application-level | Seconds | Moderate | Cross-platform |

**PowerLens advantages:**
- Handles sub-millisecond blocks through execution amplification
- Validated stability (>90% blocks with CV <10%)
- Python-native API with minimal code changes
- Automatic calibration and overhead removal

**PowerLens trade-offs:**
- Requires repeated execution (not suitable for side-effect-heavy code)
- Single-machine, Intel-only
- Higher measurement overhead per block (~10ms including repetitions)

## Research Context

PowerLens is the measurement infrastructure for the **EnCoDe** (Energy Estimation of Source Code At Design-Time) framework. While PowerLens handles runtime measurement, EnCoDe uses these measurements to train machine learning models that predict block-level energy consumption from static code features alone—enabling energy-aware development without execution.

**EnCoDe Framework Pipeline:**
1. **PowerLens** (this tool): Measures ground-truth energy for code blocks
2. **Feature Extraction**: Extracts 33 static features from Abstract Syntax Trees (AST)
3. **Machine Learning**: Trains regression and classification models
4. **Design-Time Inference**: Predicts energy from source code alone (no execution needed)

**Key Results from EnCoDe:**
- **Regression**: R² = 0.877 for predicting absolute energy values (Gradient Boosting)
- **Classification**: 68.6% accuracy for identifying energy hotspots in low/medium/high tiers (XGBoost)
- **Interpretability**: No single feature dominates; energy emerges from interactions among complexity, density, and structural metrics
- **Practical impact**: Enables "lint-like" energy feedback during development, before compilation

## Contributing

This is research software developed for academic study. For questions, issues, or collaboration inquiries, please refer to the associated research paper or contact the authors through the repository.


**Note**: This is an unpublished working draft submitted for peer review. Citation details will be updated upon acceptance and publication.

## Authors

Anonymous 

## Future Work

Based on the EnCoDe research, several extensions are planned:

### Near-term
- **Multi-language support**: Extend beyond Python to JavaScript, Java, C++
- **Additional energy domains**: Expose DRAM, Core (PP0), and Uncore (PP1) measurements
- **Adaptive amplification**: Automatically determine optimal repetition count N per block
- **IDE integration**: Real-time energy feedback in VSCode, PyCharm

### Long-term
- **ARM support**: Extend to ARM energy counters for mobile/embedded devices
- **GPU profiling**: Integrate NVIDIA/AMD GPU energy measurement
- **Distributed measurements**: Support for multi-node, distributed systems
- **Automated refactoring**: Suggest energy-efficient code transformations
- **ML model energy**: Apply block-level analysis to neural network training code

### Research Directions
- **Energy-aware compilation**: Guide compiler optimizations using block-level energy profiles
- **Cross-platform models**: Predict energy across different hardware configurations
- **Energy anomaly detection**: Identify unexpected energy hotspots during development
- **Sustainability metrics**: Integrate with carbon intensity APIs for environmental impact

## Acknowledgments

This work is part of ongoing research in energy-aware software engineering and sustainable computing. PowerLens addresses a fundamental measurement granularity gap identified in prior work: existing tools operate at application or method-level granularity and cannot reliably profile microsecond-scale code constructs. By enabling fine-grained, block-level energy measurements, PowerLens makes it possible to:

1. **Shift energy assessment from runtime to design-time**: Developers can reason about energy early in the development lifecycle
2. **Treat energy as a first-class quality attribute**: Alongside performance, maintainability, and security
3. **Enable data-driven energy optimization**: Ground-truth measurements support evidence-based refactoring decisions
4. **Align with Green AI principles**: Uses lightweight, interpretable models rather than energy-intensive deep learning

PowerLens demonstrates that energy efficiency need not be a retroactive afterthought—it can be proactively addressed during code construction, code review, and design decisions.
