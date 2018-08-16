"""
Setup script.
"""
import os
import sys
from setuptools import setup

version = '1.0.0'

if sys.argv[-1] == 'tag':
    os.system("git tag -a %s -m 'version %s'" % (version, version))
    os.system("git push origin master --tags")
    sys.exit()

if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
    os.system("python setup.py bdist_wheel upload")
    sys.exit()

if sys.argv[-1] == 'test':
    test_requirements = [
        'pytest',
        'flake8',
        'coverage'
    ]
    try:
        modules = map(__import__, test_requirements)
    except ImportError as e:
        err_msg = e.message.replace("No module named ", "")
        msg = "%s is not installed. Install your test requirments." % err_msg
        raise ImportError(msg)
    os.system('py.test')
    sys.exit()


setup(
    author='David Collien',
    author_email='david@openlearning.com',
    description='falcon-signed-requests',
    download_url='https://github.com/OpenLearningNet/falcon-signed-request-middleware/tarball/master',
    setup_requires=['pytest-runner'],
    install_requires=[
        'falcon',
        'time_uuid'
    ],
    license='MIT',
    name='falcon-signed-requests',
    packages=[
        'falcon_signed_requests',
    ],
    scripts=[],
    test_suite='tests',
    tests_require=[
        'pytest>=3.0.7,<4.0.0',
        'pytest-cov>=2.4.0,<3.0.0',
        'pytest-mock>=1.6.0,<2.0.0',
        'codecov>=2.0.3,<3.0.0',
        'coverage>=4.0.3,<5.0.0',
        'tox>=2.3.1,<3.0.0',
        'python-coveralls==2.9.0'
    ],
    url='https://github.com/OpenLearningNet/falcon-signed-request-middleware',
    version=version
)
