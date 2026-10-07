#!/usr/bin/env node
'use strict';

// Minimal stdio MCP adapter around pinned Playwright. Every interaction returns
// actual images and appends frames/action receipts owned by this browser process.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const readline = require('node:readline');
const root = process.env.UX_GAN_RUNTIME;
if (!root) throw new Error('UX_GAN_RUNTIME is required');
const { chromium } = require(path.join(root, 'node_modules', 'playwright'));
const out = path.resolve(process.env.UX_GAN_SCREENSHOTS || '.');
const target = new URL(process.env.UX_GAN_TARGET || 'http://localhost');
const smoke = process.argv.includes('--smoke');
let browser, context, page, index = 0;
const tools = [
  ['ux_navigate', 'Open a URL and return its actual screenshot. Do this before reading UI source.', {url:{type:'string'}}],
  ['ux_capture', 'Look at the current rendered screen as an image; get a recorded screenshot.', {}],
  ['ux_resize', 'Set viewport (desktop 1440x900, tablet 768x1024, mobile 390x844) and capture.', {width:{type:'integer'},height:{type:'integer'}}],
  ['ux_click', 'Click a control chosen from the screenshot; returns before and after images. Use selector OR image coordinates.', {selector:{type:'string'},x:{type:'number'},y:{type:'number'},double:{type:'boolean'}}],
  ['ux_fill', 'Fill a visible input chosen from the image; preserves live browser state and captures before/after.', {selector:{type:'string'},value:{type:'string'}}],
  ['ux_select', 'Select an option on a visible native select; captures before/after.', {selector:{type:'string'},value:{type:'string'}}],
  ['ux_press', 'Press a key such as Tab, Enter or Escape; captures before/after.', {key:{type:'string'}}],
  ['ux_scroll', 'Scroll the page by a pixel amount and return before/after images.', {pixels:{type:'number'}}],
  ['ux_back', 'Use browser Back; captures before/after.', {}],
  ['ux_wait', 'Capture before, wait up to 10 seconds for processing, and capture after.', {seconds:{type:'number'}}],
  ['ux_offline', 'Simulate a network failure/recovery in this test browser; captures before/after.', {offline:{type:'boolean'}}],
  ['ux_dialog', 'Accept or cancel a pending browser confirm/alert; captures after the dialog.', {accept:{type:'boolean'},text:{type:'string'}}],
  ['ux_inspect', 'Read visible text/URL/console for locating an element AFTER looking at a screenshot. Not a substitute for visual review.', {}]
].map(([name,description,properties])=>({name,description,inputSchema:{type:'object',properties,additionalProperties:false}}));
let dialog, dialogWake, pendingAction, errors = [];
async function boot() {
  const opts = {headless:true};
  if (process.env.UX_GAN_BROWSER_EXECUTABLE) opts.executablePath=process.env.UX_GAN_BROWSER_EXECUTABLE;
  browser = await chromium.launch(opts);
  context = await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});
  page = await context.newPage();
  page.on('console',msg=>{if(['error','warning'].includes(msg.type())) errors.push({type:msg.type(),text:msg.text()});});
  page.on('pageerror',err=>errors.push({type:'pageerror',text:err.message}));
  page.on('dialog',d=>{dialog=d; if(dialogWake) dialogWake();});
  page.setDefaultTimeout(12000);
}
function receipt(value) {
  fs.appendFileSync(path.join(out,'browser-receipts.jsonl'),JSON.stringify(value)+'\n',{mode:0o600});
}
async function frame(label) {
  const id = `frame-${String(++index).padStart(4,'0')}-${crypto.randomUUID().slice(0,8)}`;
  const file = path.join(out,id+'.png');
  const buf = await page.screenshot({path:file,fullPage:false,timeout:12000});
  const url = page.url();
  const viewport = page.viewportSize();
  const meta = {id,path:file,label,url,viewport,source:new URL(url).origin===target.origin?'live':'official_reference',sha256:crypto.createHash('sha256').update(buf).digest('hex'),captured_at:new Date().toISOString()};
  receipt({kind:'frame',...meta});
  return {meta,image:{type:'image',data:buf.toString('base64'),mimeType:'image/png'}};
}
function externalGuard(action) {
  if (!['ux_navigate','ux_capture','ux_resize','ux_scroll','ux_wait','ux_inspect','ux_back'].includes(action) && new URL(page.url()).origin!==target.origin)
    throw new Error('External references are view-only; form/click/send actions are disabled there.');
}
async function call(name,a) {
  if (!page) await boot();
  if (!tools.some(t=>t.name===name)) throw new Error('Unknown tool '+name);
  externalGuard(name);
  if (dialog && name==='ux_inspect')
    return {content:[{type:'text',text:JSON.stringify({url:page.url(),pending_dialog:dialog.message()})}]};
  if (dialog && !['ux_dialog','ux_inspect'].includes(name))
    throw new Error('A browser dialog is pending; use ux_dialog to accept or cancel it first.');
  if (name==='ux_inspect') return {content:[{type:'text',text:JSON.stringify({url:page.url(),title:await page.title(),visible_text:await page.locator('body').innerText(),console:errors.slice(-30)})}]};
  const frames=[];
  if (!['ux_navigate','ux_capture','ux_dialog'].includes(name)) frames.push(await frame('before '+name));
  const dialogAppears = new Promise(resolve=>{dialogWake=resolve;});
  const operation = (async()=>{switch(name) {
    case 'ux_navigate': {
      const u=new URL(a.url); if(!['http:','https:'].includes(u.protocol)) throw new Error('Only http/https URLs');
      await page.goto(u.href,{waitUntil:'domcontentloaded',timeout:30000}); break;
    }
    case 'ux_resize':
      if (!Number.isInteger(a.width)||!Number.isInteger(a.height)||a.width<320||a.width>2560||a.height<400||a.height>2160) throw new Error('Invalid viewport');
      await page.setViewportSize({width:a.width,height:a.height}); break;
    case 'ux_click':
      if(a.selector) { const l=page.locator(a.selector); if(a.double) await l.dblclick({noWaitAfter:true}); else await l.click({noWaitAfter:true}); }
      else if(Number.isFinite(a.x)&&Number.isFinite(a.y)) await page.mouse.click(a.x,a.y,{clickCount:a.double?2:1});
      else throw new Error('selector or x/y required');
      break;
    case 'ux_fill': await page.locator(a.selector).fill(a.value); break;
    case 'ux_select': await page.locator(a.selector).selectOption(a.value); break;
    case 'ux_press': await page.keyboard.press(a.key); break;
    case 'ux_scroll': await page.mouse.wheel(0,a.pixels); break;
    case 'ux_back': await page.goBack({waitUntil:'domcontentloaded'}); break;
    case 'ux_wait': await page.waitForTimeout(Math.max(0,Math.min(10,a.seconds||1))*1000); break;
    case 'ux_offline': await context.setOffline(Boolean(a.offline)); break;
    case 'ux_dialog':
      if(!dialog) throw new Error('No pending browser dialog');
      { const current=dialog; dialog=undefined;
        if(a.accept) await current.accept(a.text); else await current.dismiss();
        if(pendingAction) {await pendingAction; pendingAction=undefined;} }
      break;
  }})();
  try { await Promise.race([operation,dialogAppears]); }
  finally {dialogWake=undefined;}
  if(dialog) {
    pendingAction=operation.catch(e=>{errors.push({type:'dialog_action',text:e.message});});
    receipt({kind:'action',tool:name,args:a,before:frames.map(x=>x.meta.id),dialog:dialog.message(),captured_at:new Date().toISOString()});
    return {content:[{type:'text',text:JSON.stringify({pending_dialog:dialog.message(),before:frames.map(x=>x.meta)})},...frames.map(x=>x.image)]};
  }
  if(name!=='ux_wait') await page.waitForTimeout(200);
  frames.push(await frame(name==='ux_capture'?'current':'after '+name));
  const state={url:page.url(),title:await page.title(),frames:frames.map(x=>x.meta),console:errors.slice(-10)};
  receipt({kind:'action',tool:name,args:a,frames:state.frames.map(x=>x.id),url:state.url,captured_at:new Date().toISOString()});
  return {content:[{type:'text',text:JSON.stringify(state)},...frames.map(x=>x.image)]};
}
async function main() {
  if(smoke) {
    await boot(); await page.setContent('<title>UX browser check</title><p>Browser ready</p>');
    const bytes=await page.screenshot();
    process.stdout.write(JSON.stringify({ready:true,png_bytes:bytes.length,version:require(path.join(root,'node_modules/playwright/package.json')).version})+'\n');
    await browser.close(); return;
  }
  fs.mkdirSync(out,{recursive:true});
  const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
  let queue=Promise.resolve();
  rl.on('line',line=>{queue=queue.then(async()=>{
    let req;
    try {
      req=JSON.parse(line); if(req.id===undefined) return;
      let result;
      switch(req.method) {
        case 'initialize': result={protocolVersion:req.params?.protocolVersion||'2024-11-05',capabilities:{tools:{}},serverInfo:{name:'ux-gan-visual-browser',version:'1.0.0'}}; break;
        case 'ping': result={}; break;
        case 'tools/list': result={tools}; break;
        case 'tools/call':
          try {result=await call(req.params.name,req.params.arguments||{});}
          catch(e) {result={isError:true,content:[{type:'text',text:e.message}]};}
          break;
        default: process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:req.id,error:{code:-32601,message:'Method not found'}})+'\n'); return;
      }
      process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:req.id,result})+'\n');
    }catch(e){process.stderr.write(e.message+'\n');}
  });});
  rl.on('close',()=>{queue.finally(async()=>{if(browser) await browser.close();});});
  for(const sig of ['SIGINT','SIGTERM']) process.on(sig,async()=>{if(browser) await browser.close(); process.exit(0);});
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exit(1);});
