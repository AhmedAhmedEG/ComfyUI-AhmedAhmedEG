const search=document.getElementById('nav-search');
search.addEventListener('input',()=>{
 const query=search.value.trim().toLowerCase();let count=0;
 document.querySelectorAll('.nav-group').forEach(group=>{
  let shown=0;group.querySelectorAll('a').forEach(link=>{
   const match=!query||link.dataset.search.includes(query);link.hidden=!match;if(match){shown++;count++}
  });group.hidden=shown===0;
 });document.getElementById('search-empty').hidden=count>0;
});
const menu=document.getElementById('menu-toggle');
menu.addEventListener('click',()=>{const open=document.body.classList.toggle('sidebar-open');menu.setAttribute('aria-expanded',String(open));if(open)search.focus()});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('sidebar-open')){document.body.classList.remove('sidebar-open');menu.setAttribute('aria-expanded','false');menu.focus()}});
