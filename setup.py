from setuptools import setup

required = []

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name='chaluptests',
      version='1.0.0',
      description='A deep-learning-based conditional independence test that works for big, high-dimensional data.',
      author='Krzysztof Chalupka',
      author_email='kjchalup@caltech.edu',
      url='https://github.com/kjchalup/independence_test',
      packages=['chaluptests'],
      install_requires=required)
