from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))
exec(open(os.path.join(here, 'ck_prism/version.py')).read())

# Read the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ck_prism',
    version=__version__,
    description='CLI authentication for AWS credential exchange',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    license='Apache License 2.0',
    author='Aditya Ajay',
    author_email='aditya.ajay@cloudkeeper.com',
    url='https://www.cloudkeeper.com/',
    project_urls={
        'Source': 'https://github.com/CloudKeeper-Inc/ck-prism',
        'Bug Reports': 'https://github.com/CloudKeeper-Inc/ck-prism/issues',
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Security',
        'Topic :: System :: Systems Administration :: Authentication/Directory',
    ],
    keywords='aws authentication cli credentials cloudkeeper',
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'ck-prism=ck_prism.main:main',
        ],
    },
    install_requires=[
        'requests>=2.31.0',
    ],
)