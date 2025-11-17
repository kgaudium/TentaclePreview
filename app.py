import re
import signal
import sys
import threading
from typing import Any
from urllib.parse import urlparse

import requests
from flask import Flask, request, Response, jsonify, render_template
from flask_socketio import SocketIO, emit

from TentaclePreview import output
from TentaclePreview import tentacle_preview as tentacle
from TentaclePreview.output import LogType

app = Flask(__name__, static_folder="tentacle_preview_static")
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def main_page():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    output.log('WebSocket: client connected', 'info')
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def on_disconnect():
    output.log('WebSocket: client disconnected', 'info')

@socketio.on('request_status')
def on_request_status():
    tentacles = [
        {
            'name': t.name,
            'url': t.url,
            'is_build_success': t.is_build_success,
            'is_start_success': t.is_start_success,
            'last_commit': t.last_commit
        }
        for t in tentacle.TENTACLES_LIST
    ]
    emit('status_update', {'tentacles': tentacles})

@socketio.on('request_logs')
def on_request_logs(data):
    tentacle_name = data.get('tentacle')
    log_type = data.get('log_type', 'build')

    tenty = tentacle.get_tenty_by_name(tentacle_name)
    if not tenty:
        output.log(f'WebSocket: Tentacle "{tentacle_name}" not found', 'warning')
        return

    logs = tenty.get_logs(log_type)
    emit('logs_update', {
        'tentacle': tentacle_name,
        'log_type': log_type,
        'logs': logs,
        'stream': False
    })

def broadcast_status_update(name, build_status, start_status):
    try:
        socketio.emit('status_update', {
            'tentacle': name,
            'build_status': build_status,
            'start_status': start_status
        })
        # output.log(f'Broadcast status: {name}, build={build_status}, start={start_status}')
    except Exception as e:
        output.log(f'Error broadcasting status: {e}', 'error')

def broadcast_logs_update(name, log_type, logs, stream=False):
    try:
        socketio.emit('logs_update', {
            'tentacle': name,
            'log_type': log_type,
            'logs': logs,
            'stream': bool(stream)
        })
        # output.log(f'Broadcast logs: {name}, type={log_type}, stream={stream}')
    except Exception as e:
        output.log(f'Error broadcasting logs: {e}', 'error')


def broadcast_new_system_log(log_entry: output.LogEntry, **kwargs: dict[str, Any]) -> None:
    global socketio

    try:
        socketio.emit('system_logs_update', {
            'log_type': log_entry.log_type.value,
            'message': log_entry.message,
            'time': log_entry.time,
        })
    except Exception as e:
        print(e)

@app.route('/api/tentacles')
def api_tentacles():
    tentacles_data = []
    for tenty in tentacle.TENTACLES_LIST:
        tentacles_data.append({
            'name': tenty.name,
            'url': tenty.url,
            'is_build_success': tenty.is_build_success,
            'is_start_success': tenty.is_start_success,
            'last_commit': tenty.last_commit
        })

    return jsonify({
        'tentacles': tentacles_data,
        'total': len(tentacles_data)
    })


