import requests
from django.conf import settings

def _parse_ollama_response(resp_json):
    # Ollama response formats can vary by version.
    # Try known keys in order of likelihood.
    if not resp_json:
        return None
    if isinstance(resp_json, dict):
        if 'response' in resp_json and isinstance(resp_json['response'], str):
            return resp_json['response']
        if 'text' in resp_json and isinstance(resp_json['text'], str):
            return resp_json['text']
        if 'results' in resp_json and isinstance(resp_json['results'], list) and resp_json['results']:
            first = resp_json['results'][0]
            if isinstance(first, dict):
                # sometimes content or output_text etc.
                for k in ('content', 'output_text', 'text'):
                    if k in first and isinstance(first[k], str):
                        return first[k]
                # fallback: join pieces
                if 'content' in first and isinstance(first['content'], list):
                    return ''.join([c.get('text','') if isinstance(c, dict) else str(c) for c in first['content']])
    # fallback to string repr
    try:
        return str(resp_json)
    except Exception:
        return None

def ollama_generate(prompt: str, model: str = None, timeout: int = None) -> str:
    base = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    model = model or getattr(settings, 'OLLAMA_MODEL', None) or 'llama3.2'
    timeout = timeout or getattr(settings, 'OLLAMA_REQUEST_TIMEOUT', 25)
    url = f"{base}/api/generate"

    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': 0.2,
            'top_p': 0.9
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            return f"Ollama алдаа: {r.status_code}"
        data = r.json()
        parsed = _parse_ollama_response(data)
        return parsed or (str(data) if data else '')
    except requests.exceptions.ConnectionError:
        return 'Ollama сервер ажиллахгүй байна. ollama serve ажиллуулна уу.'
    except Exception as e:
        return f'Алдаа: {e}'
