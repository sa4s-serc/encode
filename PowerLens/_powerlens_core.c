// _powerlens_core.c - Low-level RAPL access for powerlens
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <string.h>

// Define MSR register addresses for RAPL
#define MSR_RAPL_POWER_UNIT 0x606
#define MSR_PKG_ENERGY_STATUS 0x611
#define MSR_PP0_ENERGY_STATUS 0x639  // Core energy
#define MSR_PP1_ENERGY_STATUS 0x641  // Uncore energy
#define MSR_DRAM_ENERGY_STATUS 0x619 // DRAM energy

// For powercap interface
#define POWERCAP_PATH "/sys/class/powercap/intel-rapl"

// Function to read MSR on a specific CPU
static int read_msr(int cpu, unsigned int reg, uint64_t *val)
{
    char msr_file_name[64];
    int fd;
    ssize_t ret;

    snprintf(msr_file_name, sizeof(msr_file_name), "/dev/cpu/%d/msr", cpu);
    fd = open(msr_file_name, O_RDONLY);
    if (fd < 0)
    {
        if (errno == ENXIO)
        {
            // MSR not supported or CPU offline
            return -1;
        }
        else if (errno == EACCES)
        {
            // Permission denied - need root access
            // Don't throw an error - we'll try powercap instead
            return -1;
        }
        else
        {
            // Other error
            return -1;
        }
    }

    ret = pread(fd, val, sizeof(*val), reg);
    close(fd);

    if (ret != sizeof(*val))
    {
        return -1;
    }

    return 0;
}

// Try to read energy from powercap interface (for non-root users)
static int read_powercap(const char *domain, uint64_t *val)
{
    char energy_file[128];
    FILE *fp;
    unsigned long long energy_uj;

    snprintf(energy_file, sizeof(energy_file),
             "%s/%s/energy_uj", POWERCAP_PATH, domain);

    fp = fopen(energy_file, "r");
    if (!fp)
    {
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, energy_file);
        return -1;
    }

    if (fscanf(fp, "%llu", &energy_uj) != 1)
    {
        fclose(fp);
        PyErr_SetString(PyExc_IOError, "Error parsing energy value");
        return -1;
    }

    fclose(fp);
    *val = energy_uj;
    return 0;
}

// powerlens-style wait for energy counter update
static int wait_for_update(int cpu, uint64_t *value, int *iterations)
{
    uint64_t prev_value, current_value;
    int loop_count = 0;

    // Get initial value
    if (read_msr(cpu, MSR_PKG_ENERGY_STATUS, &prev_value) < 0)
    {
        // Try powercap if MSR fails
        if (read_powercap("intel-rapl:0", &prev_value) < 0)
        {
            return -1;
        }
    }

    // Loop until value changes - indicating an update
    do
    {
        loop_count++;

        if (read_msr(cpu, MSR_PKG_ENERGY_STATUS, &current_value) < 0)
        {
            // Try powercap if MSR fails
            if (read_powercap("intel-rapl:0", &current_value) < 0)
            {
                return -1;
            }
        }

        // Avoid tight loop consuming 100% CPU and producing heat
        if (loop_count % 1000 == 0)
        {
            struct timespec ts = {0, 100}; // 100 nanoseconds
            nanosleep(&ts, NULL);
        }

    } while (current_value == prev_value);

    *value = current_value;
    if (iterations != NULL)
    {
        *iterations = loop_count;
    }

    return 0;
}

// Read current RAPL energy value (aligned with update)
static PyObject *
_powerlens_read_energy_aligned(PyObject *self, PyObject *args)
{
    uint64_t current_value = 0;
    int cpu = 0; // Default to CPU 0

    // Wait for update to align with interval boundary
    if (wait_for_update(cpu, &current_value, NULL) < 0)
    {
        return NULL;
    }

    // Now we're at a clean interval boundary
    return PyLong_FromUnsignedLongLong(current_value);
}

