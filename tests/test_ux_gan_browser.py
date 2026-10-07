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

# A frontend-only fixture: document collections, contextual actions and retained
# navigation state. It tests browser evidence/operations, not skill design quality.
DOCUMENTS="""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>文書管理テスト</title>
<style>body{font-family:sans-serif;margin:24px auto;padding:16px;max-width:800px}
button,select,textarea{font-size:16px;padding:10px}li{margin:16px 0}textarea{display:block;box-sizing:border-box;width:100%;min-height:120px}
[hidden]{display:none}label{display:inline-block;margin:8px 0}</style>
<section id="collection"><h1>文書</h1><label for="kind">文書の種類</label>
<select id="kind"><option value="all">すべて</option><option value="pdf">PDF</option></select>
<ul id="documents"></ul><div id="bulk" hidden><span id="count"></span>
<button id="archive">選択した文書をアーカイブ</button></div></section>
<section id="detail" hidden><a href="#">文書一覧に戻る</a><h1 id="name"></h1>
<label for="note">文書のメモ</label><textarea id="note"></textarea><button id="save-note">メモを保存</button>
<h2>関連文書</h2><a id="related"></a></section><p id="result" role="status"></p>
<script>
const docs=[{id:'a',name:'設計仕様',kind:'pdf',related:'b'},
{id:'b',name:'利用規約',kind:'pdf',related:'a'},{id:'c',name:'作業メモ',kind:'note',related:'a'}];
const selected=new Set(),drafts=new Map(),archived=new Set();
const get=id=>document.getElementById(id);
function render(){
 const id=location.hash.slice(1),doc=docs.find(d=>d.id===id);
 get('collection').hidden=Boolean(doc);get('detail').hidden=!doc;
 if(doc){get('name').textContent=doc.name;get('note').value=drafts.get(id)||'';
 const related=docs.find(d=>d.id===doc.related);get('related').href='#'+related.id;
 get('related').textContent=related.name;return;}
 get('documents').replaceChildren();
 for(const d of docs.filter(d=>!archived.has(d.id)&&(get('kind').value==='all'||d.kind===get('kind').value))){
 const li=document.createElement('li'),label=document.createElement('label'),box=document.createElement('input'),link=document.createElement('a');
 box.type='checkbox';box.id='select-'+d.id;box.checked=selected.has(d.id);
 box.onchange=()=>{box.checked?selected.add(d.id):selected.delete(d.id);updateBulk()};
 label.append(box,document.createTextNode(d.name+'を選択'));link.href='#'+d.id;link.id='open-'+d.id;link.textContent=d.name;
 li.append(label,document.createTextNode(' · '),link);get('documents').append(li);}
 if(!get('documents').children.length){const li=document.createElement('li');li.textContent='該当する文書はありません';get('documents').append(li)}
 updateBulk();
}
function updateBulk(){get('bulk').hidden=!selected.size;get('count').textContent=selected.size+'件を選択中'}
get('kind').onchange=render;
get('note').oninput=()=>drafts.set(location.hash.slice(1),get('note').value);
get('save-note').onclick=()=>get('result').textContent=get('name').textContent+'のメモを保存しました: '+get('note').value;
get('archive').onclick=()=>{if(confirm(selected.size+'件の文書をアーカイブしますか？')){
 const count=selected.size;for(const id of selected)archived.add(id);selected.clear();render();
 get('result').textContent=count+'件の文書をアーカイブしました';}};
addEventListener('hashchange',render);render();
</script></html>"""


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

    def test_object_navigation_retains_filter_selection_and_draft_then_bulk_operation(self):
        (self.base/"documents.html").write_text(DOCUMENTS)
        self.tool("ux_navigate",url=self.url+"/documents.html")
        self.tool("ux_select",selector="#kind",value="pdf")
        self.tool("ux_click",selector="#select-a")
        self.tool("ux_click",selector="#select-b")
        self.tool("ux_click",selector="#open-a")
        self.tool("ux_fill",selector="#note",value="公開前に確認する下書き")
        self.tool("ux_click",selector="#related")
        related = json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertTrue(related["url"].endswith("#b"))
        self.tool("ux_back")
        self.tool("ux_click",selector="#save-note")
        saved = json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertIn("設計仕様のメモを保存しました: 公開前に確認する下書き",saved["visible_text"])
        self.tool("ux_back")
        collection = json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertIn("2件を選択中",collection["visible_text"])
        self.assertNotIn("作業メモ",collection["visible_text"])
        self.tool("ux_resize",width=768,height=1024)
        pending = self.tool("ux_click",selector="#archive")
        self.assertIn("2件の文書",json.loads(pending["content"][0]["text"])["pending_dialog"])
        self.tool("ux_dialog",accept=False)
        cancelled = json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertIn("2件を選択中",cancelled["visible_text"])
        self.tool("ux_click",selector="#archive")
        self.tool("ux_dialog",accept=True)
        mobile = self.tool("ux_resize",width=390,height=844)
        meta = json.loads(mobile["content"][0]["text"])
        result = json.loads(self.tool("ux_inspect")["content"][0]["text"])
        self.assertEqual(result["title"],"文書管理テスト")
        self.assertIn("該当する文書はありません",result["visible_text"])
        self.assertIn("2件の文書をアーカイブしました",result["visible_text"])
        self.assertFalse(result["console"])
        self.assertEqual(meta["frames"][-1]["viewport"],{"width":390,"height":844})
        receipts = [json.loads(s) for s in (self.out/"browser-receipts.jsonl").read_text().splitlines()]
        frames = [r for r in receipts if r["kind"]=="frame"]
        self.assertEqual({(r["viewport"]["width"],r["viewport"]["height"]) for r in frames},
                         {(1440,900),(768,1024),(390,844)})
        for frame in frames:
            self.assertEqual(hashlib.sha256(Path(frame["path"]).read_bytes()).hexdigest(),frame["sha256"])

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
