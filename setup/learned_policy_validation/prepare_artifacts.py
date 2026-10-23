"""Download only pinned public inference assets, or verify existing ones."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--assets-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    assets_dir = args.assets_dir.resolve()
    manifest = json.loads((ROOT / 'inference-assets.json').read_text())
    for asset in manifest['assets']:
        relative = Path(asset['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Asset path must remain inside the research directory')
        path = assets_dir / relative
        valid = path.is_file() and sha256(path) == asset['sha256']
        if not valid:
            if args.verify_only:
                raise RuntimeError('Missing or mismatched asset: ' + str(relative))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.download')
            print('Downloading ' + str(relative), flush=True)
            # Uses inherited proxy and TLS trust. No account tokens are required.
            with urllib.request.urlopen(asset['url'], timeout=60) as response, temporary.open('wb') as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    output.write(chunk)
            if sha256(temporary) != asset['sha256']:
                temporary.unlink()
                raise RuntimeError('Checksum mismatch: ' + str(relative))
            temporary.replace(path)
    if not args.verify_only:
        import av
        data = assets_dir / 'sources/anuaju__openmanipulator_lerobot'
        with av.open(str(data / 'videos__observation.images.camera1__chunk-000__file-000.mp4')) as video:
            frame = next(video.decode(video=0))
            frame.to_image().save(data / 'frame-000.png')
    print(json.dumps({'verified_assets': len(manifest['assets']),
                      'robot_commands_sent': 0, 'mode': 'verify-only' if args.verify_only else 'prepared'}))


if __name__ == '__main__':
    main()
