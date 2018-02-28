import os
from setuptools import setup, find_packages

VERSION = "1.2.0rc2"

src_dir = os.path.dirname(__file__)

install_requires = [
    "troposphere>=1.9.0",
    "botocore>=1.6.0",
    "boto3>=1.3.1",
    "PyYAML~=3.12",
    "awacs>=0.6.0",
    "formic~=0.9b",
    "gitpython~=2.0",
    "schematics~=2.0.1",
    "python-dateutil~=2.0"
]

tests_require = [
    "mock~=2.0.0",
    "moto~=1.1.24",
    "testfixtures~=4.10.0",
    "coverage~=4.3.4"
]

setup_requires = [
    "nose",
]

scripts = [
    "scripts/compare_env",
    "scripts/docker-stacker",
    "scripts/stacker.cmd",
    "scripts/stacker"
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
        url="https://github.com/remind101/stacker",
        description="AWS CloudFormation Stack manager",
        long_description=read("README.rst"),
        packages=find_packages(),
        scripts=scripts,
        install_requires=install_requires,
        tests_require=tests_require,
        setup_requires=setup_requires,
        test_suite="nose.collector",
    )
