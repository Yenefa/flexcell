"""Empirical FSM-agreement routing estimates, never physical success odds."""
import hashlib
import json
import math
import os
from pathlib import Path


def prompt_digest():
    """Digest over the backend prompt surface: the WHOLE jev_backends source
    bytes, so every backend's prompt logic is covered (LocalReproduction's
    _render AND ClefBackend's instructions/criteria templates).  Bytes, not
    ast.dump(): the AST dump is CPython-version dependent, and read_text()
    without encoding= breaks on hosts whose default codec is not UTF-8."""
    return hashlib.sha256(
        Path(__file__).with_name('jev_backends.py').read_bytes()).hexdigest()


class ConfidenceCalibration:
    def __init__(self, path=None):
        self.data = None
        self.error = 'calibration_not_configured'
        path = path or os.environ.get('FLEXCELL_JEV_CALIBRATION')
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if (data['schema_version'] != 1 or data['prompt_sha256'] != prompt_digest()
                    or data['model_sha256'] != os.environ.get('FLEXCELL_JEV_MODEL_SHA256')
                    or data['model'] != os.environ.get('FLEXCELL_JEV_MODEL')
                    or data['label_definition'] != 'FSM_ACTION_AGREEMENT'):
                raise ValueError('calibration identity mismatch')
            for b in data['bins']:
                if not (0 <= b['lower'] < b['upper'] <= 1 and b['n'] >= 0
                        and math.isfinite(b['wilson_lower']) and 0 <= b['wilson_lower'] <= 1):
                    raise ValueError('invalid calibration bin')
            self.data, self.error = data, ''
            self.sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.error = 'invalid_calibration:%s' % type(exc).__name__

    def estimate(self, reported):
        if self.data:
            for b in self.data['bins']:
                if b['lower'] <= reported < b['upper'] or reported == b['upper'] == 1:
                    if b['n'] >= 5:
                        return b['wilson_lower'], True, self.sha256
                    return 0., False, 'insufficient_bin_samples'
        return reported, False, self.error
