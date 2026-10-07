"""Opt-in real Chromium checks; default unit suite does not download browsers."""
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=ROOT/"tools/codex-ux-stack/skill/scripts/visual-browser.cjs"
HTML="""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>投稿作成テスト</title>
<style>body{font-family:sans-serif;margin:40px auto;padding:20px;max-width:600px}input,button{font-size:18px;padding:12px}input{box-sizing:border-box;width:100%}button{margin-top:16px}#error{color:#a00}</style>
<h1>投稿を作る</h1><label for="title">投稿タイトル</label><input id="title">
<button id="save">Go</button><button id="cancel">キャンセル</button>
<p id="error" role="alert"></p><p id="result" role="status"></p>
<script>save.onclick=()=>{if(!title.value.trim()){error.textContent='投稿タイトルを入力してください';return}
error.textContent='';result.textContent='保存しました: '+title.value};
cancel.onclick=()=>{if(confirm('入力内容を破棄しますか？')){title.value='';result.textContent='取り消しました'}};</script>
</html>"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


@unittest.skipUnless(os.getenv("UX_GAN_RUNTIME"),"Set UX_GAN_RUNTIME to an installed test runtime")
class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="ux-browser-check-")
        self.base=Path(self.tmp.name)
        (self.base/"index.html").write_text(HTML)
        handler=functools.partial(Quiet,directory=str(self.base))
        self.server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_port}"
        self.out=self.base/"screenshots"
        env=dict(os.environ,UX_GAN_SCREENSHOTS=str(self.out),UX_GAN_TARGET=self.url)
        self.proc=subprocess.Popen(["node",str(BRIDGE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,text=True,env=env)
        self.request_id=0
        self.rpc("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}})

    def tearDown(self):
        self.proc.stdin.close()
        try:self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=5)
        self.proc.stdout.close();self.proc.stderr.close()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        self.tmp.cleanup()

    def rpc(self,method,params):
        self.request_id+=1
        self.proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":self.request_id,"method":method,"params":params})+"\n")
        self.proc.stdin.flush()
        r=json.loads(self.proc.stdout.readline())
        self.assertEqual(r["id"],self.request_id)
        self.assertNotIn("error",r)
        return r["result"]

    def tool(self,name,**args):
        result=self.rpc("tools/call",{"name":name,"arguments":args})
        self.assertFalse(result.get("isError"),result)
        return result

    def test_actual_error_success_mobile_and_before_after_receipts(self):
        self.tool("ux_navigate",url=self.url)
        self.tool("ux_click",selector="#save")
        result=json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertIn("投稿タイトルを入力してください",result["visible_text"])
        self.tool("ux_fill",selector="#title",value="初めての投稿")
        saved=self.tool("ux_click",selector="#save")
        self.assertEqual(len([c for c in saved["content"] if c["type"]=="image"]),2)
        result=json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertIn("保存しました: 初めての投稿",result["visible_text"])
        mobile=self.tool("ux_resize",width=390,height=844)
        meta=json.loads(mobile["content"][0]["text"])
        self.assertEqual(meta["frames"][-1]["viewport"],{"width":390,"height":844})
        self.assertEqual(meta["title"],"投稿作成テスト")
        self.assertFalse(meta["console"])
        receipts=[json.loads(s) for s in (self.out/"browser-receipts.jsonl").read_text().splitlines()]
        frames=[r for r in receipts if r["kind"]=="frame"]
        self.assertGreaterEqual(len(frames),9)
        self.assertEqual(len({r["path"] for r in frames}),len(frames))
        for frame in frames:
            self.assertEqual(hashlib.sha256(Path(frame["path"]).read_bytes()).hexdigest(),frame["sha256"])

    def test_external_reference_is_view_only(self):
        self.tool("ux_navigate",url=self.url.replace("127.0.0.1","localhost"))
        result=self.rpc("tools/call",{"name":"ux_fill","arguments":{"selector":"#title","value":"external"}})
        self.assertTrue(result["isError"])
        self.assertIn("view-only",result["content"][0]["text"])
        self.tool("ux_capture")

    def test_confirm_can_be_cancelled_then_accepted_without_blocking(self):
        self.tool("ux_navigate",url=self.url)
        self.tool("ux_fill",selector="#title",value="保持する入力")
        pending=self.tool("ux_click",selector="#cancel")
        self.assertIn("入力内容を破棄",json.loads(pending["content"][0]["text"])["pending_dialog"])
        cancelled=self.tool("ux_dialog",accept=False)
        self.assertTrue(any(c["type"]=="image" for c in cancelled["content"]))
        self.tool("ux_click",selector="#save")
        text=json.loads(self.tool("ux_inspect")["content"][0]["text"])["visible_text"]
        self.assertIn("保存しました: 保持する入力",text)
        self.tool("ux_click",selector="#cancel")
        self.tool("ux_dialog",accept=True)
        text=json.loads(self.tool("ux_inspect")["content"][0]["text"])["visible_text"]
        self.assertIn("取り消しました",text)
        self.tool("ux_click",selector="#save")
        text=json.loads(self.tool("ux_inspect")["content"][0]["text"])["visible_text"]
        self.assertIn("投稿タイトルを入力してください",text)


if __name__=="__main__":unittest.main()