// Read energy value aligned with end of an interval
static PyObject *
_powerlens_read_energy_aligned_end(PyObject *self, PyObject *args)
{
    uint64_t current_value = 0;
    int cpu = 0; // Default to CPU 0
    int loop_count = 0;

    // Wait for update while counting iterations
    if (wait_for_update(cpu, &current_value, &loop_count) < 0)
    {
        return NULL;
    }

    // Return both the energy value and loop count for calibration
    PyObject *result = PyTuple_New(2);
    PyTuple_SET_ITEM(result, 0, PyLong_FromUnsignedLongLong(current_value));
    PyTuple_SET_ITEM(result, 1, PyLong_FromLong(loop_count));
    return result;
}

// Compute energy consumption with calibration
static PyObject *
_powerlens_compute_energy(PyObject *self, PyObject *args)
{
    PyObject *start_obj, *end_obj, *calib_obj;
    uint64_t start_val, end_val;
    int loop_count;
    double loop_energy_per_iteration, energy_unit;

    if (!PyArg_ParseTuple(args, "OOO", &start_obj, &end_obj, &calib_obj))
    {
        return NULL;
    }

    start_val = PyLong_AsUnsignedLongLong(start_obj);

    // End is a tuple (energy_val, loop_count)
    end_val = PyLong_AsUnsignedLongLong(PyTuple_GetItem(end_obj, 0));
    loop_count = PyLong_AsLong(PyTuple_GetItem(end_obj, 1));

    // Get calibration data
    energy_unit = PyFloat_AsDouble(PyDict_GetItemString(calib_obj, "energy_unit"));
    loop_energy_per_iteration = PyFloat_AsDouble(
        PyDict_GetItemString(calib_obj, "loop_energy_per_iteration"));

    // Calculate raw energy difference, handling wrap-around
    uint64_t max_val = 0xFFFFFFFF; // 32-bit counter
    double raw_diff;

    if (end_val >= start_val)
    {
        raw_diff = (double)(end_val - start_val);
    }
    else
    {
        // Counter wrapped around
        raw_diff = (double)((max_val - start_val) + end_val + 1);
    }

    // Convert to joules and subtract loop overhead
    double total_joules = raw_diff * energy_unit;
    double loop_joules = loop_count * loop_energy_per_iteration;
    double result_joules = total_joules - loop_joules;

    // Ensure we don't return negative energy due to calibration error
    if (result_joules < 0)
    {
        result_joules = 0;
    }

    return PyFloat_FromDouble(result_joules);
}

// Wait for SMM to execute
static PyObject *
_powerlens_wait_for_smm(PyObject *self, PyObject *args)
{
    uint64_t prev_time, current_time;
    uint64_t prev_value, current_value;
    int cpu = 0;
    struct timespec ts = {0, 100000}; // 100 microseconds
    int found_smm = 0;

    // Get initial value and time
    if (read_msr(cpu, MSR_PKG_ENERGY_STATUS, &prev_value) < 0)
    {
        // Try powercap if MSR fails
        if (read_powercap("intel-rapl:0", &prev_value) < 0)
        {
            return NULL;
        }
    }

    // Start timestamp
    struct timespec start_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);
    prev_time = start_time.tv_sec * 1000000000ULL + start_time.tv_nsec;

    // Wait for significant delay (SMM) for up to 32ms
    // TSMM occurs approximately every 16ms
    while (!found_smm)
    {
        nanosleep(&ts, NULL);

        // Get current value and time
        if (read_msr(cpu, MSR_PKG_ENERGY_STATUS, &current_value) < 0)
        {
            // Try powercap if MSR fails
            if (read_powercap("intel-rapl:0", &current_value) < 0)
            {
                return NULL;
            }
        }

        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        current_time = now.tv_sec * 1000000000ULL + now.tv_nsec;

        // Check elapsed time (ns)
        uint64_t time_diff = current_time - prev_time;

        // If time between reads is much larger than expected, assume SMM occurred
        if (time_diff > 500000)
        { // 500 microseconds threshold
            found_smm = 1;
        }

        // If we've waited over 32ms, give up and return
        uint64_t elapsed = current_time -
                           (start_time.tv_sec * 1000000000ULL + start_time.tv_nsec);
        if (elapsed > 32000000)
        { // 32ms in ns
            break;
        }

        prev_value = current_value;
        prev_time = current_time;
    }

    return PyBool_FromLong(found_smm);
}

