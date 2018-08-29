import os
from setuptools import setup, find_packages


VERSION = "1.4.1"

src_dir = os.path.dirname(__file__)

install_requires = [
    "future",
    "troposphere>=1.9.0",
    "botocore<1.11.0",
    "boto3>=1.7.0,<1.8.0",
    "PyYAML>=3.12",
    "awacs>=0.6.0",
    "gitpython~=2.0",
    "schematics~=2.0.1",
    "formic2",
    "python-dateutil~=2.0",
]

tests_require = [
    "mock~=2.0.0",
    "moto~=1.1.24",
    "testfixtures~=4.10.0",
    "coverage~=4.3.4",
    "flake8-future-import",
]

setup_requires = ["nose"]

scripts = [
    "scripts/compare_env",
    "scripts/docker-stacker",
    "scripts/stacker.cmd",
    "scripts/stacker",
]


def read(filename):
    full_path = os.path.join(src_dir, filename)
    with open(full_path) as fd:
        return fd.read()


if __name__ == "__main__":
    setup(
        name="stacker",
        version=VERSION,
        author="Michael Barrett",
        author_email="loki77@gmail.com",
        license="New BSD license",
        url="https://github.com/cloudtools/stacker",
        description="AWS CloudFormation Stack manager",
        long_description=read("README.rst"),
        packages=find_packages(),
        scripts=scripts,
        install_requires=install_requires,
        tests_require=tests_require,
        setup_requires=setup_requires,
        test_suite="nose.collector",
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "License :: OSI Approved :: BSD License",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
        ],
    )
