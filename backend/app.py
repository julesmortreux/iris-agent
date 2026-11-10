"""Service HTTP de l'agent Iris."""

import json
import logging
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend import config
from backend.agent import run_agent

MAX_MESSAGE_CHARS = 500
MAX_HISTORY_MESSAGES = 20
MAX_EXCLUDED_IDS = 200

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger('iris')

if not config.MISTRAL_API_KEY:
    logger.warning("MISTRAL_API_KEY non définie")

app = Flask(__name__, static_folder=config.PUBLIC_DIR, static_url_path='')
CORS(app, origins=config.CORS_ORIGINS)


def _error(message: str, status: int):
    return jsonify({'success': False, 'error': message}), status


@app.post('/api/chat')
def chat():
    """Reçoit {message, history, exclude_ids} et renvoie la réponse d'Iris."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('Corps JSON attendu', 400)
    message = str(data.get('message') or '').strip()
    history = data.get('history') or []
    exclude_ids = data.get('exclude_ids') or []
    if not message:
        return _error('Message vide', 400)
    if len(message) > MAX_MESSAGE_CHARS:
        return _error(f'Message trop long ({MAX_MESSAGE_CHARS} caractères au plus)', 400)
    if not isinstance(history, list) or not isinstance(exclude_ids, list):
        return _error('history et exclude_ids doivent être des listes', 400)
    history = [m for m in history if isinstance(m, dict)][-MAX_HISTORY_MESSAGES:]
    exclude_ids = [str(i) for i in exclude_ids][-MAX_EXCLUDED_IDS:]

    request_id = uuid.uuid4().hex[:12]
    try:
        reply = run_agent(message, history, exclude_ids)
    except Exception:
        logger.exception("Erreur sur /api/chat (%s)", request_id)
        return _error('Erreur interne', 500)

    trace = asdict(reply.pop('trace'))
    # Une ligne JSON par requête : exploitable telle quelle par un outil de supervision.
    logger.info(json.dumps({
        'request_id': request_id, 'intent': trace['intent'], 'outcome': trace['outcome'],
        'tools': reply['sources_used'], 'contacts': len(reply['contacts']), 'hunters': len(reply['hunters']),
        'timings_s': {k: round(v, 2) for k, v in trace['timings'].items()},
        'tokens': sum(u['input_tokens'] + u['output_tokens'] for u in trace['usage']),
    }, ensure_ascii=False))
    response = jsonify({'success': True, **reply})
    response.headers['X-Request-Id'] = request_id
    return response


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.get('/')
def demo():
    return app.send_static_file('index.html')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=config.PORT, debug=config.FLASK_DEBUG)
