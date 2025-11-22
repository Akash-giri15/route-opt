# backend/cpp_native/setup.py
from setuptools import setup, Extension
import pybind11

cpp_args = ['/std:c++17'] # Windows standard flag. Use '-std=c++17' for Linux/Mac.

ext_modules = [
    Extension(
        'ch_native',
        ['ch_core.cpp'],
        include_dirs=[pybind11.get_include()],
        language='c++',
        extra_compile_args=cpp_args,
    ),
]

setup(
    name='ch_native',
    version='1.0',
    ext_modules=ext_modules,
)