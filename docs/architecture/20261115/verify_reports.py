"""Recompute the archived CI compatibility comparison; runs no tests or robot."""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
from compare_test_reports import cases, compare


def verify():
    metadata = json.loads((HERE / 'archive.json').read_text())
    raw = (HERE / metadata['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == metadata['sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        assert len(zipped.namelist()) == len(set(zipped.namelist()))
        assert set(zipped.namelist()) == set(metadata['members_sha256'])
        for name, digest in metadata['members_sha256'].items():
            assert hashlib.sha256(zipped.read(name)).hexdigest() == digest, name
        result = compare(cases(io.BytesIO(zipped.read('before.xml'))),
                         cases(io.BytesIO(zipped.read('after.xml'))))
        assert result == json.loads(zipped.read('comparison.json'))
        assert result['passed']
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
