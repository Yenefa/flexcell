"""Archive every raw file, with per-run ZIPs and streaming SHA256 verification."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def digest(stream):
    sha=hashlib.sha256()
    for chunk in iter(lambda:stream.read(1024*1024),b''):sha.update(chunk)
    return sha.hexdigest()


def archive(root,destination):
    cases={p.parent.name for p in root.glob('*/run_status.json')}
    groups={};manifest=dict(files={},archives={})
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root);group=rel.parts[0] if rel.parts[0] in cases else 'support'
        groups.setdefault(group,[]).append((path,rel.as_posix()))
    for group,files in sorted(groups.items()):
        target=destination/('raw_'+group+'.zip')
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
            for path,rel in files:
                with path.open('rb') as stream:sha=digest(stream)
                output.write(path,rel)
                manifest['files'][rel]=dict(sha256=sha,bytes=path.stat().st_size,archive=target.name)
        with zipfile.ZipFile(target) as source:
            for path,rel in files:
                with source.open(rel) as stream:assert digest(stream)==manifest['files'][rel]['sha256'],rel
        with target.open('rb') as stream:sha=digest(stream)
        manifest['archives'][target.name]=dict(sha256=sha,bytes=target.stat().st_size,verified=True)
    manifest.update(file_count=len(manifest['files']),total_raw_bytes=sum(v['bytes'] for v in manifest['files'].values()))
    with (destination/'raw_sha256.json').open('x') as stream:json.dump(manifest,stream,indent=2)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();archive(args.root,args.destination)
