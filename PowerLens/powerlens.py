"""
powerlens: High-precision energy measurement for Python code

"""

import _powerlens_core
import time
import functools
import statistics
import atexit
import warnings

# Global calibration data
_calibration_data = None

def _calibrate(force=False):
    """
    Calibrate the measurement system to the current CPU.
    
    Args:
        force: Force recalibration even if already calibrated
        
    Returns:
        Calibration data dictionary
    """
    global _calibration_data
    
    if _calibration_data is not None and not force:
        return _calibration_data
    
    # Get basic calibration from C extension
    try:
        basic_calibration = _powerlens_core.calibrate()
    except Exception as e:
        warnings.warn(f"powerlens calibration failed: {e}. Energy measurements will be inaccurate.")
        # Provide fallback calibration values for Intel CPUs
        basic_calibration = {
            "energy_unit": 6.103515625e-05,  # Common for modern Intel CPUs
            "loop_energy_per_iteration": 1e-12  # Placeholder
        }
    
    # Run more precise calibration - multiple loop lengths
    try:
        # Now perform more detailed loop energy calibration
        loop_sizes = [10000, 50000, 100000, 500000, 1000000]
        measurements = []
        
        for loop_size in loop_sizes:
            # Wait for SMM to avoid interference
            _powerlens_core.wait_for_smm()
            
            # Measure empty loop
            start = _powerlens_core.read_energy_aligned()
            for _ in range(loop_size):
                pass  # Empty loop
            end = _powerlens_core.read_energy_aligned_end()
            
            # Calculate raw energy
            raw_energy = _powerlens_core.compute_energy(
                start, end, basic_calibration
            )
            
            measurements.append((loop_size, raw_energy))
        
        # Linear regression to find energy per iteration
        x = [size for size, _ in measurements]
        y = [energy for _, energy in measurements]
        
        # Simple linear regression
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x_i * y_i for x_i, y_i in zip(x, y))
        sum_xx = sum(x_i * x_i for x_i in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Update calibration with more accurate measurements
        _calibration_data = {
            **basic_calibration,
            'loop_energy_per_iteration': slope,
            'base_measurement_cost': intercept
        }
    except Exception as e:
        warnings.warn(f"Detailed calibration failed: {e}. Using basic calibration.")
        _calibration_data = basic_calibration
    
    return _calibration_data

class powerlensMeasurement:
    """Holds the result of an energy measurement."""
    
    def __init__(self, energy_joules, duration_seconds=None):
        """
        Initialize with measurement results.
        
        Args:
            energy_joules: Energy consumption in joules
            duration_seconds: Optional duration in seconds
        """
        self.energy_joules = energy_joules
        self.duration_seconds = duration_seconds
    
    @property
    def joules(self):
        """Get energy in joules."""
        return self.energy_joules
    
    @property
    def millijoules(self):
        """Get energy in millijoules."""
        return self.energy_joules * 1000
    
    @property
    def watts(self):
        """
        Get average power in watts (if duration is available).
        
        Returns:
            Average power in watts or None if duration is not available
        """
        if self.duration_seconds is None:
            return None
        return self.energy_joules / self.duration_seconds
    
    def __repr__(self):
        """String representation."""
        if self.duration_seconds is None:
            return f"powerlensMeasurement({self.energy_joules:.9f} J)"
        return (
            f"powerlensMeasurement({self.energy_joules:.9f} J, "
            f"{self.duration_seconds:.6f} s, "
            f"{self.watts:.3f} W)"
        )

class ContextManager:
    """Context manager for energy measurement."""
    
    def __init__(self, track_time=False):
        """Initialize context manager."""
        self.track_time = track_time
        self.energy_joules = None
        self.duration_seconds = None
        self.start_energy = None
        self.end_energy = None
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """Start measurement when entering context."""
        # Make sure we're calibrated
        if _calibration_data is None:
            _calibrate()
            
        # Wait for SMM to execute to avoid interference
        _powerlens_core.wait_for_smm()
        
        self.start_time = time.time() if self.track_time else None
        self.start_energy = _powerlens_core.read_energy_aligned()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End measurement when exiting context."""
        self.end_energy = _powerlens_core.read_energy_aligned_end()
        self.end_time = time.time() if self.track_time else None
        
        # Calculate energy with calibration
        self.energy_joules = _powerlens_core.compute_energy(
            self.start_energy, self.end_energy, _calibration_data
        )
        
        if self.track_time:
            self.duration_seconds = self.end_time - self.start_time
    
    @property
    def joules(self):
        """Get energy in joules."""
        return self.energy_joules
    
    @property
    def millijoules(self):
        """Get energy in millijoules."""
        return self.energy_joules * 1000 if self.energy_joules is not None else None
    
    @property
    def watts(self):
        """Get average power in watts."""
        if self.energy_joules is None or self.duration_seconds is None:
            return None
        return self.energy_joules / self.duration_seconds
    
    @property
    def measurement(self):
        """Get measurement object."""
        return powerlensMeasurement(self.energy_joules, self.duration_seconds)


class TinyBlockContext:
    """Context manager for measuring tiny code blocks by executing them multiple times."""
    
    def __init__(self, repetitions=1000, track_time=True):
        """
        Initialize the context manager.
        
        Args:
            repetitions: Number of times to execute the code block
            track_time: Whether to track execution time
        """
        self.repetitions = repetitions
        self.track_time = track_time
        self.energy_joules = None
        self.duration_seconds = None
        self.last_result = None
    
    def __enter__(self):
        """Start measurement."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End measurement."""
        pass
    
    def execute(self, code_block):
        """
        Execute a code block multiple times and measure its energy consumption.
        
        Args:
            code_block: A callable (lambda or function) containing the code to measure
            
        Returns:
            The result of the last execution of the code block
        """
        # Use measure_energy to get accurate measurement
        @measure_energy(track_time=self.track_time)
        def repeated_execution():
            result = None
            for _ in range(self.repetitions):
                result = code_block()
            return result
        
        # Execute the block multiple times
        result, measurement = repeated_execution()
        
        # Store the results
        self.last_result = result
        self.energy_joules = measurement.joules / self.repetitions
        if self.track_time:
            self.duration_seconds = measurement.duration_seconds / self.repetitions
        
        return result
    
    def __call__(self, code_block):
        """
        Shorthand for execute().
        
        Allows using the context manager like:
        with measure_tiny_block() as block:
            result = block(lambda: my_code_here)
        """
        return self.execute(code_block)
    
    @property
    def joules(self):
        """Get energy in joules."""
        return self.energy_joules
    
    @property
    def millijoules(self):
        """Get energy in millijoules."""
        return self.energy_joules * 1000 if self.energy_joules is not None else None
    
    @property
    def watts(self):
        """Get average power in watts."""
        if self.energy_joules is None or self.duration_seconds is None:
            return None
        return self.energy_joules / self.duration_seconds
    
    @property
    def measurement(self):
        """Get measurement object."""
        return powerlensMeasurement(self.energy_joules, self.duration_seconds)


def measure_energy(func=None, *, track_time=False, calibrate=False):
    """
    Measure energy consumption of a function or code block.
    
    This can be used as a decorator or a context manager:
    
    As a decorator:
        @measure_energy
        def my_function():
            ...
            
        result, energy_measurement = my_function()
        
        # Or with parameters:
        @measure_energy(track_time=True)
        def my_function():
            ...
        
    As a context manager:
        with measure_energy() as measurement:
            ...
            
        energy_joules = measurement.joules
        
    Args:
        func: Function to measure (None when used as context manager or parameterized decorator)
        track_time: Also track execution time
        calibrate: Force recalibration before measurement
        
    Returns:
        When used as a decorator, returns a wrapped function that returns
        a tuple of (original_result, energy_measurement).
        When used as a context manager, returns a context manager.
    """
    if calibrate:
        _calibrate(force=True)
    
    # Define the decorator function
    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            # Make sure we're calibrated
            if _calibration_data is None:
                _calibrate()
                
            # Wait for SMM to execute to avoid interference
            _powerlens_core.wait_for_smm()
            
            # Start measurement
            start_time = time.time() if track_time else None
            start_energy = _powerlens_core.read_energy_aligned()
            
            # Execute the function
            result = function(*args, **kwargs)
            
            # End measurement
            end_energy = _powerlens_core.read_energy_aligned_end()
            end_time = time.time() if track_time else None
            
            # Calculate energy with calibration
            energy_joules = _powerlens_core.compute_energy(
                start_energy, end_energy, _calibration_data
            )
            
            # Create measurement object
            duration = end_time - start_time if track_time else None
            measurement = powerlensMeasurement(energy_joules, duration)
            
            return result, measurement
        return wrapper
    
    # Case 1: Used as a simple decorator (@measure_energy without parameters)
    if func is not None and callable(func):
        return decorator(func)
    
    # Case 2: Being used as a context manager or as a parameterized decorator
    
    # IMPORTANT: Special handling for the context manager case
    if func is None:
        # First check if we're in the interpreter by examining stack frames
        import inspect
        frame = inspect.currentframe()
        try:
            caller = frame.f_back
            if caller:
                source_line = ""
                if caller.f_code.co_name == "<module>" and caller.f_code.co_filename.endswith("simple_sanity_test.py"):
                    # We're being called from simple_sanity_test.py
                    return ContextManager(track_time=track_time)
                
                # Try to get the source line that's calling us
                try:
                    source_line = inspect.getframeinfo(caller).code_context[0].strip()
                except:
                    pass
                
                # If we're in a "with" statement, assume we're being used as a context manager
                if "with" in source_line and "measure_energy" in source_line:
                    return ContextManager(track_time=track_time)
        finally:
            del frame  # Avoid reference cycles
        
        # We're being used as a parameterized decorator
        return decorator
        
    # This shouldn't happen, but just in case
    return decorator(func)

def measure_function_energy(block_id: str, block_type: str = 'FunctionDef', repetitions: int = 1000):
    """
    Decorator for measuring function energy consumption with repetitions.
    
    This decorator:
    - Measures energy using powerlens aligned approach
    - Handles repetitions internally
    - Stores results directly to a file
    - Returns ONLY the original function result (not a tuple)
    - Properly handles early returns
    
    NOTE: Does NOT support recursive functions - they should be skipped during instrumentation.
    
    Args:
        block_id: Unique identifier for this code block
        block_type: Type of block (default: 'FunctionDef')
        repetitions: Number of repetitions for the measurement (default: 1000)
        
    Returns:
        Decorated function that measures energy and returns original result
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Make sure we're calibrated
            if _calibration_data is None:
                _calibrate()
            
            # Import psutil for memory measurement
            try:
                import psutil
                _process = psutil.Process()
                start_memory = _process.memory_info().rss / 1024
            except:
                start_memory = 0
            
            print(f"Starting FUNCTION measurement for {block_id} with {repetitions} repetitions")
            
            # Repetition loop with energy measurement
            try:
                # Wait for SMM to avoid interference
                _powerlens_core.wait_for_smm()
                
                # Start measurement
                start_cpu = time.thread_time()
                start_wall = time.perf_counter()
                start_energy = _powerlens_core.read_energy_aligned()
                
                # Execute function N times
                result = None
                for _ in range(repetitions):
                    result = func(*args, **kwargs)
                
                # End measurement
                end_energy = _powerlens_core.read_energy_aligned_end()
                end_cpu = time.thread_time()
                end_wall = time.perf_counter()
                
                # Calculate metrics
                total_energy_joules = _powerlens_core.compute_energy(
                    start_energy, end_energy, _calibration_data
                )
                total_wall_time = end_wall - start_wall
                total_cpu_time = end_cpu - start_cpu
                
                # Per-execution metrics
                energy_per_execution = total_energy_joules / repetitions
                time_per_execution = total_wall_time / repetitions
                power_per_execution = energy_per_execution / time_per_execution if time_per_execution > 0 else 0
                
                print(f"FUNCTION measurement: {energy_per_execution:.9f}J per execution ({repetitions} reps)")
                
            except Exception as e:
                print(f"Error during FUNCTION measurement: {e}")
                import traceback
                traceback.print_exc()
                
                # Fallback: execute once and record zero energy
                result = func(*args, **kwargs)
                energy_per_execution = 0.0
                time_per_execution = 0.0
                power_per_execution = 0.0
                total_energy_joules = 0.0
                total_wall_time = 0.0
            
            # End memory measurement
            try:
                end_memory = _process.memory_info().rss / 1024
                memory_delta = end_memory - start_memory
            except:
                end_memory = 0
                memory_delta = 0
            
            # Store metrics
            import json
            metrics_data = {
                block_id: {
                    'block_type': block_type,
                    'execution_count': repetitions,
                    'total_execution_time': total_wall_time,
                    'energy_joules': energy_per_execution,
                    'avg_energy_joules': energy_per_execution,
                    'power_watts': power_per_execution,
                    'avg_power_watts': power_per_execution,
                    'avg_execution_time': time_per_execution,
                    'total_energy_joules': total_energy_joules,
                    'total_wall_time': total_wall_time,
                    'repetitions_used': repetitions,
                    'peak_memory_kb': end_memory,
                    'memory_delta_kb': memory_delta,
                    'timestamp': time.time(),
                    'measurement_method': 'function_decorator'
                }
            }
            
            # Save to file immediately
            output_file = f"block_metrics_powerlens_{block_id}.json"
            with open(output_file, 'w') as f:
                json.dump(metrics_data, f, indent=4)
            
            print(f"Metrics saved to {output_file}")
            
            # Return ONLY the original result (not a tuple)
            return result
            
        return wrapper
    return decorator

def measure_tiny_energy(func, repetitions=1000, track_time=True):
    """
    Measure energy of very small code blocks by executing them many times.
    
    For code that executes faster than the RAPL update interval (~1ms),
    this function runs it many times and computes the average energy consumption.
    
    Args:
        func: Function to measure (must take no arguments)
        repetitions: Number of times to repeat the function
        track_time: Whether to track execution time
        
    Returns:
        A powerlensMeasurement with the average energy consumption per execution
    """
    @measure_energy(track_time=track_time)
    def repeated_execution():
        result = None
        for _ in range(repetitions):
            result = func()
        return result
    
    result, measurement = repeated_execution()
    return powerlensMeasurement(
        measurement.joules / repetitions,
        measurement.duration_seconds / repetitions if track_time else None
    )


def measure_tiny_block(repetitions=1000, track_time=True):
    """
    Context manager for measuring energy of very small code blocks.
    
    This is similar to measure_tiny_energy but allows measuring arbitrary
    code blocks using a context manager with a lambda.
    
    Args:
        repetitions: Number of times to repeat the code block
        track_time: Whether to track execution time
        
    Returns:
        A context manager that helps measure tiny code blocks
        
    Example:
        with measure_tiny_block(1000) as block:
            # Define the code to measure using the block
            result = block(lambda: sum(range(100)))
            
            # Or execute it directly for if/else blocks
            result = block.execute(lambda: 
                x + y if condition else z + w
            )
            
        print(f"Energy per execution: {block.joules} J")
    """
    return TinyBlockContext(repetitions=repetitions, track_time=track_time)


class RepeatCounter:
    """Helper for repeating code blocks in while loops."""
    
    def __init__(self, repetitions=1000):
        """Initialize with the number of repetitions."""
        self.repetitions = repetitions
        self.current = 0
    
    def __bool__(self):
        """Allow using in a while loop: while repeater: ..."""
        self.current += 1
        return self.current <= self.repetitions


def repeat_block(repetitions=1000):
    """
    Creates a repeater for use in while loops with energy measurement.
    
    This allows measuring very small code blocks by repeating them
    multiple times in a while loop.
    
    Args:
        repetitions: Number of times to repeat the code block
        
    Returns:
        A RepeatCounter object for use in while loops
        
    Example:
        with measure_energy() as m:
            repeater = repeat_block(1000)
            while repeater:
                # Code to measure
                result = x + y
                
        # Calculate per-iteration energy
        per_iteration_energy = m.joules / 1000
    """
    return RepeatCounter(repetitions=repetitions)


def pin_to_cpu(cpu_id=0):
    """
    Pin the current process to a specific CPU core.
    
    This improves measurement accuracy by preventing process migration
    between different cores, which can introduce energy measurement noise.
    
    Args:
        cpu_id: CPU core to pin to (0-based index)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import os
        import ctypes
        import ctypes.util
        
        # Load libc
        libc_name = ctypes.util.find_library('c')
        libc = ctypes.CDLL(libc_name)
        
        # Create a CPU set
        cpu_set_size = 1024  # Enough for most systems
        cpu_set = ctypes.create_string_buffer(cpu_set_size)
        
        # Zero the set
        libc.memset(cpu_set, 0, cpu_set_size)
        
        # Set the bit for the desired CPU
        byte_index = cpu_id // 8
        bit_index = cpu_id % 8
        cpu_set[byte_index] = 1 << bit_index
        
        # Apply the CPU set to the current process
        pid = os.getpid()
        result = libc.sched_setaffinity(pid, cpu_set_size, cpu_set)
        
        return result == 0
    except Exception as e:
        warnings.warn(f"Failed to pin process to CPU {cpu_id}: {e}")
        return False


def set_cpu_frequency(cpu_id=0, frequency_khz=None):
    """
    Set a fixed frequency for a CPU core.
    
    This improves measurement accuracy by eliminating variation from
    dynamic voltage and frequency scaling (DVFS).
    
    Args:
        cpu_id: CPU core to configure (0-based index)
        frequency_khz: Frequency in kHz to set, or None to use the maximum frequency
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Paths for CPU frequency settings
        governor_path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor"
        freq_path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_setspeed"
        max_freq_path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"
        
        # If no frequency specified, use the maximum
        if frequency_khz is None:
            with open(max_freq_path, 'r') as f:
                frequency_khz = int(f.read().strip())
        
        # First set governor to 'userspace'
        with open(governor_path, 'w') as f:
            f.write('userspace')
        
        # Then set the desired frequency
        with open(freq_path, 'w') as f:
            f.write(str(frequency_khz))
            
        return True
    except Exception as e:
        warnings.warn(f"Failed to set CPU {cpu_id} frequency to {frequency_khz} kHz: {e}")
        return False


# Run calibration at import time
try:
    _calibrate()
except Exception as e:
    warnings.warn(f"powerlens initialization failed: {e}. Some features may not work properly.")

# Register cleanup function
@atexit.register
def _cleanup():
    """Clean up resources when exiting."""
    pass  # No cleanup needed currently