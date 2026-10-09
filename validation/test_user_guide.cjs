const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('../.validation/ui/node_modules/jsdom');
const root=path.join(__dirname,'..');
async function test(){
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
  const html=fs.readFileSync(path.join(root,'docs/MiniMax-H3-User-Guide.html'),'utf8');
  const dom=new JSDOM(html,{url:'https://guide.test/',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
    w.HTMLElement.prototype.scrollIntoView=()=>{};
    w.requestAnimationFrame=cb=>w.setTimeout(cb,0);
    const interval=w.setInterval.bind(w);w.setInterval=cb=>interval(cb,2);
  }});
  const w=dom.window,d=w.document,$=id=>d.getElementById(id);
  const phase=async id=>{w.location.hash=id;w.dispatchEvent(new w.HashChangeEvent('hashchange'));await new Promise(resolve=>setTimeout(resolve,20));};
  assert.equal(errors.length,0,errors.map(e=>e.message).join('\n'));
  assert.equal(d.querySelectorAll('.step').length,6);
  assert.equal(d.querySelectorAll('.feature').length,37);
  assert.equal(d.querySelectorAll('#node-list a').length,22);
  assert.equal(d.querySelectorAll('.slide,#next,#previous').length,0);
  await phase('shot');assert.match($('lab-title').textContent,/Make a shot/);
  $('demo-duration').value=2;$('demo-duration').dispatchEvent(new w.Event('input'));assert.match($('demo-timing').textContent,/56 frames/);
  $('demo-prompt').value='A dog <runs> & jumps';$('demo-prompt').dispatchEvent(new w.Event('input'));
  $('simulate').click();assert.ok($('simulate').disabled);
  const completionDeadline=Date.now()+2000;
  while($('simulate').disabled && Date.now()<completionDeadline) {
    await new Promise(resolve=>setTimeout(resolve,10));
  }
  assert.equal($('preview').hidden,false);assert.equal($('simulate').disabled,false);
  await phase('refs');d.querySelector('[data-mode="I2VA"]').click();$('toggle-ref').click();assert.match($('lab-panel').textContent,/Opening frame bound/);
  await phase('shot');assert.equal($('demo-prompt').value,'A dog <runs> & jumps');assert.equal($('demo-mode').value,'I2VA');assert.equal($('demo-duration').value,'2');
  await phase('story');$('toggle-chain').click();d.querySelector('[data-shot="1"]').click();assert.match($('lab-panel').textContent,/Shot 1 tail → Shot 2 prefix/);
  d.querySelector('[data-shot="0"]').click();assert.match($('lab-panel').textContent,/establishes the starting take/);
  await phase('enhance');d.querySelector('[data-enhancement="pixel"]').click();assert.match($('lab-panel').textContent,/Master images → Pixel/);
  await phase('save');assert.match($('lab-panel').textContent,/my_story.mp4/);
  $('search').value='LoRA';$('search').dispatchEvent(new w.Event('input'));assert.ok([...d.querySelectorAll('.feature')].some(e=>!e.hidden));assert.ok([...d.querySelectorAll('.feature')].some(e=>e.hidden));
  $('search').value='zzzznotfound';$('search').dispatchEvent(new w.Event('input'));assert.equal($('empty').hidden,false);
  d.querySelector('[data-feature="face"]').click();assert.equal($('feature-face').open,true);assert.equal($('feature-face').hidden,false);assert.equal($('search').value,'');
  $('motion').click();assert.ok(d.body.classList.contains('motion-paused'));
  const workflow=JSON.parse($('workflow-data').textContent);assert.deepEqual(workflow,JSON.parse(fs.readFileSync(path.join(root,'workflows/MiniMax H3 Start Here.json'),'utf8')));
  let downloaded=false;w.URL.createObjectURL=()=>{downloaded=true;return 'blob:test'};w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=()=>{};
  d.querySelector('[data-action="download-workflow"]').click();assert.ok(downloaded);
  $('feature-refine').hidden=true;w.dispatchEvent(new w.Event('beforeprint'));assert.ok([...d.querySelectorAll('details')].every(e=>e.open&&!e.hidden));w.dispatchEvent(new w.Event('afterprint'));assert.equal($('feature-refine').hidden,true);
  assert.equal(d.querySelectorAll('script[src],link[rel=stylesheet],img[src]').length,0);
  assert.equal(errors.length,0,errors.map(e=>e.message).join('\n'));
  dom.window.close();process.stdout.write('Animated guide passed: six stages, 37 features, 22 nodes, demo state/timing, reference binding, continuity, enhancement routing, search, download and print.\n');
}
test().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
