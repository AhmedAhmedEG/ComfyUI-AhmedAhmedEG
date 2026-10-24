import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.preflight_cache import PreflightCache,model_graph_signature,UnsupportedGraph
from core.cache_manager import ProjectCacheManager
from tests.test_master_preview_repairs import master


class PreflightTests(unittest.TestCase):
    def setup_graph(self,case):
        path=Path(case.temp.name)/'model.safetensors';path.write_bytes(b'checkpoint')
        graph={'5':{'class_type':'MiniMaxH3MasterNode','inputs':{'fl2va_model':['2',0],'ref2va_model':['2',0]}},
            '2':{'class_type':'UNETLoader','inputs':{'unet_name':'model.safetensors','weight_dtype':'default'}}}
        folder=SimpleNamespace(get_full_path_or_raise=lambda category,name:str(path),get_user_directory=lambda:case.temp.name)
        return graph,folder,path

    def inputs(self,case,graph,state):
        return {'timeline_data':json.dumps(state),'config':{'project_id':'regression','run_mode':'full_batch'},
            'prompt':graph,'unique_id':'5','video_vae':case.vae,'audio_vae':case.audio_vae,'clip':case.clip}

    def test_lazy_status_and_execution_reuse_before_requesting_any_model(self):
        with master() as case:
            graph,folder,path=self.setup_graph(case)
            with patch.dict(sys.modules,{'folder_paths':folder}):
                state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1,'seed':7}],
                    model=None,fl2va_model=case.model,prompt=graph,unique_id='5')[-1])
                args=self.inputs(case,graph,state)
                check=PreflightCache(args,state)
                self.assertTrue(check.matches(0),'Saved input signature should match before model evaluation')
                self.assertEqual(case.node.check_lazy_status(**args),[])
                # The browser receives the just-saved generation identifier.
                # It describes the result, not a request to produce new footage.
                state['clips'][0]['saved_generation']='newly-completed-result'
                args['timeline_data']=json.dumps(state)
                self.assertTrue(PreflightCache(args,state).matches(0))
                self.assertEqual(case.node.check_lazy_status(**args),[])
                case.sampling_calls.clear();case.native_calls.clear()
                result=case.node.execute(**args)
                self.assertEqual(case.sampling_calls,[])
                self.assertEqual(case.native_calls,[],'Reuse should precede text/VAE conditioning too')
                self.assertEqual(json.loads(result[8])['generated'],0)
                state['clips'][0]['prompt']='changed'
                self.assertEqual(case.node.check_lazy_status(**self.inputs(case,graph,state)),['fl2va_model'])
                path.write_bytes(b'replaced checkpoint')
                self.assertFalse(PreflightCache(args,json.loads(args['timeline_data'])).matches(0))

    def test_missing_cache_and_dynamic_seed_request_model(self):
        with master() as case:
            graph,folder,_=self.setup_graph(case)
            with patch.dict(sys.modules,{'folder_paths':folder}):
                state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1,'seed':7}],model=None,fl2va_model=case.model,prompt=graph,unique_id='5')[-1])
                args=self.inputs(case,graph,state)
                manager=ProjectCacheManager('regression',case.temp.name)
                Path(manager.get_clip_frames_path('one')).unlink()
                self.assertEqual(case.node.check_lazy_status(**args),['fl2va_model'])
                state['clips'][0]['seed_mode']='randomize'
                self.assertIsNone(PreflightCache(self.inputs(case,graph,state),state).key(0))

    def test_all_weight_loaders_are_skipped_for_unchanged_result(self):
        with master() as case:
            graph,folder,path=self.setup_graph(case)
            graph['5']['inputs'].update(clip=['3',0],video_vae=['4',0],audio_vae=['6',0])
            graph.update({'3':{'class_type':'CLIPLoader','inputs':{'clip_name':'encoder','type':'minimax','device':'default'}},
                '4':{'class_type':'VAELoader','inputs':{'vae_name':'video'}},
                '6':{'class_type':'VAELoader','inputs':{'vae_name':'audio'}}})
            with patch.dict(sys.modules,{'folder_paths':folder}):
                state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1,'seed':7}],
                    model=None,fl2va_model=case.model,prompt=graph,unique_id='5')[-1])
                args=self.inputs(case,graph,state)
                args.update(clip=None,video_vae=None,audio_vae=None)
                self.assertTrue(PreflightCache(args,state).matches(0))
                self.assertEqual(case.node.check_lazy_status(**args),[])
                case.native_calls.clear();case.sampling_calls.clear()
                result=case.node.execute(**args)
                self.assertEqual(case.native_calls,[])
                self.assertEqual(case.sampling_calls,[])
                self.assertEqual(json.loads(result[8])['generated'],0)
                changed=json.loads(args['timeline_data']);changed['clips'][0]['prompt']='different'
                expected=['fl2va_model','video_vae','audio_vae','clip']
                self.assertEqual(case.node.check_lazy_status(**{**args,'timeline_data':json.dumps(changed)}),expected)
                graph['3']['inputs']['device']='cpu'
                self.assertEqual(case.node.check_lazy_status(**args),expected)
                graph['3']['class_type']='UnknownEncoderModifier'
                self.assertEqual(case.node.check_lazy_status(**args),expected)
                self.assertEqual(case.node.check_lazy_status(**args,generation_mode='Conditioning only'),expected[1:])
                for name in ('clip','video_vae','audio_vae'):
                    self.assertTrue(case.node.INPUT_TYPES()['required'][name][1]['lazy'])

    def test_model_graph_follows_selected_switch_and_rejects_unknown_modifiers(self):
        with master() as case:
            graph,folder,_=self.setup_graph(case)
            graph['switch']={'class_type':'ComfySwitchNode','inputs':{'switch':True,'on_true':['2',0],'on_false':['missing',0]}}
            with patch.dict(sys.modules,{'folder_paths':folder}):
                self.assertEqual(model_graph_signature(graph,['switch',0])['switch'],True)
                graph['switch']['class_type']='UnrecognizedModelPatcher'
                with self.assertRaises(UnsupportedGraph):model_graph_signature(graph,['switch',0])

    def test_result_labels_do_not_hide_a_real_continuity_dependency_change(self):
        with master() as case:
            graph,folder,_=self.setup_graph(case)
            with patch.dict(sys.modules,{'folder_paths':folder}):
                state=json.loads(case.execute([
                    {'id':'one','type':'T2V','duration':1,'seed':7},
                    {'id':'two','type':'T2V','duration':1,'seed':7,'continuity':True}],
                    model=None,fl2va_model=case.model,prompt=graph,unique_id='5')[-1])
                for item in state['clips']:item['saved_generation']='browser-result-label'
                state['clips'][0]['validated']=True
                args=self.inputs(case,graph,state)
                self.assertTrue(PreflightCache(args,state).matches(1))
                self.assertEqual(case.node.check_lazy_status(**args,generation_mode='Next clip'),[])
                manager=ProjectCacheManager('regression',case.temp.name)
                manager.update_clip_metadata('one',{'generation':'actually-replaced-upstream-result'})
                self.assertFalse(PreflightCache(args,state).matches(1))
                self.assertEqual(case.node.check_lazy_status(**args,generation_mode='Next clip'),['fl2va_model'])

    def test_overwritten_checkpoint_cannot_relabel_retained_weights(self):
        with master() as case:
            graph,folder,path=self.setup_graph(case)
            state={'project_id':'regression','clips':[{'id':'one','type':'T2V','duration':1,'seed':7}]}
            args=self.inputs(case,graph,state);args['fl2va_model']=case.model
            with patch.dict(sys.modules,{'folder_paths':folder}):
                self.assertIsNotNone(PreflightCache(args,state).key(0))
                path.write_bytes(b'different weights')
                self.assertIsNone(PreflightCache(args,state).key(0))

    def test_clip_adapter_content_participates_in_preflight_key(self):
        with master() as case:
            graph,folder,_=self.setup_graph(case)
            state={'project_id':'regression','clips':[{'id':'one','type':'T2V','seed':7,'loras':[{'name':'adapter','strength':.7}]}]}
            args=self.inputs(case,graph,state)
            with patch.dict(sys.modules,{'folder_paths':folder}),patch('core.loras.resolve_lora_files',return_value=[{'sha256':'one'}]):
                first=PreflightCache(args,state).key(0)
            with patch.dict(sys.modules,{'folder_paths':folder}),patch('core.loras.resolve_lora_files',return_value=[{'sha256':'two'}]):
                second=PreflightCache(args,state).key(0)
            self.assertIsNotNone(first);self.assertNotEqual(first,second)


if __name__=='__main__':unittest.main()
