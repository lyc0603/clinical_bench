"""Specification-bound character storage; never infer or fill clinical values."""
import inspect


def normalize_character_storage(frame, definitions):
    result = frame.copy()
    for name, definition in definitions.items():
        if name not in result or definition['Type'] != 'Character':
            continue
        column = result[name]
        if not column.dropna().map(lambda value: isinstance(value, str)).all():
            raise ValueError(name + ': nonmissing non-character value cannot be normalized')
        # SAS character missing is blank. Object dtype and explicit blanks also
        # survive JSON round trips when the entire column is missing.
        result[name] = column.astype(object).where(column.notna(), '')
    return result


CHARACTER_STORAGE_CODE = inspect.getsource(normalize_character_storage)
