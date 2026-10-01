import json
from flexcell_skills.confidence_calibration import ConfidenceCalibration, prompt_digest


def test_calibration_is_bound_to_weights_prompt_and_model(tmp_path, monkeypatch):
    monkeypatch.setenv('FLEXCELL_JEV_MODEL', 'fast')
    monkeypatch.setenv('FLEXCELL_JEV_MODEL_SHA256', 'weights')
    path=tmp_path/'calibration.json'
    path.write_text(json.dumps(dict(schema_version=1, model='fast', model_sha256='weights',
        prompt_sha256=prompt_digest(), label_definition='FSM_ACTION_AGREEMENT',
        bins=[dict(lower=0., upper=1., n=20, wilson_lower=.65)])))
    calibration=ConfidenceCalibration(path)
    estimate, valid, _=calibration.estimate(.99)
    assert valid and estimate == .65
    monkeypatch.setenv('FLEXCELL_JEV_MODEL_SHA256', 'other_weights')
    assert not ConfidenceCalibration(path).estimate(.99)[1]


def test_missing_or_sparse_calibration_cannot_authorize_fast_route(tmp_path, monkeypatch):
    monkeypatch.delenv('FLEXCELL_JEV_CALIBRATION', raising=False)
    assert not ConfidenceCalibration().estimate(1.)[1]
    path=tmp_path/'bad.json'
    path.write_text('{')
    assert not ConfidenceCalibration(path).estimate(1.)[1]
