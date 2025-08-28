from setuptools import setup, find_packages

setup(
    name="arc",
    version="0.0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "arc=libarc.main:main",
        ],
    },
    install_requires=[
        # list dependencies here e.g. "click>=8.0"
    ],
)
