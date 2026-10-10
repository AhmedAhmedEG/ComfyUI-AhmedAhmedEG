"""Build static documentation: index, getting started and one page per public node."""
from __future__ import annotations
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'

def esc(value):
    if isinstance(value, bool): value = str(value).lower()
    return html.escape(str(value), quote=True)

def slug(value):
    return re.sub(r'(?<!^)(?=[A-Z][a-z]|[A-Z]$)', '-', value.removeprefix('MiniMaxH3')).lower()

def items(values, ordered=False):
    tag = 'ol' if ordered else 'ul'
    return f'<{tag}>'+''.join(f'<li>{esc(value)}</li>' for value in values)+f'</{tag}>'

def section(title, content, anchor=None):
    anchor = anchor or re.sub('[^a-z0-9]+', '-', title.lower()).strip('-')
    return f'<h2 id="{anchor}">{esc(title)}</h2>{content}'

def build():
    data = json.loads((DOCS / 'guide_content.json').read_text(encoding='utf-8'))
    manuals = DOCS / 'manuals'
    def technical_manual(path):
        return path.read_text(encoding='utf-8').replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    schema = json.loads(subprocess.check_output([sys.executable, "-X", "utf8", str(ROOT/'tools/documentation_schema.py')], cwd=ROOT).decode('utf-8'))
    assert set(data['nodes']) == set(schema), 'Every public node needs exactly one documentation page'
    template = (DOCS / 'documentation_template.html').read_text(encoding='utf-8')
    groups = list(dict.fromkeys(s['category'] for s in schema.values()))
    generated = {}
    links = {key: 'nodes/'+slug(key)+'.html' for key in schema}
    assert len(set(links.values())) == len(schema)

    def link(key, prefix=''):
        return f'<a href="{prefix}{links[key]}">{esc(schema[key]["name"])}</a>'

    def nav(current, prefix):
        output = ''
        for target, title in [('index.html','Documentation index'),('getting-started.html','Getting started'),('architecture.html','Architecture and data')]:
            active = ' aria-current="page"' if current == target else ''
            output += f'<a href="{prefix}{target}"{active}>{title}</a>'
        for group in groups:
            output += '<section class="nav-group"><h3>'+esc(group)+'</h3>'
            for key, spec in schema.items():
                if spec['category'] != group: continue
                active = ' aria-current="page"' if current == links[key] else ''
                searchable = (spec['name']+' '+key+' '+data['nodes'][key]['summary']).lower()
                output += f'<a href="{prefix}{links[key]}" data-search="{esc(searchable)}"{active}>'+esc(spec['name'].removeprefix('MiniMax H3 '))+'</a>'
            output += '</section>'
        return output

    def page(path, title, description, body):
        prefix = '../' if path.startswith('nodes/') else ''
        headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
        toc = ''.join(f'<a href="#{anchor}">{label}</a>' for anchor, label in headings)
        result = template
        for marker, value in {'__TITLE__':esc(title),'__DESCRIPTION__':esc(description),'__PREFIX__':prefix,
                              '__VERSION__':esc(data['version']),'__NAV__':nav(path,prefix),'__MAIN__':body,'__TOC__':toc}.items():
            result = result.replace(marker,value)
        assert not re.search(r'__[A-Z_]+__',result), 'Unresolved template marker'
        generated[path] = result

    overview = '<div class="eyebrow">Node pack reference</div><h1>ComfyUI-AhmedAhmedEG</h1><p class="lead">MiniMax H3 generation, shot continuity, references, refinement and export. Start with one working shot, then look up the node you need.</p>'
    overview += '<div class="actions"><a class="button primary" href="getting-started.html">Getting started →</a><a class="button" href="architecture.html">Architecture and data</a><a class="button" href="nodes/master-node.html">Generation and continuity explained</a></div>'
    overview += '<div class="callout">The basic workflow uses four nodes from this pack: <b>Master Node</b>, <b>Director Settings</b>, <b>Reference Pack</b> and <b>Smart Preview</b>. Model loaders and ordinary video saving use stock ComfyUI nodes.</div>'
    overview += section('Documentation index','<p>Every node has its own page with behavior, wiring, a usage example, inputs, settings, outputs and limitations.</p>')
    for group in groups:
        content='<div class="node-grid">'
        for key,spec in schema.items():
            if spec['category']==group:
                content+=f'<a class="node-card" href="{links[key]}"><b>{esc(spec["name"])}</b><p>{esc(data["nodes"][key]["summary"])}</p></a>'
        overview += section(group,content+'</div>')
    page('index.html','Index','Getting started and documentation for all 23 public nodes.',overview)

    workflow = json.loads((ROOT/'workflows/MiniMax H3 Start Here.json').read_text(encoding='utf-8'))
    model_rows = []
    for node in workflow['nodes']:
        if node['type'] == 'UNETLoader':
            value=node['widgets_values_named']['unet_name']; kind='FL2VA model' if 'fl2va' in value else 'REF2VA model'; connection='fl2va_model' if 'fl2va' in value else 'ref2va_model'
        elif node['type']=='CLIPLoader':
            kind='Text encoder'; value=node['widgets_values_named']['clip_name']; connection='clip (type minimax)'
        elif node['type']=='VAELoader':
            value=node['widgets_values_named']['vae_name']; kind='Video VAE' if 'video' in value else 'Audio VAE'; connection='video_vae' if 'video' in value else 'audio_vae'
        else: continue
        model_rows.append(f'<tr><td>{kind}</td><td><code>{esc(value)}</code></td><td><code>{esc(connection)}</code></td></tr>')
    start='''<div class="eyebrow">Start here</div><h1>Getting started</h1><p class="lead">Generate one short video, review the take, then add the next shot. The starter already has the necessary connections and connects the Master to a separate Smart Preview node.</p><div class="actions"><a class="button primary" href="../workflows/MiniMax%20H3%20Start%20Here.json" download="MiniMax H3 Start Here.json">Download starter workflow</a></div>'''
    start+=section('Before you touch a setting','''<p><b>ComfyUI is a visual recipe.</b> Each box is a <b>node</b>: a small tool that loads a file, supplies settings, generates media or saves a result. The whole collection of boxes and connections is a <b>workflow</b>.</p><p>A node takes information through its <b>input sockets</b> on the left and passes results through its <b>output sockets</b> on the right. The curved lines are cables. To connect nodes, drag from an output dot to the matching input dot. Different data types need matching sockets: a MODEL connection carries an AI model, not a picture.</p><p>The starter already has the cables connected. You do not need to rebuild it. <b>Your first job is to select the installed files, write one prompt and click Run.</b> Run follows the connections automatically; you do not run each box separately.</p>''')
    start+=section('Read the actual starter workflow','''<a href="starter-workflow.png"><img class="editor-shot" src="starter-workflow.png" alt="Actual MiniMax H3 starter workflow rendered in ComfyUI, including both diffusion loaders, text and VAE loaders, settings, Master and separate Smart Preview"></a><p class="caption">Actual starter JSON opened in the installed ComfyUI frontend. Click the image to open it at full size. This shows the graph, not an AI-generated illustration.</p><div class="table-wrap"><table><thead><tr><th>Box you see</th><th>What it does</th><th>What you do first</th></tr></thead><tbody><tr><td>FL2VA · Load Diffusion Model</td><td>The video-making AI used for text and opening/closing-picture shots.</td><td>Select the installed FL2VA file.</td></tr><tr><td>REF2VA · Load Diffusion Model</td><td>The video-making AI for reference-guided and video-editing shots.</td><td>Select the installed REF2VA file. It can stay connected during text-only generation.</td></tr><tr><td>Text encoder · Load CLIP</td><td>Converts your written prompt into numbers the video AI can understand.</td><td>Select the MiniMax text encoder file and set its <code>type</code> dropdown to <code>minimax</code>.</td></tr><tr><td>Video · Load VAE</td><td>Loads the decoder that converts compressed video data into visible frames.</td><td>Select the video VAE file.</td></tr><tr><td>Audio · Load VAE</td><td>Loads the decoder that converts compressed sound data into audible sound.</td><td>Select the audio VAE file.</td></tr><tr><td>Director Settings</td><td>Supplies canvas size and sampling settings.</td><td>Keep the starter values.</td></tr><tr><td>Master Node</td><td>Shot editor and generation controller.</td><td>Write the prompt and assign pool references.</td></tr><tr><td>Reference Pack</td><td>The single source of reference media.</td><td>Connect your media loaders and enter optional names.</td></tr><tr><td>H3 SLA Attention ×2</td><td>Patches each model family’s attention.</td><td>Keep the supplied settings initially.</td></tr><tr><td>REF2VA Turbo LoRA + model/steps switches</td><td>Switches between base and LoRA-patched REF2VA.</td><td>One toggle selects both model and steps.</td></tr><tr><td>Smart Preview</td><td>Separate player connected to Master project_state.</td><td>Keep Latest clip selected.</td></tr></tbody></table></div><p><b>Director Settings, Master, Reference Pack and Smart Preview are this pack’s starter nodes.</b> The other boxes are ordinary ComfyUI tools. The two VAEs and two diffusion loaders are intentional: each has a different job.</p>''')
    start+=section('1. Install and load the starter', '<ol><li>Install this repository in your ComfyUI <code>custom_nodes</code> folder, install its requirements with ComfyUI’s Python, and restart ComfyUI.</li><li>Use native MiniMax H3 support and install plaguekind-nodes for H3 SLA Attention. The stock Boolean/model switch and LoRA loader are already in your supplied reference workflow.</li><li>Download the starter above. The JSON is a workflow file containing the boxes and cables, not a model or a video. Drop it onto the ComfyUI canvas to load it. Find the custom nodes under <b>ComfyUI-AhmedAhmedEG → Start here</b>.</li></ol><p>If this pack is already installed, skip installation and load the starter. Use a separate workflow tab if you want to keep another workflow open. After an update, refresh the browser so it loads the current editor.</p>')
    start+=section('2. Select the models', '<p>Use the two stock <b>Load Diffusion Model</b> nodes, stock <b>Load CLIP</b> with type <code>minimax</code>, and two stock <b>Load VAE</b> nodes. The saved selections are:</p><div class="table-wrap"><table><thead><tr><th>Purpose</th><th>Starter selection</th><th>Master input</th></tr></thead><tbody>'+''.join(model_rows)+'</tbody></table></div><p>Choose equivalent installed files if your filenames differ. Both diffusion families stay connected; the Master lazily selects the one needed by each shot.</p>')
    start+='<div class="screenshot-grid"><figure><a href="starter-models.png"><img src="starter-models.png" alt="Real FL2VA, REF2VA and minimax text-encoder selections in ComfyUI"></a><figcaption>The two video models and text encoder. These are three different files.</figcaption></figure><figure><a href="starter-vaes.png"><img src="starter-vaes.png" alt="Real separate video and audio VAE loaders in ComfyUI"></a><figcaption>The two decoders: video produces pictures, audio produces sound. Keep both connected.</figcaption></figure></div><p>The dropdowns list files installed on the <b>ComfyUI server</b>. A file on your own computer will not appear in a remote server’s dropdown. If a required file is missing, install it on that server before running.</p>'
    start+=section('Attention and the fast LoRA switch','<p>Each diffusion family passes through its own H3 SLA Attention node, using the settings from your supplied R2V workflow. <b>Enable REF2VA Turbo LoRA</b> switches the REF2VA branch between its base model and the selected LoRA-patched model. It does not patch FL2VA. The single Boolean toggle also selects sampling steps: 25 for the base model, 8 for the supplied Turbo LoRA. Edit the two integer nodes if you need other values. The model and step selectors are collapsed to keep their connected, redundant switch widgets out of the way. Director Settings steps is connected to the step selector.</p>')
    start+=section('3. Generate Shot 1','''<ol><li>Keep the starter’s Director Settings: <b>960 × 544, 24 fps, 25 steps, CFG 1, euler/simple, seed 0</b>.</li><li>At the top of the Master choose <b>Generation mode → Next shot</b>, and in the selected clip’s Continuity section use <b>Independent (No Continuity)</b> for this first test.</li><li>In the Master, select <b>T2V (Text to Video)</b>, duration <b>2 seconds</b> and shot audio <b>Generate</b>.</li><li>Paste the prompt below and click ComfyUI’s <b>Run</b> button.</li></ol><pre><code>A small robot walks through a sunlit greenhouse.
The camera tracks beside it. Leaves sway gently.
Soft footsteps and birds outside.</code></pre><div class="callout success"><b>Expected result:</b> one short generated take with sound. H3 rounds generated lengths to its 5 + 17k grid; a 2-second request becomes 56 frames, approximately 2.33 seconds.</div><img class="editor-shot" src="master-editor.png" alt="Master shot editor with timeline, shot controls and prompt"><p class="caption">Edit the visible shot controls. Graph sockets are above this editor.</p>''')
    start+='<figure><a href="starter-settings.png"><img src="starter-settings.png" alt="Actual Director Settings with beginner starter values"></a><figcaption>Sampling Settings on the left; Generation mode and per-clip Continuity are in the Master. Click for full size.</figcaption></figure><p>Wait for the run to finish before judging the result. Generation time depends on the server and chosen files. Clicking Run again adds another job; it does not make the current job faster.</p>'
    start+=section('4. Review the new clip','<ol><li>In the separate <b>Smart Preview</b> node, choose <b>Latest clip</b>. This requests a separate file for only the newest completed shot.</li><li>Use <b>Full video</b> when you want to watch the completed sequence. Enable Autoplay or use Save preview as needed.</li><li>Validate a take you accept. Matching cached results can then be reused.</li></ol><p>Preview copies fit within 960 × 540. Final export uses the generated frames at their configured size. Preview scope does not change which shots are generated.</p>')
    start+=section('5. Add references or another shot','<ul><li><b>Opening image:</b> connect Load Image to Reference Pack, name the image, choose I2V in the Master and assign that pool image as the opening frame.</li><li><b>Subject/style/media references:</b> connect media through Reference Pack, choose REF2VA, assign existing pool media and insert its prompt token, such as <code>&lt;Picture 1&gt;</code>. Audio references also need visual references.</li><li><b>Next shot:</b> click + Add Shot. Keep Independent for a separate scene, or select a continuity method and video/audio context lengths in the selected clip’s Continuity section for a continuation.</li><li><b>Review:</b> watch Latest clip first, then Full video to inspect the join. Changing a chained predecessor can invalidate dependent takes.</li></ul><p>For advanced media trimming, source edits and saved-take continuation, see '+link('MiniMaxH3MasterNode')+' and '+link('MiniMaxH3Checkpoint')+'.</p>')
    start+=section('6. Save a preview or export the final video','<p><b>Save preview</b> in Smart Preview downloads the displayed preview file. Latest clip downloads only that clip. Full video downloads the preview of the completed sequence. These are preview-resolution copies.</p><p>For a final-resolution file, load <a href="../workflows/MiniMax%20H3%20Consolidated.json" download>MiniMax H3 Consolidated.json</a>. Its Create Video → Save Video connections package and save the Master’s images, audio and fps. The starter deliberately ends at Smart Preview: Master project_state connects to the separate player.</p>')
    start+=section('Common first-run problems','<ul><li><b>UNKNOWN node:</b> update/restart the pack, refresh ComfyUI and load the current starter. Older graphs can contain removed wrapper nodes.</li><li><b>Missing model/input:</b> check the family model, minimax CLIP, both VAEs and the assigned references.</li><li><b>Out of memory:</b> shorten the shot or lower resolution before adding optional quality stages. Large text encoders also use memory.</li><li><b>No preview:</b> generate a completed take first. Workflows do not contain saved cache tensors; those stay on the server.</li></ul>')
    start+=section('Words you will meet','''<div class="table-wrap"><table><thead><tr><th>Word</th><th>Meaning</th></tr></thead><tbody><tr><td>Prompt</td><td>Your written instructions: action, appearance, camera movement and sound.</td></tr><tr><td>Model / checkpoint file</td><td>A trained AI file on the ComfyUI server. Selecting it does not download it.</td></tr><tr><td>Shot / clip</td><td>One short piece of the sequence. The editor calls these timeline pieces “clips”.</td></tr><tr><td>Take</td><td>One generated version of a shot. A new attempt can produce another take.</td></tr><tr><td>Frames / IMAGE</td><td>Individual pictures in order. IMAGE can carry a batch of many pictures.</td></tr><tr><td>fps</td><td>Frames per second. H3 generation uses 24; 24 pictures make roughly one second.</td></tr><tr><td>Latent</td><td>Compressed working data used by the AI. A decoder turns it into pictures and sound.</td></tr><tr><td>VAE</td><td>The encoder/decoder that converts between visible or audible media and compressed data.</td></tr><tr><td>Seed</td><td>The starting random number. Keep it fixed when comparing settings.</td></tr><tr><td>Steps</td><td>How many sampling iterations generation takes. More steps usually take longer and do not guarantee a better result.</td></tr><tr><td>CFG</td><td>A sampling control for guidance from the prompt. Keep the H3 starter value of 1 initially.</td></tr><tr><td>Reference</td><td>A picture, video or sound you ask the AI to follow.</td></tr><tr><td>Continuity</td><td>Using the end of the previous shot to help the next shot continue it.</td></tr><tr><td>Cache / validated</td><td>Stored completed results / a shot marked approved for reuse. Changed inputs can still require regeneration.</td></tr><tr><td>T2V / I2V / FL2V</td><td>Text-to-video / image-to-video / first-and-last-frame-to-video. Choose T2V for a written description alone.</td></tr><tr><td>REF2VA / V2V / RV2V</td><td>Reference-guided video and audio / video editing / reference video editing. These need the REF2VA model.</td></tr><tr><td>Denoise</td><td>How much a refinement pass may alter an existing result. A higher setting can change its content more.</td></tr><tr><td>LoRA</td><td>A small additional model file that modifies a base model, often for a style or subject. It is optional.</td></tr><tr><td>RefMod</td><td>A reference model/bundle treated as a reference asset, rather than a LoRA patch.</td></tr><tr><td>Sampler / scheduler</td><td>The method and sequence of noise levels used during generation. Keep euler/simple to begin.</td></tr><tr><td>Upscale</td><td>Increase the picture dimensions. Enlarging does not guarantee newly correct details.</td></tr><tr><td>Config / pack</td><td>A bundle of instructions or assets passed through a socket; it is not finished media.</td></tr></tbody></table></div><p><b>You do not need all 23 custom nodes.</b> Start with the four pack nodes in the starter. Visit another node’s page when you need the specific job it performs; each page now begins with a plain-language explanation and a first-use example.</p>''')
    page('getting-started.html','Getting started','Load the starter, select models, generate, review and save your first H3 shot.',start)
    page('architecture.html','Architecture and data','Data types, execution stages, temporal math, caches, memory and project state.',technical_manual(manuals/'architecture.html'))

    def input_rows(key, fields):
        rows=[]
        node=data['nodes'][key]
        for field in fields:
            name=field['name']
            description=node['control_descriptions'].get(name) or field['description'] or data['control_descriptions'].get(name)
            assert description, (key,name)
            default=field['default']
            if field['connection']: default_text='Connection'
            elif default is None: default_text='Installed selection' if field['dynamic'] else '—'
            elif len(str(default))>100: default_text='Editor-managed JSON'
            elif default=='': default_text='Empty'
            else: default_text=esc(default)
            options=[]
            if field['choices']: options.append('Choices: '+', '.join(esc(v) for v in field['choices']))
            if field['dynamic']: options.append('Choices depend on installed models or ComfyUI.')
            if field['min'] is not None or field['max'] is not None: options.append(f'Range: {esc(field["min"])}–{esc(field["max"])}')
            if field['step'] is not None: options.append('Step: '+esc(field['step']))
            rows.append('<tr><td><code>'+esc(name)+'</code><span class="optional">'+('Required' if field['required'] else 'Optional')+'</span></td><td><code>'+esc(field['type'])+'</code><div class="range">'+default_text+'</div></td><td>'+esc(description)+''.join('<div class="choices">'+text+'</div>' for text in options)+'</td></tr>')
        return '<div class="table-wrap"><table><thead><tr><th>Input / control</th><th>Type · initial value</th><th>What it does</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

    for key,spec in schema.items():
        node=data['nodes'][key]
        assert len(node['output_descriptions'])==len(spec['outputs']), key
        body='<div class="eyebrow">'+esc(spec['category'])+'</div><h1>'+esc(spec['name'])+'</h1><p class="lead">'+esc(node['summary'])+'</p>'
        body+='<div class="metadata"><span class="tag">'+esc(spec['category'])+'</span><span class="tag">'+str(len(spec['outputs']))+' output'+('s' if len(spec['outputs'])!=1 else '')+'</span></div><p><b>Use it when:</b> '+esc(node['when'])+'</p>'
        beginner=node['beginner']
        body+=section('In plain language','<p>'+esc(beginner['meaning'])+'</p><div class="callout"><b>Your first use:</b> '+esc(beginner['first_use'])+'</div>')
        if key in ('MiniMaxH3MasterNode','MiniMaxH3DirectorSettings'):
            body+='<a href="../starter-workflow.png"><img class="editor-shot" src="../starter-workflow.png" alt="Actual connected starter workflow in ComfyUI"></a><p class="caption">This node in the starter workflow. '+('<a href="../getting-started.html#read-the-actual-starter-workflow">Read what every box does</a>')+'.</p>'
        body+=section('Connections','<pre><code>'+esc('\n'.join(node['wiring']))+'</code></pre>')
        manual_path = manuals / (key + '.html')
        assert manual_path.is_file(), f'Missing technical manual: {key}'
        body += technical_manual(manual_path)
        body+=section('Execution summary',items(node['behavior']))
        body+=section('How to use it',items(node['steps'],True))
        ports=[field for field in spec['inputs'] if field['connection']]
        controls=[field for field in spec['inputs'] if not field['connection'] and field['name'] not in ('timeline_data','builder_state')]
        if ports: body+=section('Input sockets',input_rows(key,ports))
        if controls: body+=section('Settings and controls','<p class="caption">Initial values come from the node’s declared UI schema. The starter can use different values. Required settings have widgets; they do not all require cables. Runtime model/sampler choices depend on your installation.</p>'+input_rows(key,controls))
        managed=[field for field in spec['inputs'] if field['name'] in ('timeline_data','builder_state')]
        if managed: body+='<details><summary>Advanced editor-state inputs</summary><div>'+input_rows(key,managed)+'</div></details>'
        output_rows=[]
        for field,description in zip(spec['outputs'],node['output_descriptions']):
            output_rows.append('<tr><td><code>'+esc(field['name'])+'</code></td><td><code>'+esc(field['type'])+'</code></td><td>'+esc(description)+'</td></tr>')
        body+=section('Outputs',('<div class="table-wrap"><table><thead><tr><th>Output label</th><th>Type</th><th>Contents</th></tr></thead><tbody>'+''.join(output_rows)+'</tbody></table></div>') if output_rows else '<p>This display node has no output sockets. It is the workflow’s preview endpoint.</p>')
        if node['extra']:
            extra=node['extra']
            if not extra.startswith('<h2'): extra=section('Additional usage',extra)
            body+=extra
        if node['notes']: body+=section('Limits and troubleshooting',items(node['notes']))
        if node['related']:
            assert set(node['related'])<=set(schema), key
            body+=section('Related nodes','<div class="related">'+''.join('<span class="button">'+link(other,'../')+'</span>' for other in node['related'])+'</div>')
        body+='<p class="source">Definition: <a href="../../'+spec['source']+'">'+esc(spec['source'])+'</a></p>'
        page(links[key],spec['name'],node['summary'],body)

    generated['MiniMax-H3-User-Guide.html']='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=index.html"><title>Documentation</title></head><body><p>The guide is now a documentation site. <a href="index.html">Open the documentation index</a>.</p></body></html>\n'
    manifest_path=DOCS/'generated_pages.json'
    previous=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    for relative in set(previous)-set(generated):
        path=(DOCS/relative).resolve()
        if DOCS.resolve() not in path.parents or path.suffix!='.html': raise ValueError('Invalid generated-page path')
        if path.exists(): path.unlink()
    for relative,value in generated.items():
        path=DOCS/relative; path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8',newline='\n')
    manifest_path.write_text(json.dumps(sorted(generated),indent=2)+'\n',encoding='utf-8')
    print(f'Built documentation index, Getting Started and {len(schema)} individual node pages.')
    return generated

if __name__ == '__main__': build()
