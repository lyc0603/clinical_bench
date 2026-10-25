"""Nonclinical parameter probes, never ADaM experimental outcomes.

Successful HTTP responses establish acceptance, not that sampling changed.
DeepSeek thinking-mode temperature is documented as ignored.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

TEMPERATURES = (0.2, 0.6, 1.0)
MODELS = {
    'openai': ('gpt-6.1-sol', 'OPENAI_API_KEY', 'https://api.openai.com/v1/responses'),
    'anthropic': ('claude-sonnet-5-5', 'ANTHROPIC_API_KEY', 'https://api.anthropic.com/v1/messages'),
    'deepseek': ('deepseek-flash', 'DEEPSEEK_API_KEY', 'https://api.deepseek.com/chat/completions'),
}
SOURCES = {
    'openai': 'https://developers.openai.com/api/docs/guides/latest-model',
    'anthropic': 'https://platform.claude.com/docs/en/models/sonnet-5-5/overview',
    'deepseek': 'https://api-docs.deepseek.com/guides/thinking_mode/',
}
DOCUMENTED = {'openai': 'unsupported_with_supported_reasoning_modes',
              'anthropic': 'unsupported', 'deepseek': 'ignored_in_thinking_mode'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if not a.execute:
        p.error('--execute required for paid nonclinical API probes')
    if a.out.exists():
        raise ValueError('Preserve previous attempts: select a fresh output directory')
    env = {}
    for line in a.env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('\"\'')
    if any(not env.get(v[1]) for v in MODELS.values()):
        raise ValueError('Missing provider credential; no probes made')
    a.out.mkdir(parents=True)
    report = {'scope': 'nonclinical temperature capability probes only',
              'clinical_inputs_transmitted': False, 'experiment_started': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'sources': SOURCES, 'records': [],
              'interpretation': 'Acceptance does not establish temperature effectiveness; no 16-metric endpoints exist.'}
    target = a.out / 'capability.json'
    for provider, (model, key, url) in MODELS.items():
        for temperature in TEMPERATURES:
            headers = {'Content-Type': 'application/json'}
            body = {'model': model, 'temperature': temperature}
            prompt = 'Reply only READY. This is a nonclinical API parameter compatibility test.'
            if provider == 'openai':
                headers['Authorization'] = 'Bearer ' + env[key]
                body.update(input=prompt, reasoning={'effort': 'low'}, max_output_tokens=256)
            elif provider == 'anthropic':
                headers.update({'x-api-key': env[key], 'anthropic-version': '2023-06-01'})
                body.update(messages=[{'role': 'user', 'content': prompt}], max_tokens=256)
            else:
                headers['Authorization'] = 'Bearer ' + env[key]
                body.update(messages=[{'role': 'user', 'content': prompt}],
                            thinking={'type': 'enabled'}, max_tokens=64)
            record = {'provider': provider, 'requested_model': model, 'temperature': temperature,
                      'utc': datetime.now(timezone.utc).isoformat(),
                      'documented_behavior': DOCUMENTED[provider], 'request_parameters': body}
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    result = json.load(response)
                    record.update(http_status=response.status, returned_model=result.get('model'),
                                  usage=result.get('usage'), acceptance=True)
            except urllib.error.HTTPError as exc:
                try:
                    error = json.loads(exc.read()).get('error', {})
                except (ValueError, AttributeError):
                    error = {}
                message = str(error.get('message', ''))
                for secret in env.values():
                    if len(secret) > 8:
                        message = message.replace(secret, '[REDACTED]')
                record.update(http_status=exc.code, acceptance=False,
                              error_type=error.get('type'), error_code=error.get('code'),
                              error_parameter=error.get('param'), error_message=message[:800])
            except (urllib.error.URLError, TimeoutError) as exc:
                record.update(http_status=None, acceptance=None, transport_error=type(exc).__name__)
            report['records'].append(record)
            target.write_text(json.dumps(report, indent=2) + '\n')
            print(provider, temperature, record.get('http_status'), flush=True)

if __name__ == '__main__':
    main()
