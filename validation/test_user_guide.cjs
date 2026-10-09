const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('../.validation/ui/node_modules/jsdom');
const root=path.join(__dirname,'..'),docs=path.join(root,'docs');
const data=JSON.parse(fs.readFileSync(path.join(docs,'guide_content.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(docs,'generated_pages.json'),'utf8'));
const nodes=manifest.filter(p=>p.startsWith('nodes/'));
assert.equal(nodes.length,22);assert.equal(Object.keys(data.nodes).length,22);
const errors=[];
for(const relative of manifest){
 const absolute=path.join(docs,relative),vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
 const dom=new JSDOM(fs.readFileSync(absolute,'utf8'),{url:'file:///'+absolute.replaceAll('\\','/'),runScripts:'outside-only',virtualConsole:vc});
 const d=dom.window.document;
 for(const el of d.querySelectorAll('a[href],link[href],script[src],img[src]')){
  const ref=el.getAttribute(el.hasAttribute('href')?'href':'src');
  assert(!/^(https?:|javascript:)/i.test(ref),'Documentation should work offline: '+ref);
  if(ref.startsWith('data:'))continue;
  const [file,anchor]=ref.split('#'),target=file?path.resolve(path.dirname(absolute),decodeURIComponent(file)):absolute;
  assert(fs.existsSync(target),relative+' → missing '+ref);
  if(anchor&&target.endsWith('.html')){
   const linked=target===absolute?dom:new JSDOM(fs.readFileSync(target,'utf8'));
   assert(linked.window.document.getElementById(anchor),relative+' → missing anchor '+ref);
   if(linked!==dom)linked.window.close();
  }
 }
 if(relative.startsWith('nodes/')){
  assert(d.querySelector('h1'));
  for(const id of ['in-plain-language','connections','how-it-works','how-to-use-it','outputs','limits-and-troubleshooting'])assert(d.getElementById(id),relative+' needs '+id);
  assert.equal(d.querySelectorAll('nav a[aria-current=page]').length,1);
  assert(d.querySelector('table tbody tr'));
 }
 if(relative==='index.html'){
  assert.equal(d.querySelectorAll('.node-card').length,22);
  dom.window.eval(fs.readFileSync(path.join(docs,'assets/documentation.js'),'utf8'));
  const search=d.getElementById('nav-search');search.value='FaceRefine';search.dispatchEvent(new dom.window.Event('input'));
  assert.equal([...d.querySelectorAll('.nav-group a')].filter(a=>!a.hidden).length,1);
  search.value='zzzznotfound';search.dispatchEvent(new dom.window.Event('input'));assert.equal(d.getElementById('search-empty').hidden,false);
  const menu=d.getElementById('menu-toggle');menu.click();assert.equal(menu.getAttribute('aria-expanded'),'true');
  d.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Escape'}));assert.equal(menu.getAttribute('aria-expanded'),'false');
 }
 if(relative==='getting-started.html'){
  assert(d.querySelector('a[download]'));assert.match(d.body.textContent,/FL2VA/);assert.match(d.body.textContent,/REF2VA/);
  assert.match(d.body.textContent,/Latest clip/);assert.match(d.body.textContent,/56 frames/);
  assert(d.getElementById('before-you-touch-a-setting'));
  assert(d.getElementById('words-you-will-meet'));
  for(const image of ['starter-workflow.png','starter-models.png','starter-vaes.png','starter-settings.png'])assert(d.querySelector(`img[src="${image}"]`));
 }
 dom.window.close();
}
assert.equal(errors.length,0,errors.map(e=>e.message).join('\n'));
console.log('Documentation passed: index, Getting Started, 22 node pages, local links/anchors/assets, search, menu and current workflow download.');