// Calibration function
static PyObject *
_powerlens_calibrate(PyObject *self, PyObject *args)
{
    uint64_t power_unit_val, start_val, end_val;
    int cpu = 0;
    double energy_unit;
    int loop_count = 0;
    double total_energy = 0.0;
    int iterations = 10;

    // Read power unit register to get energy unit
    if (read_msr(cpu, MSR_RAPL_POWER_UNIT, &power_unit_val) < 0)
    {
        // Try to get energy unit from powercap (this is a simplification)
        // In real implementation, we'd need to read the unit from elsewhere
        energy_unit = 6.103515625e-05; // Common default, but may vary by CPU
    }
    else
    {
        // Energy units are in bits 8:12
        energy_unit = pow(0.5, (double)((power_unit_val >> 8) & 0x1F));
    }

    // Run several calibration iterations to get average loop energy
    for (int i = 0; i < iterations; i++)
    {
        // Get aligned reading
        if (wait_for_update(cpu, &start_val, NULL) < 0)
        {
            return NULL;
        }

        // Run an empty delay loop similar to what we use in measurements
        for (int j = 0; j < 100000; j++)
        {
            asm volatile("nop"); // Prevent optimization
        }

        // Get end reading with iteration count
        if (wait_for_update(cpu, &end_val, &loop_count) < 0)
        {
            return NULL;
        }

        // Calculate energy difference
        uint64_t max_val = 0xFFFFFFFF; // 32-bit counter
        double raw_diff;

        if (end_val >= start_val)
        {
            raw_diff = (double)(end_val - start_val);
        }
        else
        {
            // Counter wrapped around
            raw_diff = (double)((max_val - start_val) + end_val + 1);
        }

        // Convert to joules
        double joules = raw_diff * energy_unit;
        total_energy += joules;
    }

    // Calculate average energy per loop iteration
    double loop_energy_per_iteration = total_energy / (loop_count * iterations);

    // Create and return calibration data dict
    PyObject *calib_dict = PyDict_New();
    PyDict_SetItemString(calib_dict, "energy_unit", PyFloat_FromDouble(energy_unit));
    PyDict_SetItemString(calib_dict, "loop_energy_per_iteration",
                         PyFloat_FromDouble(loop_energy_per_iteration));

    return calib_dict;
}

// Module method definitions
static PyMethodDef powerlensMethods[] = {
    {"read_energy_aligned", _powerlens_read_energy_aligned, METH_NOARGS,
     "Read energy counter aligned with an update interval."},
    {"read_energy_aligned_end", _powerlens_read_energy_aligned_end, METH_NOARGS,
     "Read energy counter aligned with an update interval at the end of measurement."},
    {"compute_energy", _powerlens_compute_energy, METH_VARARGS,
     "Compute calibrated energy difference between start and end readings."},
    {"calibrate", _powerlens_calibrate, METH_NOARGS,
     "Calibrate the measurement system."},
    {"wait_for_smm", _powerlens_wait_for_smm, METH_NOARGS,
     "Wait for System Management Mode to execute"},
    {NULL, NULL, 0, NULL} // Sentinel
};

// Module definition
static struct PyModuleDef powerlensmodule = {
    PyModuleDef_HEAD_INIT,
    "_powerlens_core",
    "powerlens energy measurement core functionality.",
    -1,
    powerlensMethods};

// Module initialization
PyMODINIT_FUNC
PyInit__powerlens_core(void)
{
    return PyModule_Create(&powerlensmodule);
}