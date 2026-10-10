#!/usr/bin/env python3
"""Explicit synthetic file and local-browser final-output comparison (stdlib host).

Use an existing Node dependency directory via --deps; no installation, user MCP
registration or hooks are changed. Public Context7/Parallel retrieval is sampled
separately and must not be interpreted as a reasoning-accuracy measurement.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request


def body(result):
    return '\n'.join(c.get('text', '') for c in result.get('content', []))


class MCP:
    def __init__(self, command, home, cwd):
        self.command, self.home, self.cwd, self.counter = command, home, cwd, 0

    async def start(self):
        self.home.mkdir(parents=True, exist_ok=True)
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.home), 'LANG': 'C.UTF-8',
               'XDG_CACHE_HOME': str(self.home/'cache'), 'DO_NOT_TRACK': '1',
               'TOKEN_OPTIMIZER_UPDATE_CHECK': '0', 'DISABLE_THOUGHT_LOGGING': 'true'}
        start = time.monotonic()
        self.process = await asyncio.create_subprocess_exec(*self.command, cwd=self.cwd, env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True, limit=8*1024*1024)
        await self.rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                                     'clientInfo': {'name': 'ecc-effectiveness-evaluation', 'version': '1.0'}})
        self.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        await self.process.stdin.drain()
        self.tools = (await self.rpc('tools/list', {}))['tools']
        self.startup_seconds = time.monotonic()-start
        return self

    async def rpc(self, method, params):
        self.counter += 1
        request_id = self.counter
        self.process.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})+'\n').encode())
        await self.process.stdin.drain()
        async def response():
            while True:
                line = await self.process.stdout.readline()
                if not line: raise RuntimeError('MCP exited before returning a result')
                try: result = json.loads(line)
                except ValueError: continue
                if result.get('id') == request_id:
                    if 'error' in result: raise RuntimeError(str(result['error']))
                    return result['result']
        return await asyncio.wait_for(response(), 60)

    async def call(self, name, arguments):
        return await self.rpc('tools/call', {'name': name, 'arguments': arguments})

    async def close(self):
        if hasattr(self, 'process'):
            try: os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: await asyncio.wait_for(self.process.wait(), 3)
            except asyncio.TimeoutError:
                try: os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                await self.process.wait()


def file_answer(content):
    import re
    expected_types = {'retry_limit': int, 'max_count': int, 'request_id': str, 'error': str, 'guard': str}
    answer = {}
    for key, convert in expected_types.items():
        match = re.search(r'(?m)^'+key+r'=([^\r\n]+)', content)
        if match: answer[key] = convert(match[1])
    return answer


def http_rpc(url, payload, session=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
               'MCP-Protocol-Version': '2024-11-05', 'User-Agent': 'ecc-effectiveness-check/1.0'}
    if session: headers['Mcp-Session-Id'] = session
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        text = response.read(4*1024*1024).decode()
        session = response.headers.get('Mcp-Session-Id', session)
    values = [line[6:] for line in text.splitlines() if line.startswith('data: ')]
    result = json.loads(values[-1] if values else text)
    return result, session


async def run(args, scratch):
    deps = args.deps.resolve()
    versions = {}
    for name in ['@ooples/token-optimizer-mcp', '@upstash/context7-mcp', '@playwright/mcp', 'chrome-devtools-mcp', 'playwright']:
        versions[name] = json.loads((deps/name/'package.json').read_text())['version']
    expected = {'retry_limit': 3, 'max_count': 1700, 'request_id': 'req-01731', 'error': 'E_CONFLICT', 'guard': 'approval_required'}
    document = '\n'.join(f'background_{i}=synthetic unchanged detail' for i in range(1500))+'\n'
    document += '\n'.join(f'{key}={value}' for key, value in expected.items())+'\n'
    file = scratch/'fixture.txt'; file.write_text(document)
    cases = ['first-read', 'same-session-repeat', 'new-session-shared-cache', 'new-session-explicit-full']
    contract = {'file_tasks': [{'id': name, 'input': {'document_sha256': hashlib.sha256(document.encode()).hexdigest(),
                    'context_has_prior_content': name=='same-session-repeat', 'explicit_full': name=='new-session-explicit-full'},
                    'expected': expected} for name in cases],
                'browser_tasks': [{'id': 'quantity-'+str(q), 'input': {'quantity': q, 'unit_price': 170}, 'expected': str(q*170)} for q in [10, 11]],
                'primary': 'Exact final extracted values/DOM result, not tools/list or response length',
                'controls': 'Same synthetic document/query and same locally owned HTML/Chrome for every method; warm time and startup reported separately',
                'token_scope': 'Returned UTF-8 bytes only; no claim about billed tokens', 'versions': versions}
    encoded = json.dumps(contract, sort_keys=True).encode(); contract_sha = hashlib.sha256(encoded).hexdigest()
    (args.out/'tools-contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2)+'\n')
    rows, public = [], []
    if args.browser_only:
        previous = json.loads((args.out/'tools-results.json').read_text())
        rows = [r for r in previous['rows'] if r['candidate'] in ['native', 'token-optimizer']]
        public = previous['public_retrieval']
    def save():
        (args.out/'tools-results.json').write_text(json.dumps({'contract_sha256': contract_sha, 'rows': rows, 'public_retrieval': public,
                    'checked_at': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2)+'\n')
    node = shutil.which('node')
    for repetition in range(0 if args.browser_only else 2):
        home = scratch/('optimizer-home-'+str(repetition))
        command = [node, str(deps/'@ooples/token-optimizer-mcp/dist/server/index.js')]
        first = await MCP(command, home, scratch).start()
        prior = ''
        for case in cases:
            if case == 'new-session-shared-cache':
                await first.close(); first = await MCP(command, home, scratch).start(); prior = ''
            start = time.monotonic()
            native = subprocess.run(['cat', str(file)], capture_output=True, text=True, check=True).stdout
            rows.append({'task_id': case, 'trial': repetition+1, 'candidate': 'native', 'output': file_answer(native),
                         'elapsed_seconds': time.monotonic()-start, 'response_bytes': len(native.encode()), 'calls': 1})
            start = time.monotonic(); count_before = first.counter
            parameters = {'path': str(file), 'maxSize': 200000}
            if case == 'new-session-explicit-full': parameters['diffMode'] = False
            response = await first.call('smart_read', parameters)
            contents = [body(response)]
            ref = response.get('_meta', {}).get('tokenOptimizer', {}).get('disclosureRef')
            if ref: contents.append(body(await first.call('expand', {'ref': ref, 'reason': 'Need exact required contract fields for independent evaluation'})))
            text = '\n'.join(contents)
            effective = prior+'\n'+text if case=='same-session-repeat' else text
            rows.append({'task_id': case, 'trial': repetition+1, 'candidate': 'token-optimizer', 'output': file_answer(effective),
                         'elapsed_seconds': time.monotonic()-start, 'startup_seconds': first.startup_seconds,
                         'response_bytes': len(text.encode()), 'calls': first.counter-count_before,
                         'tool_error': response.get('isError', False), 'reply_excerpt': text[:160]})
            if case=='first-read': prior=text
            save()
        await first.close()
    # A local, synthetic JavaScript page; no production browser profile or service.
    html = '<!doctype html><title>ECC fixture</title><input id="quantity"><button id="compute">Calculate</button><output id="result"></output><script>document.querySelector("#compute").onclick=()=>{document.querySelector("#result").textContent=String(Number(document.querySelector("#quantity").value)*170)}</script>'
    (scratch/'index.html').write_text(html)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(scratch)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_port}/index.html'
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    native_script = scratch/'native-browser.mjs'
    native_script.write_text('import {chromium} from '+json.dumps(str(deps/'playwright/index.mjs'))+';\n'
        'const b=await chromium.launch({headless:true,executablePath:'+json.dumps(chrome)+'});const p=await b.newPage();'
        'for(const q of [10,11]){const t=performance.now();await p.goto('+json.dumps(url)+');await p.locator("#quantity").fill(String(q));await p.locator("#compute").click();'
        'console.log(JSON.stringify({task_id:"quantity-"+q,output:await p.locator("#result").textContent(),elapsed_seconds:(performance.now()-t)/1000}));}await b.close();')
    for repetition in range(2):
        completed = subprocess.run([node, str(native_script)], text=True, capture_output=True, timeout=60, check=True)
        for line in completed.stdout.splitlines():
            row = json.loads(line); row.update(candidate='native-browser', trial=repetition+1); rows.append(row)
        for name, command in [('playwright', [node, str(deps/'@playwright/mcp/cli.js'), '--headless', '--isolated', '--executable-path', chrome]),
                              ('chrome-devtools', [node, str(deps/'chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js'), '--headless', '--isolated', '--no-usage-statistics', '--no-performance-crux'])]:
            mcp = await MCP(command, scratch/(name+str(repetition)), scratch).start()
            try:
                for quantity in [10, 11]:
                    start = time.monotonic()
                    function = '()=>{document.querySelector("#quantity").value='+json.dumps(str(quantity))+';document.querySelector("#compute").click();return {result:document.querySelector("#result").textContent};}'
                    if name=='playwright':
                        await mcp.call('browser_navigate', {'url': url})
                        response = await mcp.call('browser_evaluate', {'function': function})
                    else:
                        import re
                        created = await mcp.call('new_page', {'url': url})
                        page_match = re.search(r'(?m)^\s*(\d+):.*'+re.escape(url), body(created))
                        if not page_match:
                            raise RuntimeError('Cannot identify owned page from actual MCP response: '+body(created)[:350])
                        response = await mcp.call('evaluate_script', {'pageId': int(page_match[1]), 'function': function})
                    import re
                    match = re.search(r'"result"\s*:\s*"(\d+)"', body(response))
                    rows.append({'task_id': 'quantity-'+str(quantity), 'trial': repetition+1, 'candidate': name,
                                 'output': match[1] if match else None, 'elapsed_seconds': time.monotonic()-start,
                                 'startup_seconds': mcp.startup_seconds, 'tool_error': response.get('isError', False), 'reply_excerpt': body(response)[:400]})
                    save()
            finally: await mcp.close()
    server.shutdown(); server.server_close()
    if args.browser_only:
        save()
        print('Saved corrected browser outputs; previous file/retrieval measurements retained.', flush=True)
        return
    context7 = await MCP([node, str(deps/'@upstash/context7-mcp/dist/index.js')], scratch/'context7', scratch).start()
    try:
        for question in ['Python requests timeout is not a total response download deadline', 'Pydantic v2 field_validator mode before raw input']:
            start = time.monotonic()
            library = 'requests' if 'requests' in question else 'pydantic'
            response = await context7.call('resolve-library-id', {'libraryName': library, 'query': question})
            library_id = '/psf/requests' if library=='requests' else '/pydantic/pydantic'
            docs = await context7.call('query-docs', {'libraryId': library_id, 'query': question})
            public.append({'candidate': 'context7', 'query': question, 'elapsed_seconds': time.monotonic()-start,
                           'tool_error': bool(response.get('isError') or docs.get('isError')), 'response': body(docs)})
            save()
    finally: await context7.close()
    try:
        start=time.monotonic()
        initialization, session = http_rpc('https://search.parallel.ai/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'ecc-benchmark', 'version': '1'}}})
        result, session = http_rpc('https://search.parallel.ai/mcp', {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}, session)
        names = [t['name'] for t in result.get('result', {}).get('tools', [])]
        public.append({'candidate': 'parallel-search', 'stage': 'discovery', 'tool_names': names, 'elapsed_seconds': time.monotonic()-start})
        query = 'Python Requests official documentation timeout is not a time limit on the entire response download'
        result, _ = http_rpc('https://search.parallel.ai/mcp', {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
            'params': {'name': 'web_search', 'arguments': {'objective': query, 'search_queries': [query]}}}, session)
        public.append({'candidate': 'parallel-search', 'query': query, 'response': result.get('result', result)})
    except Exception as error:
        public.append({'candidate': 'parallel-search', 'error': type(error).__name__+': '+str(error)[:200]})
    save()
    print('Saved actual file/browser outputs and separate public-retrieval observations.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--browser-only', action='store_true', help='Keep collected file/retrieval evidence and repeat only the browser experiment')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ecc-mcp-tools-') as temporary:
        asyncio.run(run(args, Path(temporary)))


if __name__ == '__main__': main()
