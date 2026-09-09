
from setuptools import setup, find_packages

setup(
    name="kcp-compressor",
    version="4.0.0",
    author="Pankaj KC",
    description="Order-2 Bit Context Arithmetic Codec with Delta Transformations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "kcp=kcp.cli:main",
        ],
    },
)
