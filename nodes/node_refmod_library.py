"""One owner for installed RefMod selection, descriptions and strength."""
import hashlib,json,math

class MiniMaxH3RefModLibrary:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'library_data':('STRING',{'default':'[]','multiline':True,'tooltip':'Selected installed RefMods and their descriptions/strength. Edited in the library panel.'})}}
    RETURN_TYPES=('MMX_REFMOD_LIBRARY',)
    RETURN_NAMES=('refmods',)
    FUNCTION='build'
    CATEGORY='ComfyUI-AhmedAhmedEG/References and prompts'
    def build(self, library_data='[]'):
        rows=json.loads(library_data)
        if not isinstance(rows,list): raise ValueError('RefMod selections must be a list.')
        refs=[]
        for row in rows:
            if row.get('enabled',True) is False: continue
            name=str(row.get('name','')).strip();strength=float(row.get('strength',1))
            if not name or not math.isfinite(strength) or not 0<=strength<=4: raise ValueError('RefMod needs a name and strength from 0 to 4.')
            refs.append({'id':str(row.get('id') or 'library_'+hashlib.sha256(name.encode()).hexdigest()[:16]), 'type':'refmod',
                'name':str(row.get('description') or name),'description':str(row.get('description','')),
                'strength':strength,'data':name})
        if len({row['id'] for row in refs})!=len(refs): raise ValueError('Select each RefMod once.')
        return ({'refs':refs},)
