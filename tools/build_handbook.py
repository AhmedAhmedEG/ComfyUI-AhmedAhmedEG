"""Source-checked, illustrated guide: consistent chapters and offline interactions."""
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parent.parent
DOCS=ROOT/'docs'
def esc(v):return html.escape(str(v),quote=True)
def slug(v):return re.sub(r'(?<!^)(?=[A-Z][a-z]|[A-Z]$)','-',v.removeprefix('MiniMaxH3')).lower()
def section(title,body,anchor=None):
    anchor=anchor or re.sub('[^a-z0-9]+','-',title.lower()).strip('-')
    return f'<section class="chapter-section"><h2 id="{anchor}">{esc(title)}</h2>{body}</section>'
def listing(rows,ordered=False):
    tag='ol' if ordered else 'ul'
    return f'<{tag}>'+''.join('<li>'+esc(row)+'</li>' for row in rows)+f'</{tag}>'
GROUPS=[('Start here',['MasterNode','DirectorSettings','RefPack','SmartPreview']),('Improve a result',['DirectorSelfLift','DirectorRefine','DirectorFaceRefine','DirectorSemanticBridge','Cache']),('Write and organize',['PromptForge','LocalPromptModel','ApplyPromptDraft','ProjectImport','RefModLibrary']),('Export and finish',['ProjectVideo','VideoCombine','PixelUpscale','FrameInterpolation','OutputProcessing']),('Advanced graph tools',['DirectorGroupImageToVideo','DirectorGroupReferenceToVideo','DirectorGroupsCombine','TimelineBuilder','Checkpoint','TailFromLatent','AdvanceCheckpoint','ModelOverridePack'])]

