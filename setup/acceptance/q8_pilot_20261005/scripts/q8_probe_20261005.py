import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.request

from flexcell_skills.confidence_calibration import ConfidenceCalibration, prompt_digest
from flexcell_skills.jev_backends import ClefBackend

evidence = Path(sys.argv[1])
calibration_path = evidence / 'calibration.json'
if calibration_path.exists():
    data = json.loads(calibration_path.read_text())
    assert data['prompt_sha256'] == prompt_digest()
    assert data['model_sha256'] == os.environ['FLEXCELL_JEV_MODEL_SHA256']
    config = Path.home() / '.config/flexcell'
    target = config / 'jev_calibration_clef_q8_20261005.json'
    target.write_bytes(calibration_path.read_bytes())
    profile = config / 'mainline_jev.sh'
    saved = evidence / 'mainline_jev_before.sh'
    if not saved.exists():
        saved.write_bytes(profile.read_bytes())
    lines = profile.read_text().splitlines()
    lines = [line for line in lines if not line.startswith('export FLEXCELL_JEV_CALIBRATION=')]
    profile.write_text('\n'.join(lines).replace('prompt AST', 'source bytes') +
        '\nexport FLEXCELL_JEV_CALIBRATION="' + str(target) + '"\n')
    os.environ['FLEXCELL_JEV_CALIBRATION'] = str(target)

calibration = ConfidenceCalibration()
assert calibration.data, calibration.error
backend = ClefBackend()
ok, detail = backend.health()
assert ok, detail
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = os.environ['FLEXCELL_JEV_ENDPOINT'].split('/v1/')[0]
with opener.open(base + '/health', timeout=3) as response:
    readiness = json.load(response)
assert readiness.get('status') == 'ok', readiness
with opener.open(base + '/v1/models', timeout=3) as response:
    models = json.load(response)
assert any(m['id'] == 'Clef-Flash-Q8_0.gguf' for m in models['data'])
question = SimpleNamespace(prompt='Choose a next action.', context='task start',
    options=(SimpleNamespace(action='OBSERVE', criteria='fresh snapshot'),
             SimpleNamespace(action='PICK', criteria='object observed')))
response = backend.classify('{"task":"probe only"}', question)
assert response.raw['tokens'] > 0, response.raw
result = dict(health=detail, readiness=readiness,
    prompt_sha256=prompt_digest(), calibration_sha256=calibration.sha256,
    estimates={str(p): calibration.estimate(p) for p in (.55, .9)},
    inference=dict(choice=response.choice, tokens=response.raw['tokens'],
        input_tokens=response.raw['input_tokens'], output_tokens=response.raw['output_tokens']))
(evidence / 'probe.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
