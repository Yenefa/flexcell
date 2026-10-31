"""Export the declared upstream commits from object DBs, never dirty working files."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

base=Path('/home/ros/agentic_workcell_ws')
stage=base/'build/preposition-world-stage'
out=base/'artifacts/preposition-world-20261031'
repos=[('DynamixelSDK',base/'src/DynamixelSDK','516ae8632c593d7c84afd2bdee2a2fac965305cc'),
       ('dynamixel_interfaces',base/'src/dynamixel_interfaces','3392e1214c62c7ee9e05ccc811e3e829c063bae8'),
       ('dynamixel_hardware_interface',base/'src/dynamixel_hardware_interface','3375b3d0c99c5bcdab11b2dc15c89a2923e2bca2'),
       ('open_manipulator',Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/artifacts/local-pr75-20261030/pinned-open-manipulator'),
        '17efe42bd1df178fa44d49c43250fc4304343dbb')]
records=[]
for name,source,revision in repos:
    target=stage/'upstream/src'/name
    target.mkdir(parents=True,exist_ok=False)
    archive=out/(name+'-locked.tar')
    with archive.open('xb') as stream:
        subprocess.run(['git','-C',str(source),'archive',revision],stdout=stream,check=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(target,filter='data')
    records.append(dict(name=name,revision=revision,object_database=str(source),
                        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
(out/'locked-upstream.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
