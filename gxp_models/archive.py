"""Lossless private evidence archives, verified before any optional cleanup."""
import hashlib
from pathlib import Path
import tarfile
from main_experiment.support import manifest,save,digest


def archive_evidence(source,root):
    expected=manifest(source);target=Path(root)/'run-evidence.tar.gz';temporary=target.with_suffix('.tmp')
    if target.exists() or temporary.exists():raise ValueError('Preserve previous archive')
    with tarfile.open(temporary,'w:gz',compresslevel=3) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_symlink():raise ValueError('No symlinks in evidence')
            if path.is_file():archive.add(path,arcname=str(path.relative_to(source)),recursive=False)
    observed={}
    with tarfile.open(temporary,'r:gz') as archive:
        for member in archive:
            if not member.isfile():raise ValueError('Unexpected archive member')
            h=hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            observed[member.name]=h.hexdigest()
    if observed!=expected or manifest(source)!=expected:raise ValueError('Evidence archive mismatch')
    temporary.rename(target);save(Path(root)/'evidence-manifest.private.json',expected)
    save(Path(root)/'archive-receipt.json',{'verified_lossless':True,'files':len(expected),'sha256':digest(target),'size_bytes':target.stat().st_size,'temporary_execution_retained':True})
