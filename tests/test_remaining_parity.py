import base64,io,json,tempfile,unittest,uuid
from pathlib import Path
from PIL import Image
from core.cast_tools import boxes_of,crop_for,parse_people,read_cast
from core.forge import draft_prompts,prepare_imported_history,apply_draft
from core.project_conversion import convert_project
from core.project import write_portable,read_portable
from core.transfer import progress_callback

class RemainingParity(unittest.TestCase):
    def test_people_validation_and_detection_order(self):
        people=parse_people('{"people":[{"bbox_2d":[600,0,1000,1000],"label":"right"},{"box":[0,0,.3,1],"label":"left"}]}'.replace(',.3',',0.3'))
        self.assertEqual([p['label'] for p in people],['left','right']);self.assertEqual([p['n'] for p in people],[1,2])
        for rows in [[{'n':1,'box':[0,0,0,1]}],[{'n':True,'box':[0,0,1,1]}],[{'n':1,'box':[0,0,float('nan'),1]}],[{'n':1,'box':[0,0,1,1]}]*2]:
            with self.assertRaises(ValueError):boxes_of(rows)

    def test_overlapping_people_are_read_from_whole_frame(self):
        boxes=boxes_of([{'n':1,'box':[0,0,.8,1]},{'n':2,'box':[.2,0,1,1]}])
        self.assertIsNone(crop_for(boxes,1))
        state={'clips':[{'ref_ids':['photo']}],'available_refs':[{'id':'photo','type':'image','boxes':boxes}]}
        seen=[]
        text=read_cast(state,'1',lambda row:Image.new('RGB',(200,100)),lambda system,user,images:seen.append(json.loads(user)) or 'Blue coat.')
        self.assertEqual(text,'Blue coat.');self.assertFalse(seen[0]['pictures'][0]['cropped']);self.assertIsNotNone(seen[0]['pictures'][0]['person_box_in_full_frame'])

    def test_separate_person_crop_and_selected_assets_only(self):
        boxes=[{'n':1,'box':[0,0,.4,1]},{'n':2,'box':[.6,0,1,1]}]
        state={'clips':[{'ref_ids':['selected']}],'available_refs':[{'id':'selected','type':'image','boxes':boxes},{'id':'unused','type':'image','characters':[1]}]}
        loaded=[];dimensions=[]
        def load(row):loaded.append(row['id']);return Image.new('RGB',(200,100))
        def provider(system,user,images):
            dimensions.extend(Image.open(io.BytesIO(base64.b64decode(v))).size for v in images)
            return '<think>internal</think>Copper hair.'
        self.assertEqual(read_cast(state,'1',load,provider),'Copper hair.');self.assertEqual(loaded,['selected']);self.assertLess(dimensions[0][0],100)
        with self.assertRaises(ValueError):read_cast(state,'3',load,provider)

    def test_reviewed_cast_cards_drive_compiled_prompt_and_staleness(self):
        state={'clips':[{'id':'one','type':'REF2VA','duration':1,'ref_ids':['hero'],'prompt':'old'}],'available_refs':[{'id':'hero','type':'image','characters':[1]}],'cast_cards':{'1':'Copper hair and a blue coat.'}}
        draft=draft_prompts(state,'walk',backend='local',generator=lambda *a,**kw:'{"shots":[{"prompt":"Character 1 walks","type":"REF2VA","duration":1}]}')
        self.assertIn('Copper hair and a blue coat.',draft['shots'][0]['prompt'])
        state['cast_cards']['1']='Green coat.'
        with self.assertRaisesRegex(ValueError,'context changed'):apply_draft(state,draft)

    def test_workflow_recovers_cast_history_and_explicit_loader_identity(self):
        data={'nodes':[{'id':1,'type':'DaSiWaH3Director','widgets_values_named':{'mode':'REF2VA','width':320,'height':192,'timeline_data':json.dumps({'items':[{'id':'face','type':'image','value':'face.png','forge_label':'character-2','forge_keep':'glasses'}],'resolved_prompt':'Walk.'})},'properties':{'dasiwaH3ForgeHistory':[{'mode':'REF2VA','simple_prompt':'Archived <Picture 1>.','fields':{'summary':'walk'}}]}},{'id':2,'type':'UNETLoader','widgets_values':['h3.safetensors','default']}]}
        state,report=convert_project(data)
        self.assertEqual(state['references'][0]['characters'],[2]);self.assertIn('Keep: glasses',state['references'][0]['description'])
        self.assertEqual(report['bindings']['model_bindings']['workflow_model_2']['filename'],'h3.safetensors')
        draft=prepare_imported_history(state,0);self.assertTrue(draft['warnings']);self.assertFalse(state['clips'][0]['validated'])
        self.assertEqual(draft['shots'][0]['prompt'],'Archived <Picture 1>.')
        self.assertNotIn('context_key',state['imported_prompt_history'][0])

    def test_ambiguous_foreign_workflow_does_not_pick_a_director_silently(self):
        node={'type':'DaSiWaH3Director','widgets_values':[json.dumps({'items':[]})]}
        with self.assertRaisesRegex(ValueError,'exactly one'):convert_project({'nodes':[node,node]})

    def test_portable_transfer_progress_and_cast_data_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'face.png';Image.new('RGB',(32,32)).save(source)
            state={'clips':[{'id':'one','ref_ids':['face'],'type':'REF2VA'}],'references':[{'id':'face','type':'image','filename':'face.png','boxes':[{'n':1,'box':[0,0,1,1]}]}],'cast_cards':{'1':'Blue coat.'},'imported_prompt_history':[{'prompt':'old'}]}
            events=[];archive=Path(root)/'project.mmxproj'
            write_portable(state,root,archive,lambda *e:events.append(e));restored=read_portable(archive,root,progress=lambda *e:events.append(e))
            self.assertEqual(restored['cast_cards'],state['cast_cards']);self.assertEqual(restored['references'][0]['boxes'],state['references'][0]['boxes'])
            self.assertTrue(any(e[0]=='Packing media' and e[1]==e[2] for e in events));self.assertTrue(any(e[0]=='Extracting media' and e[1]==e[2] for e in events))

    def test_progress_events_have_stable_job_identity(self):
        class Server:
            def __init__(self):self.events=[]
            def send_sync(self,*event):self.events.append(event)
        server=Server();key=str(uuid.uuid4());report=progress_callback(server,key);report('Packing media',10,10)
        self.assertEqual(server.events[0][1]['job_id'],key);self.assertEqual(server.events[0][1]['done'],10)
        with self.assertRaises(ValueError):progress_callback(server,'not-a-uuid')

    def test_keyframe_writer_receives_cards_without_reference_mode_headers(self):
        state={'clips':[{'id':'one','type':'I2VA','duration':1,'ref_ids':['hero']}],'available_refs':[{'id':'hero','type':'image','characters':[1]}],'cast_cards':{'1':'Green coat.'}}
        messages=[]
        def generator(value,**kwargs):
            messages.extend(value)
            return '{"shots":[{"prompt":"The person steps forward.","type":"I2VA","duration":1}]}'
        draft=draft_prompts(state,'walk',backend='local',generator=generator)
        self.assertNotIn('subject_definitions',draft['shots'][0]['prompt']);self.assertIn('Green coat.',messages[0]['content']);self.assertIn('opening frame',messages[0]['content'])
        self.assertEqual(draft['reference_bindings'],[[]])
