const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const{JSDOM,VirtualConsole}=require('../.validation/ui/node_modules/jsdom');
const root=path.join(__dirname,'..'),docs=path.join(root,'docs');
const data=JSON.parse(fs.readFileSync(path.join(docs,'guide_content.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(docs,'generated_pages.json'),'utf8'));
const photos=JSON.parse(fs.readFileSync(path.join(docs,'screenshots.json'),'utf8'));
const python=process.env.H3_GUIDE_PYTHON||(fs.existsSync(path.join(root,'.validation/Scripts/python.exe'))?path.join(root,'.validation/Scripts/python.exe'):'python');
const schema=JSON.parse(execFileSync(python,['-X','utf8','tools/documentation_schema.py'],{cwd:root,encoding:'utf8'}));
const nodes=manifest.filter(p=>p.startsWith('nodes/'));
assert.equal(nodes.length,Object.keys(schema).length);assert.equal(nodes.length,27);
const screenshots=Object.values(photos).filter(p=>p.kind==='screenshot');assert(screenshots.length>=9,'At least nine current screenshots');assert.equal(new Set(screenshots.map(p=>p.file)).size,screenshots.length,'Screenshot files are distinct');
const errors=[],js=fs.readFileSync(path.join(docs,'assets/documentation.js'),'utf8'),index=fs.readFileSync(path.join(docs,'assets/search-index.js'),'utf8');
let totalOptions=0,filtersChecked=false;
for(const relative of manifest){
 const absolute=path.join(docs,relative),vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
 const dom=new JSDOM(fs.readFileSync(absolute,'utf8'),{url:'file:///'+absolute.replaceAll('\\','/'),runScripts:'outside-only',virtualConsole:vc});
 const w=dom.window,d=w.document;
 for(const el of d.querySelectorAll('a[href],link[href],script[src],img[src]')){
  const ref=el.getAttribute(el.hasAttribute('href')?'href':'src');assert(!/^javascript:/i.test(ref));
  if(el.tagName==='A'&&/^https:\/\//i.test(ref))continue;
  assert(!/^https?:/i.test(ref),'Assets must work offline: '+ref);if(ref.startsWith('data:'))continue;
  const[file,anchor]=ref.split('#'),target=file?path.resolve(path.dirname(absolute),decodeURIComponent(file)):absolute;
  assert(fs.existsSync(target),relative+' missing '+ref);
  if(anchor&&target.endsWith('.html')){const linked=target===absolute?dom:new JSDOM(fs.readFileSync(target,'utf8'));assert(linked.window.document.getElementById(anchor),relative+' missing anchor '+ref);if(linked!==dom)linked.window.close();}
 }
 if(relative.startsWith('manuals/')||relative==='MiniMax-H3-User-Guide.html'){
  assert(d.querySelector('meta[http-equiv=refresh]'));dom.window.close();continue;
 }
 assert(d.querySelector('h1'));assert(d.body.textContent.includes(data.version));assert(!d.body.textContent.includes('23 public nodes'));
 assert.equal(d.querySelectorAll('nav a[aria-current=page]').length,1,relative+' needs current navigation');
 const ids=[...d.querySelectorAll('[id]')].map(e=>e.id);assert.equal(ids.length,new Set(ids).size,relative+' duplicate IDs');
 if(relative.startsWith('nodes/')){
  const key=Object.keys(schema).find(k=>relative==='nodes/'+k.replace('MiniMaxH3','').replace(/(?<!^)(?=[A-Z][a-z]|[A-Z]$)/g,'-').toLowerCase()+'.html');
  assert(key,relative);
  for(const id of ['in-plain-language','connections','how-to-use-it','settings-and-controls','practical-examples','outputs','limits-and-troubleshooting','execution-summary'])assert(d.getElementById(id),relative+' needs '+id);
  const cards=[...d.querySelectorAll('[data-kind][data-option]')];assert.equal(cards.length,schema[key].inputs.length,relative+' source coverage');totalOptions+=cards.length;
  for(const input of schema[key].inputs){const card=d.getElementById('option-'+input.name);assert(card);assert.match(card.textContent,/Use it when/);assert.match(card.textContent,/What changes/);for(const choice of input.choices)assert(card.textContent.includes(String(choice)),key+' missing choice '+choice);}
  if(!filtersChecked&&key==='MiniMaxH3DirectorRefine'){
   w.eval(index);w.eval(js);const input=d.querySelector('.option-search'),filter=d.querySelector('.option-filter');
   input.value='confirm_first_pass';input.dispatchEvent(new w.Event('input'));assert.equal(cards.filter(c=>!c.hidden).length,1);
   input.value='zzzznooption';input.dispatchEvent(new w.Event('input'));assert(!d.querySelector('.option-empty').hidden);
   input.value='';input.dispatchEvent(new w.Event('input'));filter.value='socket';filter.dispatchEvent(new w.Event('change'));assert(cards.filter(c=>!c.hidden).every(c=>c.dataset.kind==='socket'));
   const button=d.querySelector('.image-zoom');button.click();assert(d.getElementById('image-dialog').hasAttribute('open'));assert(d.getElementById('image-full').getAttribute('src'));d.getElementById('image-close').click();assert(!d.getElementById('image-dialog').hasAttribute('open'));filtersChecked=true;
  }
 }
 if(relative==='index.html'){
  assert.equal(d.querySelectorAll('.node-card').length,27);w.eval(index);w.eval(js);
  const search=d.getElementById('nav-search');search.value='confirm_first_pass';search.dispatchEvent(new w.Event('input'));assert(d.querySelector('#search-results a[href*="#option-confirm_first_pass"]'),'Full-guide search reaches a setting');
  search.value='0.5 megapixels';search.dispatchEvent(new w.Event('input'));assert(d.querySelectorAll('#search-results a').length>0,'Editor/workflow contents searchable');
  search.value='zzzznotfound';search.dispatchEvent(new w.Event('input'));assert(!d.getElementById('search-empty').hidden);
  const menu=d.getElementById('menu-toggle');menu.click();assert.equal(menu.getAttribute('aria-expanded'),'true');d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape'}));assert.equal(menu.getAttribute('aria-expanded'),'false');
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'/'}));assert.equal(d.activeElement,search);
 }
 if(relative==='getting-started.html'){assert(d.querySelector('a[download]'));for(const text of ['FL2VA','REF2VA','56 frames','24 fps','0.92'])assert(d.body.textContent.includes(text));}
 dom.window.close();
}
assert.equal(totalOptions,269);assert(filtersChecked);assert.equal(errors.length,0,errors.map(e=>e.message).join('\n'));
console.log(`Guide passed: ${nodes.length} chapters, ${totalOptions} source inputs/settings, ${screenshots.length} real screenshots plus a wiring diagram, offline links/anchors, full-text search, option filters, lightbox, keyboard and legacy redirects.`);
