"""Real HTTP vision-provider contract checks; the server is a deterministic fixture."""
import base64,io,json,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from PIL import Image
from core.cast_tools import image_b64,parse_people,read_cast
from core.forge import provider_text
from core.forge_jobs import DraftJob

class VisionHTTP(unittest.TestCase):
    def setUp(self):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));captured.append(body)
                user=body['messages'][-1]['content'][0]['text']
                text=json.dumps({'people':[{'box':[.1,.1,.6,.9],'label':'person'}]}) if user=='Find the people.' else 'Blue coat and copper hair.'
                output=('data: '+json.dumps({'choices':[{'delta':{'content':text}}]})+'\n\ndata: [DONE]\n\n').encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start();self.captured=captured
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.worker.join(2)
    def provider(self,system,user,images):
        return provider_text(system,user,backend='compatible',endpoint=f'http://127.0.0.1:{self.server.server_port}',model='fixture',images=images,job=DraftJob())
    def test_real_sse_find_people_and_image_message(self):
        people=parse_people(self.provider('Find people and return JSON.','Find the people.',[image_b64(Image.new('RGB',(100,100)))]))
        self.assertEqual(people[0]['n'],1);self.assertTrue(self.captured[0]['stream']);self.assertEqual(self.captured[0]['messages'][-1]['content'][1]['type'],'image_url')
    def test_real_sse_card_reader_passes_only_the_selected_person_crop(self):
        timeline={'clips':[{'ref_ids':['one']}],'available_refs':[{'id':'one','type':'image','characters':[1],'boxes':[{'n':1,'box':[0,0,.4,1]}]},{'id':'unused','type':'image','characters':[1]}]}
        text=read_cast(timeline,'1',lambda row:Image.new('RGB',(200,100)),self.provider)
        self.assertEqual(text,'Blue coat and copper hair.')
        pictures=self.captured[0]['messages'][-1]['content'][1:];self.assertEqual(len(pictures),1)
        raw=base64.b64decode(pictures[0]['image_url']['url'].split(',',1)[1]);self.assertLess(Image.open(io.BytesIO(raw)).width,100)

if __name__=='__main__':unittest.main()
