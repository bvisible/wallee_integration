# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in wallee_integration/__init__.py
from wallee_integration import __version__ as version

setup(
	name='wallee_integration',
	version=version,
	description='Wallee Payment Integration for ERPNext/Frappe/Webshop',
	author='Neoservice',
	author_email='info@neoservice.ai',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
