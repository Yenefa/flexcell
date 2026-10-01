#!/usr/bin/env python3
"""Install a private gateway credential and a separate non-secret WSL profile."""
import json
import os
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import urlsplit


def main():
    config = json.load(sys.stdin)
    endpoint, model, key = config['endpoint'], config['model'], config['api_key']
    url = urlsplit(endpoint)
    official = url.netloc == 'api.deepseek.com' and url.path == '/chat/completions' and model == 'deepseek-flash'
    gateway = url.netloc == 'opencode.ai' and url.path == '/zen/v1/chat/completions'
    if (url.scheme != 'https' or not (official or gateway) or url.query or url.fragment
            or not re.fullmatch(r'deepseek-[a-z0-9.-]+', model)
            or not isinstance(key, str) or not key.strip() or '\n' in key or '\r' in key):
        raise ValueError('invalid DeepSeek endpoint configuration')
    os.umask(0o077)
    directory = Path.home() / '.config/flexcell'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key_file = directory / ('deepseek_api_key' if official else 'opencode_api_key')
    key_file.write_text(key.strip(), encoding='utf-8')
    key_file.chmod(0o600)
    profile = {
        'FLEXCELL_LLM_ENDPOINT': endpoint,
        'FLEXCELL_LLM_MODEL': model,
        'FLEXCELL_LLM_API_KEY_FILE': str(key_file),
        'FLEXCELL_LLM_BACKEND': 'deepseek-official' if official else 'opencode-zen',
        'FLEXCELL_LLM_RESPONSE_FORMAT': 'json_object',
        'FLEXCELL_LLM_THINKING': 'disabled',
        'FLEXCELL_LLM_MAX_TOKENS': '512',
        'FLEXCELL_LLM_TIMEOUT_S': '30',
    }
    # Provisioning does not activate an endpoint which has not returned a real
    # decision. Select this profile explicitly for readiness and deployment.
    if official:
        profile['FLEXCELL_LLM_BUDGET_FILE'] = str(directory / 'deepseek_budget_20261001.json')
    path = directory / ('deepseek_model.sh' if official else 'opencode_model.sh')
    path.write_text('# Non-secret runtime profile; credential stays in the separate private file.\n'
                    + ''.join(f'export {name}={shlex.quote(value)}\n' for name, value in profile.items()),
                    encoding='utf-8')
    path.chmod(0o600)
    print(json.dumps(dict(endpoint=endpoint, model=model, credential_configured=True,
                         credential_mode='0600', profile=str(path))))


if __name__ == '__main__':
    main()
