from setuptools import setup, find_packages

def read_requirements():
    with open('requirements3.txt') as req:
        return req.read().splitlines()

def find_packages():
    return ['arcgitflow']

setup(
    name='arcgitflow',
    version='0.5.5',
    description='A Python implementation of the GitFlow process',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Carden Bagwell',
    author_email='cardenbag@gmail.com',
    url='https://github.com/cardenb/gitflow',
    packages=find_packages(),
    install_requires=read_requirements(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',  # Specific MIT license classifier
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    entry_points={
        'console_scripts': [
            'arcgitflow=gitflow:main',
        ],
    },
    python_requires='>=3.6',
)
