import re
import signal
import sys
import threading
from urllib.parse import urlparse

import requests
from flask import Flask, request, Response, jsonify

from TentaclePreview import output
from TentaclePreview import tentacle_preview as tentacle

app = Flask(__name__, static_folder=None)


@app.route('/')
def main_page():  # put application's code here
    result = "<table><tr> <th>Tentacle</th> <th>local url</th> <th>Build</th> <th>Start</th> </tr>"

    for tenty in tentacle.TENTACLES_LIST:
        build_ok = "WAIT" if tenty.is_build_success is None else "OK" if tenty.is_build_success else "FAIL"
        start_ok = "WAIT" if tenty.is_start_success is None else "OK" if tenty.is_start_success else "FAIL"

        result += "<tr>"
        result += f"<td><a href=\"{request.scheme}://{request.host}/tentacle/{tenty.name}\">{tenty.name}</a></td>"
        result += f"<td><a href={request.scheme}://{tenty.url}>{tenty.url}</a></td>"
        result += f"<td>{build_ok}</td>"
        result += f"<td>{start_ok}</td>"
        result += "</tr>"

    result += "</table>"
    return result

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if "zen" in request.json:
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
        print(referer)
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
    if 1 < len(sys.argv):
        threading.Thread(target=tentacle.init, args=[sys.argv[1]]).start()
    else:
        threading.Thread(target=tentacle.init).start()

    app.run(host="0.0.0.0", port=4999)

