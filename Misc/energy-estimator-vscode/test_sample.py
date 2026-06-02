"""
Sample Python file for testing the Energy Estimator extension

Try analyzing this file to see energy estimates for different code blocks.
"""

def factorial(n):
    """Calculate factorial - should have low energy for small n"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def bubble_sort(arr):
    """Bubble sort - should have higher energy due to nested loops"""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


def read_and_process_file(filename):
    """File I/O with error handling"""
    try:
        with open(filename, 'r') as f:
            data = f.read()
            lines = data.split('\n')
            return [line.strip() for line in lines if line.strip()]
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []


def calculate_statistics(numbers):
    """Calculate basic statistics"""
    if not numbers:
        return None

    total = sum(numbers)
    count = len(numbers)
    mean = total / count

    # Calculate variance
    squared_diffs = [(x - mean) ** 2 for x in numbers]
    variance = sum(squared_diffs) / count

    return {
        'mean': mean,
        'variance': variance,
        'min': min(numbers),
        'max': max(numbers)
    }


def main():
    """Main function to test energy analysis"""
    # Test factorial
    result = factorial(5)
    print(f"Factorial of 5: {result}")

    # Test sorting
    arr = [64, 34, 25, 12, 22, 11, 90]
    sorted_arr = bubble_sort(arr.copy())
    print(f"Sorted array: {sorted_arr}")

    # Test statistics
    stats = calculate_statistics(arr)
    if stats:
        print(f"Statistics: {stats}")

    # Test file processing
    data = read_and_process_file('nonexistent.txt')
    print(f"Processed {len(data)} lines")


if __name__ == '__main__':
    main()
