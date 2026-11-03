"""Preserve character nulls and dtype, without changing clinical values."""
import inspect
from gxp_full.plan import NODE_WRAPPER as ORIGINAL_NODE_WRAPPER,EXPORT_WRAPPER as ORIGINAL_EXPORT_WRAPPER


def preserve_nullable_characters(frame,definitions):
    out=frame.copy()
    for name,definition in definitions.items():
        if name not in out or definition['Type']!='Character':continue
        column=out[name]
        if not all(isinstance(value,str) for value in column.dropna()):raise ValueError(name+': nonmissing non-character value')
        # Unlike object JSON columns, pandas nullable strings retain their
        # declared extension dtype and null semantics on the next read.
        if column.isna().all():out[name]=column.astype('string')
    return out


NORMALIZATION=inspect.getsource(preserve_nullable_characters)
INSERT=NORMALIZATION+'''
dataset=Path(program).stem.split('__',1)[0]
sheet=json.loads(Path('/inputs/specifications.json').read_text())['sheets'][dataset]
definitions={r['Variable']:r for r in (dict(zip(sheet[0],row)) for row in sheet[1:]) if r.get('Variable')}
result=preserve_nullable_characters(result,definitions)
'''
NODE_WRAPPER=ORIGINAL_NODE_WRAPPER.replace("Path(result_path).parent.mkdir(parents=True,exist_ok=True)",INSERT+"\nPath(result_path).parent.mkdir(parents=True,exist_ok=True)")
OLD_TEST='if not column.dropna().map(lambda value: isinstance(value, str)).all():'
assert ORIGINAL_EXPORT_WRAPPER.count(OLD_TEST)==1
EXPORT_WRAPPER=ORIGINAL_EXPORT_WRAPPER.replace(OLD_TEST,'if not all(isinstance(value, str) for value in column.dropna()):')