def build():
    data=json.loads((DOCS/'guide_content.json').read_text(encoding='utf-8'))
    version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    assert data['version']==version, 'Update guide content for the current package version'
    schema=json.loads(subprocess.check_output([sys.executable,'-X','utf8',str(ROOT/'tools/documentation_schema.py')],cwd=ROOT).decode('utf-8'))
    choices=json.loads((DOCS/'choice_guidance.json').read_text(encoding='utf-8'))
    editor=json.loads((DOCS/'editor_controls.json').read_text(encoding='utf-8'))
    photos=json.loads((DOCS/'screenshots.json').read_text(encoding='utf-8'))
    template=(DOCS/'documentation_template.html').read_text(encoding='utf-8')
    assert set(schema)==set(data['nodes'])
    generated={};search=[];links={k:'nodes/'+slug(k)+'.html' for k in schema}
    def link(key,prefix=''):
        return '<a href="'+prefix+links['MiniMaxH3'+key]+'">'+esc(schema['MiniMaxH3'+key]['name'].removeprefix('MiniMax H3 '))+'</a>'
    def photo(key,prefix=''):
        p=photos[key];assert (DOCS/p['file']).is_file(),p['file']
        return '<figure class="screen"><button class="image-zoom" type="button" data-image="'+prefix+p['file']+'" aria-label="Enlarge: '+esc(p['alt'])+'"><img src="'+prefix+p['file']+'" alt="'+esc(p['alt'])+'" loading="lazy" width="'+str(p['width'])+'" height="'+str(p['height'])+'"><span>View full size ↗</span></button><figcaption>'+esc(p['caption'])+'</figcaption></figure>'
    def nav(current,prefix):
        out=''
        for path,title in [('index.html','Guide home'),('getting-started.html','Your first clip'),('workflows.html','Practical workflows'),('editor.html','Timeline & reference editor'),('architecture.html','How the pieces fit')]:
            out+=f'<a href="{prefix}{path}"'+(' aria-current="page"' if current==path else '')+'>'+title+'</a>'
        for title,keys in GROUPS:
            out+='<section class="nav-group"><h3>'+title+'</h3>'
            for short in keys:
                key='MiniMaxH3'+short
                out+=f'<a href="{prefix}{links[key]}" data-search="{esc(schema[key]["name"]+" "+key+" "+data["nodes"][key]["purpose"])}"'+(' aria-current="page"' if current==links[key] else '')+'>'+esc(schema[key]['name'].removeprefix('MiniMax H3 '))+'</a>'
            out+='</section>'
        return out
    def page(path,title,desc,body):
        prefix='../' if path.startswith('nodes/') else ''
        toc=''.join(f'<a href="#{a}">{b}</a>' for a,b in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>',body))
        result=template
        for marker,value in {'__TITLE__':esc(title),'__DESCRIPTION__':esc(desc),'__PREFIX__':prefix,'__VERSION__':data['version'],'__REVIEWED__':data['reviewed'],'__COUNT__':str(len(schema)),'__NAV__':nav(path,prefix),'__MAIN__':body,'__TOC__':toc}.items():result=result.replace(marker,value)
        assert not re.search(r'__[A-Z_]+__',result)
        generated[path]=result
        search.append({'url':path,'title':title,'description':desc,'text':html.unescape(re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',body)))})
    intro='<div class="eyebrow">A practical guide to your node pack</div><h1>H3 Director.<br><em>The user guide.</em></h1><p class="lead">From a first prompt to a continuous sequence. Learn which control owns each job, see the real interface, and make one deliberate change at a time.</p><div class="actions"><a class="button primary" href="getting-started.html">Make your first clip →</a><a class="button" href="workflows.html">Choose a workflow</a></div>'
    intro+='<div class="review-stamp">Release '+data['version']+' · Reviewed '+data['reviewed']+' · '+str(len(schema))+' nodes · '+str(sum(len(n['options']) for n in data['nodes'].values()))+' inputs & settings</div>'+photo('master-timeline')
    routes=[('getting-started.html','Generate one clip','Models, canvas, prompt, references and the first run.'),('workflows.html#continue-an-action','Continue an action','Choose a method and understand context and duration.'),('nodes/director-refine.html','Review, then refine','Extra processing after a finished first pass.'),('nodes/project-video.html','Export the sequence','Use all current results, even with a latest-only raw output.')]
    intro+=section('Start with the job','<div class="route-grid">'+''.join('<a class="route" href="'+url+'"><span>'+str(i+1).zfill(2)+'</span><h3>'+title+'</h3><p>'+desc+'</p></a>' for i,(url,title,desc) in enumerate(routes))+'</div>')
    concepts=[('Pool ≠ assignment','Reference Pack prepares available assets. Each clip chooses its own subset.'),('Input ≠ output size','Reference Pack resizes inputs. Director Settings chooses the generation canvas.'),('Selected ≠ approved','The yellow outline chooses an editor target. Approval asks Master to reuse a result.'),('Refine ≠ resume','Refinement starts another stage; it does not append missing steps of a completed schedule.')]
    intro+=section('Four useful distinctions','<div class="concept-grid">'+''.join('<article><h3>'+a+'</h3><p>'+b+'</p></article>' for a,b in concepts)+'</div>')
    intro+=section('Node reference','<p>Every chapter follows the same order: purpose, connections, first steps, options, examples, outputs and troubleshooting. Search a task or control name above, or browse by job.</p>')
    for title,keys in GROUPS:intro+=section(title,'<div class="node-grid">'+''.join('<a class="node-card" href="'+links['MiniMaxH3'+k]+'"><b>'+esc(schema['MiniMaxH3'+k]['name'].removeprefix('MiniMax H3 '))+'</b><p>'+esc(data['nodes']['MiniMaxH3'+k]['purpose'])+'</p></a>' for k in keys)+'</div>')
    page('index.html','H3 Director user guide','Illustrated workflows and current option-by-option reference.',intro)

    content=json.loads((DOCS/'walkthroughs.json').read_text(encoding='utf-8'))
    for filename,chapter in content.items():
        body='<div class="eyebrow">'+esc(chapter['eyebrow'])+'</div><h1>'+chapter['heading']+'</h1><p class="lead">'+esc(chapter['description'])+'</p>'
        if filename=='getting-started.html':body+='<div class="actions"><a class="button primary" href="../workflows/MiniMax%20H3%20Start%20Here.json" download="MiniMax H3 Start Here.json">Download starter workflow ↓</a></div>'
        for block in chapter['sections']:
            body+=section(block['title'],block['body'],block.get('id'))
            if block.get('photo'):body+=photo(block['photo'])
        page(filename,chapter['title'],chapter['description'],body)

    body='<div class="eyebrow">The controls inside the nodes</div><h1>Read the interface.</h1><p class="lead">What each visible control does, when to use it, and what it changes.</p>'
    image_for={'Master timeline':'master-timeline','Clip continuity, look and LoRAs':'clip-continuity','Project panel':'master-timeline','Reference Pack asset editor':'reference-video','Smart Preview player':'smart-preview'}
    for title,rows in editor.items():
        cards=''.join('<article class="option-card" data-option="'+esc(a)+'"><h3>'+esc(a)+'</h3><p>'+esc(b)+'</p><dl><dt>Use it when</dt><dd>'+esc(c)+'</dd><dt>What changes</dt><dd>'+esc(d)+'</dd></dl></article>' for a,b,c,d in rows)
        body+=section(title,photo(image_for.get(title,'workflow-overview'))+'<div class="options-grid">'+cards+'</div>')
    page('editor.html','Timeline & reference editor','Every timeline, reference editor and Smart Preview control explained.',body)

    node_photos={'MasterNode':['master-timeline','clip-continuity','clip-look','clip-loras'],'DirectorSettings':['director-settings'],'RefPack':['reference-image','reference-video'],'SmartPreview':['smart-preview'],'DirectorSelfLift':['selflift-node'],'DirectorRefine':['refine-node'],'ProjectVideo':['project-export']}
    meanings={'IMAGE':'Decoded pictures or a frame batch; send to a viewer, compatible postprocessor or encoder.','AUDIO':'Waveform plus sample rate; keep matched to the returned frames.','LATENT':'Compressed sampled data; needs compatible decoding/continuation tools.','VIDEO':'Native video object; send to a compatible saver/consumer.','MMX_CONTINUATION':'Completed continuation data; connect to Master.latent_checkpoint.','MMX_TIMELINE':'Typed authored clip sequence; connect to Master.timeline.','STRING':'Text or JSON; inspect the output label before choosing a consumer.','MODEL':'A model branch, not rendered media; connect to the matching model input.'}
    for key,spec in schema.items():
        n=data['nodes'][key];short=key.removeprefix('MiniMaxH3');name=spec['name'].removeprefix('MiniMax H3 ')
        assert set(n['options'])=={f['name'] for f in spec['inputs']},key
        body='<div class="eyebrow">Node reference · '+esc(spec['category'])+'</div><h1>'+esc(name)+'</h1><p class="lead">'+esc(n['purpose'])+'</p><p class="use-when"><b>Use it when:</b> '+esc(n['use'])+'</p>'
        body+=section('1. What it does','<p>'+esc(n['examples'][0]['expect'])+'</p>','in-plain-language')
        if short in node_photos:body+=photo(node_photos[short][0],'../')
        body+=section('2. Connect it','<div class="wiring"><button class="copy-wiring" type="button">Copy wiring</button><pre><code>'+esc('\n'.join(n['wiring']))+'</code></pre></div>','connections')
        body+=section('3. First use',listing(n['steps'],True),'how-to-use-it')
        if short in ['MasterNode','RefPack','SmartPreview']:body+='<div class="callout"><a href="../editor.html">Read the controls inside this editor →</a></div>'
        cards=''
        for f in spec['inputs']:
            fn=f['name'];info=n['options'][fn];assert all(info.get(x) for x in ('what','when','effect')),(key,fn)
            storage=fn in {'timeline_data','builder_state','asset_edits','library_data','shot_descriptions','continuation_clip_id'} or fn.endswith('_name')
            kind='socket' if f['connection'] else 'storage' if storage else 'setting'
            default=f['default'];label='Connection' if f['connection'] else 'Installed choices' if f['dynamic'] and default is None else 'Empty' if default=='' else 'Not set' if default is None else str(default).lower() if isinstance(default,bool) else str(default)
            if len(label)>80:label='Editor-managed data'
            cards+='<article class="option-card" id="option-'+fn+'" data-option="'+esc(fn)+'" data-kind="'+kind+'"><div class="option-heading"><h3><code>'+esc(fn)+'</code></h3><span class="tag">'+{'socket':'Input socket','storage':'Editor storage','setting':'Setting'}[kind]+'</span></div><p>'+esc(info['what'])+'</p><dl><dt>Use it when</dt><dd>'+esc(info['when'])+'</dd><dt>What changes</dt><dd>'+esc(info['effect'])+'</dd>'
            if info.get('caution'):cards+='<dt>Keep in mind</dt><dd>'+esc(info['caution'])+'</dd>'
            cards+='</dl><details class="contract"><summary>Choices, defaults & connection details</summary><p><b>Type:</b> <code>'+esc(f['type'])+'</code> · <b>Initial value:</b> '+esc(label)+' · '+('Required' if f['required'] else 'Optional')+'</p>'
            if f['choices']:
                explains=choices.get(key+'.'+fn,choices.get(fn,{}))
                cards+='<dl class="choice-list">'
                for choice in f['choices']:
                    explanation=explains.get(str(choice))
                    if explanation is None and fn=='canvas_aspect':explanation='Follow source aspect when available.' if choice=='auto' else 'Use this width-to-height ratio for the active Auto canvas policy.'
                    if explanation is None and fn=='quality':explanation='Provider quality preset: compare processing cost and output with this provider, not a different codec’s numeric quality scale.'
                    if explanation is None and fn=='audio_bitrate':explanation='Automatic audio bitrate selection.' if choice=='Auto' else 'Target compressed sound rate of '+str(choice)+'. Larger rates can increase file size; they cannot recover missing source detail.'
                    assert explanation,(key,fn,choice,'missing choice explanation')
                    cards+='<dt>'+esc(choice)+'</dt><dd>'+esc(explanation)+'</dd>'
                cards+='</dl>'
            if f['dynamic']:cards+='<p>Available choices depend on installed models, samplers or providers.</p>'
            if f['min'] is not None:cards+='<p><b>Range:</b> '+esc(f['min'])+' to '+esc(f['max'])+(' · step '+esc(f['step']) if f['step'] is not None else '')+'</p>'
            cards+='</details></article>'
            search.append({'url':links[key]+'#option-'+fn,'title':name+' · '+fn,'description':info['what'],'text':' '.join((info['when'],info['effect'],info.get('caution','')))})
        controls='<div class="option-tools"><label>Find a control<input class="option-search" type="search" placeholder="Search name or explanation…"></label><label>Show<select class="option-filter"><option value="all">All controls</option><option value="setting">Settings</option><option value="socket">Input sockets</option><option value="storage">Editor storage</option></select></label><span class="option-count" aria-live="polite">'+str(len(spec['inputs']))+' controls</span></div><p class="caption">Defaults describe a newly added node. Saved workflows can use different values. Required sockets need a connection; ordinary required settings have widgets. Editor-storage fields belong to the visible editor.</p><p class="option-empty" hidden>No matching controls. Clear the search or choose All controls.</p><div class="options-grid">'+cards+'</div>'
        body+=section('4. Every option explained',controls,'settings-and-controls')
        examples=''.join('<article class="example"><span class="eyebrow">Use case '+str(i+1).zfill(2)+'</span><h3>'+esc(e['goal'])+'</h3><dl><dt>Set it up</dt><dd>'+esc(e['setup'])+'</dd><dt>Expect</dt><dd>'+esc(e['expect'])+'</dd></dl></article>' for i,e in enumerate(n['examples']))
        body+=section('5. Practical examples',examples,'practical-examples')
        for p in node_photos.get(short,[])[1:]:body+=photo(p,'../')
        output='<div class="table-wrap"><table><thead><tr><th>Output</th><th>Type</th><th>How to use it</th></tr></thead><tbody>'
        for output_index,o in enumerate(spec['outputs']):
            meaning=n['output_descriptions'][output_index]
            if o['name']=='project_state':meaning='Current project identity and timeline; connect to Smart Preview or cached export.'
            if key=='MiniMaxH3MasterNode' and o['name']=='images':meaning='Raw decoded output chosen by decoded_output; this may contain only the latest clip.'
            output+='<tr><td><code>'+esc(o['name'])+'</code></td><td>'+esc(o['type'])+'</td><td>'+esc(meaning)+'</td></tr>'
        output+='</tbody></table></div>'
        if not spec['outputs']:output='<p>This output/display node has no output sockets; its connection schedules upstream work.</p>'
        body+=section('6. What comes out',output,'outputs')
        body+=section('7. Limits & troubleshooting',listing(n['notes']),'limits-and-troubleshooting')
        body+=section('8. Check your setup','<p>Confirm the model family, source media and setting scope before comparing output. A visible control is not proof that a missing provider or model actually ran.</p><p class="source">Source: <a href="../../'+spec['source']+'">'+esc(spec['source'])+'</a>. Reviewed against '+data['version']+' on '+data['reviewed']+'.</p>','execution-summary')
        page(links[key],name,n['purpose'],body)
    def redirect(target,title):return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url='+target+'"><title>'+esc(title)+'</title></head><body><p><a href="'+target+'">Open the current '+esc(title)+'</a></p></body></html>\n'
    generated['MiniMax-H3-User-Guide.html']=redirect('index.html','H3 Director guide')
    for k in schema:generated['manuals/'+k+'.html']=redirect('../'+links[k],schema[k]['name'])
    generated['manuals/architecture.html']=redirect('../architecture.html','architecture guide')
    for rel,body in generated.items():
        p=DOCS/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding='utf-8',newline='\n')
    (DOCS/'generated_pages.json').write_text(json.dumps(sorted(generated),indent=2)+'\n',encoding='utf-8')
    (DOCS/'assets/search-index.js').write_text('window.H3_GUIDE_INDEX='+json.dumps(search,ensure_ascii=False).replace('</','<\\/')+';\n',encoding='utf-8',newline='\n')
    print(f'Built {len(schema)} node chapters, editor reference, task walkthroughs, offline search and legacy redirects.')
    return generated
