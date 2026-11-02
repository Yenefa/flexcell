"""Document the CRLF metadata defect; bind unchanged runtime bytes to the Git export."""
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

repo = Path(r'C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone')
root = repo/'artifacts/native-stale-20261031'
capsule = repo/'setup/acceptance/native_audit_20261031'
receipt_path = capsule/'receipt.json'
receipt = json.loads(receipt_path.read_text())
with (capsule/'receipt-before-source-binding.json').open('xb') as stream:
    stream.write(receipt_path.read_bytes())
archive = root/'patched-source.tar'
sha = lambda data:hashlib.sha256(data).hexdigest()
with zipfile.ZipFile(capsule/'raw-evidence.zip') as bundle:
    identity = json.loads(bundle.read('patched/window/identity.stdout'))
    exported = json.loads(bundle.read('preflight/patched-source-receipt.json'))
    sidecar = bundle.read('preflight/patched-source-revision.txt')
with tarfile.open(archive) as source:
    commit = source.pax_headers['comment']
    files = {name:sha(source.extractfile(name).read()) for name in identity['source_files']}
assert commit == exported['revision'] == receipt['patched_source_revision']
assert sha(archive.read_bytes()) == exported['sha256']
assert files == identity['source_files'] and len(files) == 209
assert identity['source_revision'] == commit+'\r'
assert sidecar == (commit+'\r\n').encode('ascii')
binding = dict(status='SOURCE_BYTES_BOUND_WITH_INVALID_REVISION_METADATA',
    canonical_source_revision=commit,recorded_source_revision=identity['source_revision'],
    source_revision_metadata='INVALID_TRAILING_CR',source_archive_sha256=exported['sha256'],
    source_archive_bytes=exported['bytes'],git_archive_pax_comment=commit,
    revision_sidecar_sha256=sha(sidecar),verified_source_files=209,source_files=files,
    explanation='Windows write_text created CRLF; bash command substitution retained CR in the environment. '
                'Raw identity and all window bytes are unchanged. The Git archive commit and every '
                'runtime source-file digest match. No strip, metadata rewrite or replacement window.')
binding_path = capsule/'source-binding.json'
with binding_path.open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(binding,indent=2)+'\n')
receipt['source_binding_sha256'] = sha(binding_path.read_bytes())
receipt['patched_source_revision_metadata'] = 'INVALID_TRAILING_CR'
receipt_path.write_bytes((json.dumps(receipt,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:v for k,v in binding.items() if k!='source_files'},indent=2))
