import os
from setuptools import setup, find_packages

VERSION = "1.7.2"

src_dir = os.path.dirname(__file__)

install_requires = [
    "future",
    "troposphere>=1.9.0",
    'botocore>=1.12.111',  # matching boto3 requirement
    "boto3>=1.9.111,<2.0",
    "PyYAML>=3.13b1",
    "awacs>=0.6.0",
    "gitpython>=2.0,<3.0",
    "jinja2>=2.7,<3.0a",
    "schematics>=2.0.1,<2.1.0",
    "formic2",
    "python-dateutil>=2.0,<3.0",
    "MarkupSafe<2.0", # 2.0 dropped python 2.7, 3.5 support - temporary
    "more-itertools<6.0.0", # 6.0.0 dropped python 2.7 support - temporary
    "rsa==4.5", # 4.6 dropped python 2.7 support - temporary
    "python-jose<3.2.0", # 3.2.0 dropped python 2.7 support - temporary
]

setup_requires = ['pytest-runner']

tests_require = [
    "pytest~=4.3",
    "pytest-cov~=2.6",
    "mock~=2.0",
    "moto[awslambda]~=1.3.16",
    "testfixtures~=4.10.0",
    "flake8-future-import",
]

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
        extras_require=dict(testing=tests_require),
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "License :: OSI Approved :: BSD License",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
        ],
    )