@app.route('/api/tentacles/<tentacle_name>/logs/<log_type>')
def api_tentacle_logs(tentacle_name, log_type):
    target_tentacle = tentacle.get_tenty_by_name(tentacle_name)
    if target_tentacle is None:
        return jsonify({'error': f'Tentacle {tentacle_name} not found'}), 404

    if log_type not in ['build', 'start']:
        return jsonify({'error': 'Invalid log type. Must be "build" or "start"'}), 400

    try:
        logs = target_tentacle.get_logs(log_type)
        return jsonify({
            'tentacle': tentacle_name,
            'log_type': log_type,
            'logs': logs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tentacles/<tentacle_name>/restart')
@app.route('/api/tentacles/<tentacle_name>/restart/<clean>')
def api_tentacle_restart(tentacle_name, clean='false'):
    target_tentacle = tentacle.get_tenty_by_name(tentacle_name)
    if target_tentacle is None:
        return jsonify({'error': f'Tentacle {tentacle_name} not found'}), 404

    clean = str(clean).lower()
    if clean not in ['true', 'false']:
        return jsonify({'error': 'Invalid clean. Must be "true" or "false"'}), 400

    try:
        target_tentacle.update(clean == 'true')
        return jsonify({
            'is_clean': clean,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tentacles/system-logs')
def api_system_logs_get():
    # TODO add line limit as argument
    return jsonify({"logs": tentacle.system_logs_to_json()})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if "zen" in request.json:
            # GitHub webhook ping event
            return jsonify({"status": "ping"}), 200

        threading.Thread(target=tentacle.proceed_webhook_event, args=[request.json]).start()
        return jsonify({"status": "update_started"}), 200

    except Exception as e:
        output.log(f"Unexpected error: {str(e)}", "error")
        return jsonify({"status": "error", "message": str(e)}), 500


def inject_base_and_rewrite_paths(content: str, branch: str) -> str:
    base_href = f"/tentacle/{branch}/"

    content = content.replace("<head>", f"<head><base href='{base_href}'>")

    def rewrite_paths(match):
        full = match.group(0)
        prefix = match.group(1)
        quote = match.group(2)
        path = match.group(3)

        if path.startswith("http") or path.startswith(base_href):
            return full

        return f'{prefix}{quote}{base_href}{path.lstrip("/")}{quote}'

    content = re.sub(r'((?:src|href|action)=)("|\')(/[^"\']+)\2', rewrite_paths, content)
    content = re.sub(r'url\(("|\')(/[^"\']+)\1\)', rewrite_paths, content)

    return content


def extract_branch_from_referer():
    referer = request.headers.get("Referer", "")
    match = re.search(r"/tentacle/([^/]+)(?:/|$)", referer)
    if match:
        return match.group(1)
    return None


def proxy_request_to(target_url):
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )

        content = resp.content
        headers = dict(resp.raw.headers)
        content_type = headers.get("Content-Type", "")

        branch = request.view_args.get("branch") or extract_branch_from_referer()

        if "text/html" in content_type and branch:
            text = content.decode("utf-8", errors="ignore")
            text = inject_base_and_rewrite_paths(text, branch)
            content = text.encode("utf-8")

        excluded_headers = {
            'content-encoding', 'content-length', 'transfer-encoding',
            'connection', 'content-security-policy', 'x-frame-options',
            'cross-origin-opener-policy', 'cross-origin-resource-policy',
            'cross-origin-embedder-policy'
        }
        filtered_headers = [(name, value) for name, value in resp.raw.headers.items()
                            if name.lower() not in excluded_headers]

        return Response(content, resp.status_code, filtered_headers)
    except requests.exceptions.RequestException as e:
        return f"Error proxying: {e}", 502


@app.route('/tentacle/<branch>/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route('/tentacle/<branch>/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_to_tentacle(branch, path=''):
    target_tentacle = tentacle.get_tenty_by_name(branch)

    if target_tentacle is None:
        return f"Tentacle for branch '{branch}' not found", 404

    rewritten_path = f"{path}" if path else ""

    query = request.query_string.decode()
    target_url = f"{request.scheme}://{target_tentacle.url}/{rewritten_path}"
    if query:
        target_url += f"?{query}"

    return proxy_request_to(target_url)


@app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy_static_fallback(path):
    referer = request.headers.get("Referer")
    if not referer:
        return f"Unknown path: /{path}", 404

    # get tentacle name from referer url
    # TODO change regex - branch names CAN contains slashes
    match = re.search(r"/tentacle/([^/]+)(?:/|$)", urlparse(referer).path)
    if not match:
        return f"Unknown path: /{path}", 404

    branch = match.group(1)
    target_tentacle = tentacle.get_tenty_by_name(branch)
    if not target_tentacle:
        return f"Tentacle for branch '{branch}' not found", 404

    # Pass   request to the tentacle without `/tentacle/name`
    query = request.query_string.decode()
    target_url = f"{request.scheme}://{target_tentacle.url}/{path}"
    if query:
        target_url += f"?{query}"

    return proxy_request_to(target_url)


def graceful_shutdown(*_):
    print()
    output.log("Got shutdown signal", "warning")
    tentacle.stop_tentacles()
    sys.exit(0)


signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


if __name__ == '__main__':
    try:
        output.on_log_event.append(broadcast_new_system_log)

        from TentaclePreview.tentacle import Tentacle
        Tentacle.set_broadcast_callbacks(broadcast_logs_update, broadcast_status_update)

        if len(sys.argv) > 1:
            threading.Thread(target=tentacle.init, args=[sys.argv[1]]).start()
        else:
            threading.Thread(target=tentacle.init).start()

        socketio.run(app, host="0.0.0.0", port=4999, allow_unsafe_werkzeug=True)
    except Exception as e:
        output.log(f"Failed to start server: {e}", "error")
