"""
Setup script for powerlens - High-precision energy measurement for Python code
"""

from setuptools import setup, Extension

powerlens_module = Extension(
    '_powerlens_core',
    sources=['_powerlens_core.c'],
    extra_compile_args=['-O3'],  
)

setup(
    name='powerlens',
    version='0.1.0',
    description='High-precision energy measurement for Python code',
    author='Anonymous',
    ext_modules=[powerlens_module],
    py_modules=['powerlens'],
    python_requires='>=3.6',
)
