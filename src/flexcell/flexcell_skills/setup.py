import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'flexcell_skills'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Yenefa',
    maintainer_email='sca331613@gmail.com',
    description='FlexCell skill server (MoveToPose action).',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'move_to_pose_server = flexcell_skills.move_to_pose_server:main',
            'observe_server = flexcell_skills.observe_server:main',
            'pick_server = flexcell_skills.pick_server:main',
            'place_server = flexcell_skills.place_server:main',
            'verify_server = flexcell_skills.verify_server:main',
            'task_fsm_server = flexcell_skills.task_fsm_server:main',
            'carry_server = flexcell_skills.carry_server:main',
        ],
    },
)
