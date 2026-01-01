import glob
import os
import sys
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


init_py_path = os.path.normpath(os.path.dirname(
    os.path.abspath(__file__))) + '/bioinformatics_tools/__init__.py'
# Grab the version
version_string = [i.strip() for i in open(init_py_path).readlines()
                  if i.strip().startswith('__version__')][0]
mypack_version = version_string.split("'")[1].split('-')[0]


# Set up the package.
setup(
    name="bioinformatics_tools",
    version=mypack_version,
    author="Dane Deemer",
    author_email="dane@liminalbios.com",

    description="Simple tools for common bioinformatic use-cases",
    long_description=long_description,
    long_description_content_type="text/markdown",

    url="https://github.com/Diet-Microbiome-Interactions-Lab/GeneralTools",

    packages=find_packages(),
    package_data={
        '': ['caragols/*.yaml', 'caragols/*.json'],
        'bioinformatics_tools.misc_tools': ['*.sh'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'bio',
        'fastapi',
        'matplotlib',
        'numpy',
        'pandas',
        'pydantic==2.*',
        'pydantic-sqlite==0.*',
        'pyyaml==6.*',
        'python-json-logger==2.0.7',
        'typer',
        'uvicorn'
    ],
    python_requires='>=3.11',
    entry_points={
        'console_scripts': [
            'dane=bioinformatics_tools.file_classes.main:cli',
            'misc=bioinformatics_tools.misc_tools.main:cli',
            'dane_wf=bioinformatics_tools.workflow_tools.main:cli',
            'dane-api=bioinformatics_tools.api.main:serve',
            ],
        },
    scripts=glob.glob('bioinformatics_tools/misc_tools/*.sh')
)
