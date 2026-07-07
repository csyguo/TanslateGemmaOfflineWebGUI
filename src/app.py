"""
TranslateGemma4B GUI — Flask application.
Serves the Web UI and provides a /api/translate proxy endpoint
that builds prompts matching the translategemma model's native format
and streams results from llama-server.

MIT License
"""

import json
import os
import re
import sys
import time
import uuid
import requests
from flask import Flask, request, jsonify, Response, render_template, stream_with_context

app = Flask(__name__)

# --- Config loading ---

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')

def load_config():
    """Load and return config.json as a dict. Exit with message on failure."""
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: config.json not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        print(f"ERROR: config.json: invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

config = load_config()

LLAMA_SERVER_BASE = (
    f"http://{config['llama_server']['host']}:{config['llama_server']['port']}"
)
LLAMA_COMPLETIONS_URL = f"{LLAMA_SERVER_BASE}/v1/completions"

# Build language lookup maps
LANG_CODE_TO_NAME = {}
VALID_LANG_CODES = set()
for lang in config['translation']['all_languages']:
    LANG_CODE_TO_NAME[lang['code']] = lang['name']
    VALID_LANG_CODES.add(lang['code'])


def get_short_name(code):
    """Get language name without parenthetical, matching original template convention.
    e.g. "Chinese (Simplified)" -> "Chinese", "English" -> "English"
    """
    full_name = LANG_CODE_TO_NAME.get(code, code)
    return re.sub(r'\s*\(.*?\)\s*', '', full_name).strip()


def build_prompt(source_lang_code, target_lang_code, input_text):
    """Build a prompt matching the translategemma model's native chat template format.

    Uses the same <start_of_turn>/<end_of_turn> special tokens and phrasing
    as the original model template, with language names looked up from config.

    The model was trained with this exact prompt structure via its Jinja template.
    We replicate it here to avoid llama-server Jinja compatibility issues while
    preserving the model's intended behaviour.
    """
    source_name = get_short_name(source_lang_code)
    target_name = get_short_name(target_lang_code)

    prompt = (
        f"<start_of_turn>user\n"
        f"You are a professional {source_name} ({source_lang_code}) to "
        f"{target_name} ({target_lang_code}) translator. Your goal is to "
        f"accurately convey the meaning and nuances of the original "
        f"{source_name} text while adhering to {target_name} grammar, "
        f"vocabulary, and cultural sensitivities.\n"
        f"Produce only the {target_name} translation, without any additional "
        f"explanations or commentary.\n\n"
        f"Please translate the following {source_name} text into "
        f"{target_name}:\n\n\n"
        f"{input_text}\n"
        f"<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )
    return prompt


def messages_to_gemma_prompt(messages, source_lang=None, target_lang=None):
    """Convert an OpenAI-format messages array into the Gemma chat template.

    System messages are prepended to the first user message (Gemma has no
    system role natively).  The returned string ends with the model turn
    marker so that llama-server continues with the assistant response.

    If *source_lang* / *target_lang* are supplied they are added as a brief
    translation hint prepended to the system context.
    """
    system_parts = []
    turns = []

    # Optional language hint – lightweight, won't interfere with a
    # caller-supplied prompt (e.g. Zotero) that already carries its own.
    if source_lang and target_lang:
        src_name = get_short_name(source_lang)
        tgt_name = get_short_name(target_lang)
        system_parts.append(
            f'Translate the following text from {src_name} ({source_lang}) '
            f'to {tgt_name} ({target_lang}). Produce only the translation.'
        )

    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'system':
            system_parts.append(content)
        elif role in ('user', 'assistant'):
            turns.append((role, content))

    # If there are no conversation turns, treat everything as a user turn
    if not turns:
        turns.append(('user', '\n\n'.join(system_parts) if system_parts else ''))

    # Prepend system content to the first user turn
    if system_parts and turns:
        first_role, first_content = turns[0]
        if first_role == 'user':
            turns[0] = ('user', '\n\n'.join(system_parts) + '\n\n' + first_content)
        else:
            # First turn is assistant → insert a synthetic user turn
            turns.insert(0, ('user', '\n\n'.join(system_parts)))

    # Build Gemma chat-template string
    prompt = ''
    for role, content in turns:
        prompt += f'<start_of_turn>{role}\n{content}\n<end_of_turn>\n'

    # Signal the start of the model's response
    prompt += '<start_of_turn>model\n'

    return prompt


def _extract_source_text(content):
    """Extract the source text from a Zotero-style translation prompt.

    Attempts to find text between 🔤 markers first, then falls back to
    [...] or 【】 brackets.  If no delimiters are found the entire
    *content* is returned as-is.
    """
    import re as _re

    # Preference order: 🔤…🔤  →  […]  →  【…】  →  raw content
    patterns = [
        (r'\U0001f524\s*(.+?)\s*\U0001f524', 'emoji'),   # 🔤...🔤
        (r'\[\s*(.+?)\s*\]',                   'bracket'), # [...]
        (r'【\s*(.+?)\s*】',                    'cjk'),     # 【...】
    ]

    for pattern, _name in patterns:
        m = _re.search(pattern, content)
        if m:
            return m.group(1).strip()

    # No delimiter found — return everything (best effort)
    return content.strip()


def extract_text_from_messages(messages):
    """Extract text to translate from an OpenAI-format messages array.

    Returns the content of the last user message. Falls back to the last
    message of any role if no user message is found.
    """
    if not messages:
        return ''
    # Prefer the last user message
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            return msg.get('content', '')
    # Fallback: last message of any role
    last = messages[-1]
    return last.get('content', '')


# --- Routes ---

@app.route('/')
def index():
    """Serve the Web UI."""
    return render_template('index.html')


@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Return language lists and defaults for the frontend."""
    return jsonify({
        'common_languages': config['translation']['common_languages'],
        'all_languages': config['translation']['all_languages'],
        'default_source_lang': config['translation']['default_source_lang'],
        'default_target_lang': config['translation']['default_target_lang'],
    })


@app.route('/api/translate', methods=['POST'])
def translate():
    """Proxy translation request to llama-server with prompt assembly + streaming."""
    data = request.get_json(force=True)

    # Validate required fields
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing required field: text'}), 400

    source_lang = data.get('source_lang', config['translation']['default_source_lang'])
    target_lang = data.get('target_lang', config['translation']['default_target_lang'])
    text = data['text']

    # Validate language codes
    if source_lang not in VALID_LANG_CODES:
        return jsonify({'error': f'unsupported language code: {source_lang}'}), 400
    if target_lang not in VALID_LANG_CODES:
        return jsonify({'error': f'unsupported language code: {target_lang}'}), 400

    # Build prompt in the model's native format
    prompt = build_prompt(source_lang, target_lang, text)

    # Use llama-server completions API (raw text prompt)
    payload = {
        'prompt': prompt,
        'stream': True,
        'temperature': 0.1,
    }

    def generate():
        """Stream tokens from llama-server to the browser."""
        try:
            resp = requests.post(
                LLAMA_COMPLETIONS_URL,
                json=payload,
                stream=True,
                timeout=(10, 120),  # (connect, read) timeout
            )
            resp.raise_for_status()

            # Force UTF-8 decoding regardless of what the response headers
            # (or charset_normalizer) report. Without this, requests may
            # default to ASCII or Latin-1 for SSE streams whose first
            # chunks are pure ASCII JSON structure, garbling non-ASCII
            # output (e.g. Chinese, Japanese, Korean, etc.).
            resp.encoding = 'utf-8'

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # SSE format: "data: {...}"
                if line.startswith('data: '):
                    data_str = line[6:]  # strip "data: " prefix
                    if data_str == '[DONE]':
                        yield 'data: {"done": true}\n\n'
                        return
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get('choices', [])
                        if choices:
                            # Completions API uses "text"
                            content = choices[0].get('text', '')
                            if content:
                                yield f'data: {{"token": {json.dumps(content)}}}\n\n'
                    except json.JSONDecodeError:
                        continue

            yield 'data: {"done": true}\n\n'

        except requests.exceptions.ConnectionError:
            yield f'data: {{"error": "llama-server unreachable"}}\n\n'
        except requests.exceptions.Timeout:
            yield f'data: {{"error": "Translation request timed out"}}\n\n'
        except Exception as e:
            yield f'data: {{"error": {json.dumps(str(e))}}}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.route('/v1/models', methods=['GET'])
def list_models():
    """OpenAI-compatible model list endpoint."""
    return jsonify({
        'object': 'list',
        'data': [
            {
                'id': 'translategemma-4b',
                'object': 'model',
                'created': int(time.time()),
                'owned_by': 'translategemma',
            },
        ],
    })


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """OpenAI-compatible Chat Completions endpoint.

    Two operating modes:

    1. **Native translation mode** (``source_lang`` + ``target_lang``
       provided) — extracts the source text from the *messages* array
       (stripping any Zotero-style prompt boilerplate and 🔤/[…] markers),
       then builds the prompt in the translategemma model's native format.
       This is the recommended mode for Zotero and other translation tools.

    2. **Raw chat mode** (no language hints) — converts the *messages*
       array verbatim into the Gemma chat template.  Use this when you
       need to send a completely custom prompt.
    """
    data = request.get_json(force=True)

    if not data or 'messages' not in data:
        return jsonify({'error': 'Missing required field: messages'}), 400

    model = data.get('model', 'translategemma-4b')
    messages = data['messages']
    stream = data.get('stream', True)
    temperature = data.get('temperature', 0.1)

    source_lang = data.get('source_lang', None)
    target_lang = data.get('target_lang', None)

    if source_lang and target_lang:
        # --- Native translation mode ---
        # Extract the actual text to translate (strip Zotero boilerplate)
        raw = extract_text_from_messages(messages)
        text = _extract_source_text(raw)

        if not text:
            return jsonify({'error': 'No text found in messages'}), 400

        # Validate language codes
        if source_lang not in VALID_LANG_CODES:
            return jsonify({'error': f'unsupported language code: {source_lang}'}), 400
        if target_lang not in VALID_LANG_CODES:
            return jsonify({'error': f'unsupported language code: {target_lang}'}), 400

        prompt = build_prompt(source_lang, target_lang, text)
    else:
        # --- Raw chat mode ---
        prompt = messages_to_gemma_prompt(messages)
        if not prompt:
            return jsonify({'error': 'No text found in messages'}), 400

    payload = {
        'prompt': prompt,
        'stream': True,
        'temperature': temperature,
    }

    if not stream:
        return _chat_completion_sync(model, payload)

    return _chat_completion_stream(model, payload)


def _chat_completion_sync(model, payload):
    """Non-streaming: collect all tokens and return a single OpenAI-format JSON."""
    try:
        resp = requests.post(
            LLAMA_COMPLETIONS_URL,
            json=payload,
            stream=True,
            timeout=(10, 120),
        )
        resp.raise_for_status()
        resp.encoding = 'utf-8'

        full_text = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith('data: '):
                data_str = line[6:]
                if data_str == '[DONE]':
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get('choices', [])
                    if choices:
                        content = choices[0].get('text', '')
                        if content:
                            full_text.append(content)
                except json.JSONDecodeError:
                    continue

        complete_text = ''.join(full_text)
        prompt_tokens = len(payload['prompt'].split())
        completion_tokens = len(complete_text.split())

        return jsonify({
            'id': f'chatcmpl-{uuid.uuid4().hex[:29]}',
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': model,
            'choices': [{
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': complete_text,
                },
                'finish_reason': 'stop',
            }],
            'usage': {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens,
            },
        })

    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'llama-server unreachable'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Translation request timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _chat_completion_stream(model, payload):
    """Streaming: yield OpenAI-format SSE chunks."""
    chat_id = f'chatcmpl-{uuid.uuid4().hex[:29]}'
    created = int(time.time())

    def generate():
        """Stream tokens in OpenAI SSE format."""
        first_chunk = True
        try:
            resp = requests.post(
                LLAMA_COMPLETIONS_URL,
                json=payload,
                stream=True,
                timeout=(10, 120),
            )
            resp.raise_for_status()
            resp.encoding = 'utf-8'

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get('choices', [])
                        if choices:
                            content = choices[0].get('text', '')
                            if content:
                                if first_chunk:
                                    # First chunk includes role declaration
                                    yield (
                                        'data: '
                                        + json.dumps({
                                            'id': chat_id,
                                            'object': 'chat.completion.chunk',
                                            'created': created,
                                            'model': model,
                                            'choices': [{
                                                'index': 0,
                                                'delta': {
                                                    'role': 'assistant',
                                                    'content': content,
                                                },
                                                'finish_reason': None,
                                            }],
                                        }, ensure_ascii=False)
                                        + '\n\n'
                                    )
                                    first_chunk = False
                                else:
                                    yield (
                                        'data: '
                                        + json.dumps({
                                            'id': chat_id,
                                            'object': 'chat.completion.chunk',
                                            'created': created,
                                            'model': model,
                                            'choices': [{
                                                'index': 0,
                                                'delta': {
                                                    'content': content,
                                                },
                                                'finish_reason': None,
                                            }],
                                        }, ensure_ascii=False)
                                        + '\n\n'
                                    )
                    except json.JSONDecodeError:
                        continue

            # Final chunk with finish_reason
            yield (
                'data: '
                + json.dumps({
                    'id': chat_id,
                    'object': 'chat.completion.chunk',
                    'created': created,
                    'model': model,
                    'choices': [{
                        'index': 0,
                        'delta': {},
                        'finish_reason': 'stop',
                    }],
                })
                + '\n\n'
            )
            yield 'data: [DONE]\n\n'

        except requests.exceptions.ConnectionError:
            err_chunk = json.dumps({
                'error': {'message': 'llama-server unreachable', 'type': 'connection_error'}
            })
            yield f'data: {err_chunk}\n\n'
            yield 'data: [DONE]\n\n'
        except requests.exceptions.Timeout:
            err_chunk = json.dumps({
                'error': {'message': 'Translation request timed out', 'type': 'timeout'}
            })
            yield f'data: {err_chunk}\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            err_chunk = json.dumps({
                'error': {'message': str(e), 'type': 'server_error'}
            })
            yield f'data: {err_chunk}\n\n'
            yield 'data: [DONE]\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


if __name__ == '__main__':
    ui_config = config['web_ui']
    print(f"Starting TranslateGemma Web UI on http://{ui_config['host']}:{ui_config['port']}")
    app.run(
        host=ui_config['host'],
        port=ui_config['port'],
        debug=False,
    )
