import json
import unittest
from core.timeline_input import merge_authored_timeline


class NodePlacement(unittest.TestCase):
    def test_external_timeline_keeps_metadata_and_master_execution_ownership(self):
        local={'project_id':'same','clips':[{'id':'one','validated':True,'seed':'99'}]}
        authored={'project_id':'same','clips':[{'id':'one','prompt':'new','duration':2}],
            'cast_cards':{'1':'Blue coat.'},'imported_prompt_history':[{'prompt':'old'}],
            'shared_ref_ids':['photo'],'references':[{'id':'photo','type':'image'}],
            'shared_prompt':'Shared','shared_prompt_policy':'append',
            'import_bindings':{'config':{'steps':3}},'audio_fade_ms':12}
        result=merge_authored_timeline(local,authored)
        for key in authored.keys()-{'clips'}:self.assertEqual(result[key],authored[key])
        self.assertFalse(result['clips'][0]['validated'])
        self.assertEqual(result['clips'][0]['seed'],'99')
        self.assertEqual(result['clips'][0]['prompt'],'new')
        result['cast_cards']['1']='Changed'
        self.assertEqual(authored['cast_cards']['1'],'Blue coat.')

    def test_different_imported_project_does_not_inherit_old_approvals(self):
        result=merge_authored_timeline({'project_id':'old','clips':[{'id':'one','validated':True,'seed':'99'}]},
            {'project_id':'imported','clips':[{'id':'one','validated':False,'seed':'42'}]})
        self.assertEqual(result['project_id'],'imported')
        self.assertFalse(result['clips'][0]['validated'])
        self.assertEqual(result['clips'][0]['seed'],'42')

    def test_group_builder_does_not_clear_unspecified_master_metadata(self):
        result=merge_authored_timeline({'cast_cards':{'1':'Keep'},'shared_ref_ids':['photo'],'clips':[]},
            {'clips':[{'id':'one'}]})
        self.assertEqual(result['cast_cards'],{'1':'Keep'})
        self.assertEqual(result['shared_ref_ids'],['photo'])

    def test_review_apply_appends_typed_timeline_without_moving_string_output(self):
        from core.forge import draft_prompts
        from nodes.node_forge import MiniMaxH3ApplyPromptDraft
        state={'clips':[{'id':'one','type':'T2VA','prompt':'before','duration':1}]}
        raw=json.dumps(state)
        node=MiniMaxH3ApplyPromptDraft()
        bypass=node.apply(raw,None,False)
        self.assertEqual(bypass[0],raw)
        self.assertEqual(bypass[1],state)
        draft=draft_prompts(state,'walk',backend='local',generator=lambda *a,**k:'{"shots":[{"prompt":"After","duration":1,"type":"T2VA"}]}')
        reviewed=node.apply(raw,draft,True)
        self.assertEqual(json.loads(reviewed[0]),reviewed[1])
        self.assertEqual(reviewed[1]['clips'][0]['prompt'],'After')
        self.assertEqual(node.RETURN_TYPES,('STRING','MMX_TIMELINE'))

    def test_menu_has_one_home_per_node_and_stable_metadata_socket(self):
        from tests.mock_torch import setup_mock_torch_if_needed
        setup_mock_torch_if_needed()
        from nodes import NODE_CLASS_MAPPINGS,NODE_DISPLAY_NAME_MAPPINGS,_MENU_GROUPS
        members=[name for names in _MENU_GROUPS.values() for name in names]
        self.assertEqual(len(members),len(set(members)))
        self.assertEqual(set(members),set(NODE_CLASS_MAPPINGS))
        self.assertEqual(len(NODE_CLASS_MAPPINGS),27)
        self.assertEqual(len(set(NODE_DISPLAY_NAME_MAPPINGS.values())),27)
        master=NODE_CLASS_MAPPINGS['MiniMaxH3MasterNode']
        self.assertEqual((master.RETURN_TYPES[2],master.RETURN_NAMES[2]),('VHS_VIDEOINFO','video_info'))
        self.assertIn('Output',NODE_CLASS_MAPPINGS['MiniMaxH3PixelUpscale'].CATEGORY)
        self.assertIn('Advanced graph tools',NODE_CLASS_MAPPINGS['MiniMaxH3ApplyPromptDraft'].CATEGORY)
