"""Read the same pinned collision meshes as trusted_sim; no robot command."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
import xacro

EXPECTED={
    'link1.stl':'d2b84e13ccd3f923148bb26c95723bb3c9e7af0a7cc85cd315ee70ce7629dd1f',
    'link2.stl':'20a6cc8a673b90ab02f97e4c2f0437ff692e71daded8a82a77b54254ae877c66',
    'link3.stl':'e6904447bca7888acb6a3a170d220b12e92f6dbf53c560987527cfd115f6eb19',
    'link4.stl':'9da72baf0854e0335bf0fe199da3676c57625e17277a4fa455b995130b29ffab',
    'link5.stl':'75e7596295dd5f5cbc68d81b2c875058f28721f98d7402d2d431ccf2334b57a6',
    'gripper_left_palm.stl':'fb4dfabe68712bbba34deb9f8469f9187009c07579dccd5401b82d08de425267',
    'gripper_right_palm.stl':'a5bfc10a067c806a19062e2fcb58989623a09edc0e9bbc4fd735a56d83f99752',
}


def prepare(out):
    out=Path(out);out.mkdir(exist_ok=False)
    package=Path(get_package_share_directory('open_manipulator_description'))
    model=package/'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'
    robot=xacro.process_file(str(model),mappings={'use_sim':'true'}).toprettyxml(indent='  ')
    (out/'robot.urdf').write_text(robot)
    sources={}
    for mesh in ET.fromstring(robot).findall('.//collision/geometry/mesh'):
        uri=mesh.get('filename')
        if not uri.startswith('package://open_manipulator_description/'):
            raise ValueError('unexpected mesh package')
        path=package/uri.removeprefix('package://open_manipulator_description/')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if EXPECTED.get(path.name)!=digest:raise ValueError('collision mesh differs from registered geometry: '+path.name)
        shutil.copyfile(path,out/path.name);sources[uri]=digest
    if set(p.name for p in out.glob('*.stl'))!=set(EXPECTED):raise ValueError('incomplete pinned mesh set')
    license_names=[n.text for n in ET.parse(package/'package.xml').getroot().findall('license')]
    if not any('apache' in s.casefold() for s in license_names):raise ValueError('license requires review')
    shutil.copyfile('/usr/share/common-licenses/Apache-2',out/'LICENSE')
    value=dict(package=str(package),urdf_sha256=hashlib.sha256((out/'robot.urdf').read_bytes()).hexdigest(),
        meshes=sources,license=license_names,
        upstream_lock_sha256=hashlib.sha256(Path('/opt/flexcell/upstream.lock.repos').read_bytes()).hexdigest())
    (out/'sources.json').write_text(json.dumps(value,indent=2))
    return value


if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1]),indent=2))
