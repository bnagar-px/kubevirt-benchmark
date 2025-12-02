#!/usr/bin/env python3
"""
Setup configuration for virtbench CLI
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name='virtbench',
    version='1.0.0',
    description='KubeVirt Benchmark Suite - Performance testing toolkit for KubeVirt VMs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Portworx',
    license='Apache 2.0',
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'click>=8.1.7',
        'rich>=13.7.0',
        'pyyaml>=6.0.3',
        'pandas>=2.3.3',
    ],
    entry_points={
        'console_scripts': [
            'virtbench=virtbench.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)

