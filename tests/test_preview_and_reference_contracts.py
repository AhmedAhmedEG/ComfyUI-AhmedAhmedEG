import json
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()
from nodes.node_smart_preview import MiniMaxH3SmartPreview
from nodes.node_ref_pack import MiniMaxH3RefPack
from nodes.node_settings import MiniMaxH3DirectorSettings


class PreviewReferenceContracts(unittest.TestCase):
    def test_preview_is_only_a_state_sink(self):
        state={'project_id':'demo','clips':[{'id':'one'}]}
        result=MiniMaxH3SmartPreview().preview(json.dumps(state))
        self.assertEqual(result['result'],())
        self.assertEqual(json.loads(result['ui']['mmx_project'][0]),state)
        with self.assertRaises(ValueError):MiniMaxH3SmartPreview().preview('{}')

    def test_reference_names_preserve_ids_and_empty_slots_are_absent(self):
        tensor=object()
        pack,=MiniMaxH3RefPack().pack(image_1=tensor,image_1_name=' Alice ',video_1_name='No connected video')
        self.assertEqual(len(pack['refs']),1)
        self.assertEqual(pack['refs'][0]['name'],'Alice')
        self.assertEqual(pack['refs'][0]['id'],'image_1')
        self.assertIs(pack['refs'][0]['data'],tensor)
        chained,=MiniMaxH3RefPack().pack(ref_pack_optional=pack,image_1=tensor,image_1_name='Bob')
        self.assertEqual([(r['id'],r['name']) for r in chained['refs']],[('image_1','Alice'),('p2_image_1','Bob')])

    def test_one_generation_control_maps_advanced_and_normal_paths(self):
        for mode,execution,run in [('Next shot','All-in-One Generation','clip_by_clip'),('All shots','All-in-One Generation','full_batch'),('Conditioning only','Conditioning Guide Output','clip_by_clip')]:
            config,=MiniMaxH3DirectorSettings().build_config(generation_mode=mode)
            self.assertEqual((config['execution_mode'],config['run_mode']),(execution,run))
        with self.assertRaises(ValueError):MiniMaxH3DirectorSettings().build_config(generation_mode='wrong')
