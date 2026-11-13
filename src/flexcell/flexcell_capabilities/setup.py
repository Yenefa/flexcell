from setuptools import find_packages, setup

setup(
    name='flexcell_capabilities',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/flexcell_capabilities']),
        ('share/flexcell_capabilities', ['package.xml']),
    ],
    install_requires=['setuptools', 'numpy'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Yenefa',
    maintainer_email='sca331613@gmail.com',
    description='Physical capability models and read-only telemetry.',
    license='Apache-2.0',
)
