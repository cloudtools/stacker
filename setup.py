import os
from setuptools import setup, find_packages
import glob

src_dir = os.path.dirname(__file__)

install_requires = [
    'aws_helper>=0.2.0',
    'troposphere>=0.7.1',
    'boto>=2.25.0',
    'PyYAML>=3.11',
]

tests_require = [
    'nose>=1.0',
]


def read(filename):
    full_path = os.path.join(src_dir, filename)
    with open(full_path) as fd:
        return fd.read()


if __name__ == '__main__':
    setup(
        name='stacker',
        version='0.3.0',
        author='Michael Barrett',
        author_email='loki77@gmail.com',
        license="New BSD license",
        url="https://github.com/remind101/stacker",
        description='Opinionated AWS CloudFormation Stack manager',
        long_description=read('README.rst'),
        packages=find_packages(),
        scripts=glob.glob(os.path.join(src_dir, 'scripts', '*')),
        install_requires=install_requires,
        tests_require=tests_require,
        test_suite='nose.collector',
    )
