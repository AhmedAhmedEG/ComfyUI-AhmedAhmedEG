"""All public controls remain documented and callable; hidden state is explicit."""
import inspect
import json
from pathlib import Path
import re
import unittest
from tools.documentation_schema import collect


class DocumentedControls(unittest.TestCase):
    def test_public_controls_have_manuals_and_execution_contracts(self):
        schema = collect()
        from nodes import NODE_CLASS_MAPPINGS
        root = Path(__file__).resolve().parent.parent
        content = json.loads((root/'docs/guide_content.json').read_text(encoding='utf8'))
        for key, node in schema.items():
            manual = (root/'docs/manuals'/f'{key}.html').read_text(encoding='utf8')
            self.assertGreater(len(re.sub('<[^>]+>', '', manual).split()), 170, key)
            cls = NODE_CLASS_MAPPINGS[key]
            signature = inspect.signature(getattr(cls, cls.FUNCTION))
            accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values())
            for field in node['inputs']:
                self.assertTrue(field['name'] in signature.parameters or accepts_kwargs, (key,field['name']))
                self.assertTrue(content['nodes'][key]['control_descriptions'].get(field['name'])
                    or field['description'] or content['control_descriptions'].get(field['name']), (key,field['name']))
            self.assertEqual(len(cls.RETURN_TYPES),len(getattr(cls,'RETURN_NAMES',cls.RETURN_TYPES)),key)

    def test_generation_mode_is_an_ordinary_visible_combo(self):
        schema = collect()['MiniMaxH3DirectorSettings']
        mode = next(field for field in schema['inputs'] if field['name']=='generation_mode')
        self.assertEqual(mode['choices'],['Next shot','All shots','Conditioning only'])
        self.assertFalse(mode['connection'])
        source = (Path(__file__).resolve().parent.parent/'web/js/minimax_director.js').read_text(encoding='utf8')
        self.assertEqual(set(re.findall(r'hideWidget\((\w+)\)',source)),
            {'timelineWidget','builderWidget','promptWidget','durationWidget'})


if __name__ == '__main__': unittest.main()
