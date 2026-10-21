"""Host-only scoring; no scores or evaluator code enter the agent container."""
import json
import re
from pathlib import Path
import shutil
import tempfile

from main_experiment.support import command, digest, manifest, report_metrics, save
from .derivation import score
from .coverage import profile
from .rebuild import RebuildRuntime


def conformance_metrics(path, expected, actual, pins):
    """Report usability concerns observed validation, not planned completeness."""
    expected, actual = set(expected), set(actual)
    result = report_metrics(path, sorted(actual), pins)
    validated = set(result['datasets'])
    usable = (bool(validated) and validated <= actual and
              not result.get('missing_configuration_tokens') and
              not result.get('qualification_problems') and
              not result.get('installation_warning'))
    result.update(report_usable=usable, expected_datasets=sorted(expected),
                  actual_datasets=sorted(actual), validated_datasets=sorted(result['datasets']),
                  missing_datasets=sorted(expected-actual), extra_datasets=sorted(actual-expected),
                  produced_not_validated=sorted(actual-validated),
                  required_not_validated=sorted(expected-validated),
                  unexpected_report_datasets=sorted(validated-actual),
                  validation_coverage_complete=usable and validated == actual == expected)
    if usable:
        result['status'] = 'valid' if validated == actual == expected else 'valid_partial'
    else:
        result['status'] = 'invalid_validation'
        # Invalid reports retain diagnostic counts without presenting them as scores.
        for field in ('dataset_rule_pairs', 'finding_instances', 'distinct_rules'):
            result['observed_'+field] = result[field]
            result[field] = None
    return result


def semantic(left, right):
    """Conservative equality: row order, types, widths and labels all matter."""
    import pyreadstat
    from lxml import etree
    left, right = Path(left), Path(right)
    if {p.name for p in left.iterdir()} != {p.name for p in right.iterdir()}:
        return False
    for p in left.iterdir():
        q = right / p.name
        if p.suffix.lower() == '.xpt':
            a, am = pyreadstat.read_xport(str(p), disable_datetime_conversion=True)
            b, bm = pyreadstat.read_xport(str(q), disable_datetime_conversion=True)
            if not a.equals(b):
                return False
            for field in ('column_labels', 'original_variable_types', 'variable_storage_width', 'file_label', 'table_name'):
                if getattr(am, field, None) != getattr(bm, field, None):
                    return False
        elif p.name == 'define.xml':
            parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
            trees = [etree.parse(str(x), parser) for x in (p, q)]
            for tree in trees:
                # Sole frozen normalization: ODM creation timestamp.
                root = tree.getroot()
                if etree.QName(root).localname != 'ODM':
                    return False
                root.attrib.pop('CreationDateTime', None)
            if etree.tostring(trees[0], method='c14n') != etree.tostring(trees[1], method='c14n'):
                return False
        elif digest(p) != digest(q):
            return False
    return True


def meddra(c):
    p = c['p21']
    m = json.loads(Path(p['meddra_manifest']).read_text())
    if str(m['version']) != '8.0' or m['language'] != 'English':
        raise ValueError('MedDRA must be English 8.0')
    canonical = Path(p['cache']).resolve() / 'configs/data/MedDRA/8.0'
    directory = Path(p['meddra_directory']).resolve()
    if directory not in (canonical, canonical / 'en'):
        raise ValueError('Dictionary must be the pinned cache MedDRA/8.0 or its en directory')
    for name in ('pt', 'soc', 'llt', 'hlt', 'hlgt'):
        filename = name + '.asc'
        candidates = {directory / filename}
        candidates.update(x / filename for x in (canonical, canonical / 'en') if (x / filename).exists())
        if any(digest(x) != m['files'][filename]['sha256'] for x in candidates):
            raise ValueError('MedDRA dictionary hash mismatch: ' + filename)
    return m


def standard_configuration(c):
    """Verify the actual pinned P21 standard artifact, not unreported model text."""
    from lxml import etree
    path = Path(c['p21']['cache']) / 'configs/2508.1/ADaM-IG 1.3 (FDA).xml'
    root = etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True))
    versions = root.findall('.//{http://www.cdisc.org/ns/odm/v1.3}MetaDataVersion')
    ns = '{http://www.cdisc.org/ns/def/v2.0}'
    if not any(v.get(ns+'StandardName') == 'ADaM-IG' and v.get(ns+'StandardVersion') == '1.3'
               for v in versions):
        raise ValueError('P21 configuration does not declare ADaM-IG 1.3')
    return {'file': str(path), 'sha256': digest(path), 'standard': 'ADaM-IG',
            'version': '1.3', 'base_model_version': 'not independently reported by P21'}


def runtime(c):
    from .backend import capture
    cache = Path(c['p21']['cache'])
    engines = manifest(cache / 'lib/engines')
    engines.pop('app.data', None)
    from .egress import policy
    return {'standard_configuration': standard_configuration(c), 'egress_policy': policy(), 'image': capture(['docker', 'image', 'inspect', '--format', '{{.Id}}', c['image']]),
            'opencode': capture(['docker', 'run', '--rm', '--network', 'none', c['image'], 'opencode', '--version']),
            'java': digest(Path(c['p21']['java'])),
            'client': digest(cache / 'lib/p21-client-1.0.9.jar'),
            'configs': manifest(cache / 'configs'), 'engines': engines,
            'meddra': meddra(c)}


class P21ValidationError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Evaluator:
    def __init__(self, c, image):
        self.c = c
        self.rebuild_runtime = RebuildRuntime(c, image)

    def p21(self, workspace, directory):
        p = self.c['p21']
        if (directory / 'p21_adam.xlsx').exists() or (directory / 'p21-diagnostics.json').exists():
            raise ValueError('P21 evaluation requires a fresh output directory')
        with tempfile.TemporaryDirectory(prefix='p21-', dir=directory) as temp:
            cache = Path(temp) / 'cache'
            shutil.copytree(p['cache'], cache)
            before = manifest(cache)
            support = Path(temp) / 'support'
            support.mkdir()
            for dom in p['support_domains']:
                shutil.copy2(Path(self.c['inputs']) / 'Input' / (dom.lower()+'.xpt'), support)
            data = workspace / 'output/adam/datasets'
            report = directory / 'p21_adam.xlsx'
            argv = [p['java'], '-jar', str(cache / 'lib/p21-client-1.0.9.jar'),
                    '--engine.version=FDA 2508.1', '--engine.folder='+str(cache / 'lib/engines'),
                    '--standard=adam', '--standard.version=1.3', '--config='+str(cache / 'configs'),
                    '--source.define='+str(data / 'define.xml'), '--source.adam='+str(data),
                    '--source.sdtm='+str(support), '--cdisc.ct.adam.version='+p['ct'],
                    '--cdisc.ct.sdtm.version='+p['ct'], '--meddra.version=8.0', '--report='+str(report)]
            execution = None
            result = None
            failure = None
            evidence = {'policy': 'p21-diagnostics-v1', 'execution': None}
            client_log = cache / 'lib/p21-client-1.0.9.log'
            previous_log = client_log.read_bytes() if client_log.exists() else b''
            try:
                execution = command(argv, cache, directory / 'p21.log', p['timeout_seconds'])
                after = manifest(cache)
                changes = {name: {'before': before.get(name), 'after': after.get(name)}
                           for name in sorted(before.keys() | after.keys())
                           if before.get(name) != after.get(name)}
                mutable = {'lib/engines/app.data', 'lib/p21-client-1.0.9.log'}
                immutable = sorted(set(changes) - mutable)
                log_bytes = client_log.read_bytes() if client_log.exists() else b''
                new_log = log_bytes[len(previous_log):] if log_bytes.startswith(previous_log) else log_bytes
                stdout = directory / 'p21.log'
                texts = [new_log.decode(errors='replace'), stdout.read_text(errors='replace') if stdout.exists() else '']
                pattern = r'(?m)(?:\bERROR\b|Exception in thread|^\s*(?:java|net)\.[\w.$]*(?:Exception|Error)(?::|$))'
                error_counts = [len(re.findall(pattern, text)) for text in texts]
                evidence.update(runtime_changes=changes, immutable_changed_paths=immutable,
                                mutable_changed_paths=sorted(set(changes) & mutable),
                                client_error_markers=error_counts[0], stdout_error_markers=error_counts[1])
                if immutable:
                    raise P21ValidationError('runtime_integrity', 'P21 immutable runtime or configuration changed')
                if execution['timed_out']:
                    raise P21ValidationError('timeout', 'P21 validation timed out')
                if any(error_counts):
                    raise P21ValidationError('client_runtime_error', 'P21 client logged runtime errors; report is unqualified')
                if not report.exists():
                    raise P21ValidationError('missing_report', 'P21 did not produce a fresh completed report')
                actual = {f.stem.upper() for f in data.iterdir() if f.suffix.lower() == '.xpt'}
                result = conformance_metrics(report, self.c['expected_datasets'], actual,
                                       ['FDA 2508.1', '1.0.9', p['ct'], 'ADaM-IG 1.3 (FDA).xml', 'MedDRA', '8.0'])
                result['execution'] = execution
                result['diagnostics'] = 'p21-diagnostics.json'
                return result
            except Exception as exc:
                failure = exc
                raise
            finally:
                # Preserve raw manifests, logs and execution metadata even when a gate fails.
                save(directory / 'p21-runtime-before.json', before)
                save(directory / 'p21-runtime-after.json', manifest(cache))
                if client_log.exists():
                    shutil.copy2(client_log, directory / 'p21-client.log')
                retain = failure is not None or not (result or {}).get('report_usable')
                evidence.update(execution=execution, cache_retained=retain,
                                failure_code=getattr(failure, 'code', 'evaluation_error') if failure else None,
                                failure_reason=str(failure) if failure else None,
                                report_usable=(result or {}).get('report_usable', False))
                if retain:
                    shutil.move(str(cache), str(directory / 'p21-failed-runtime'))
                save(directory / 'p21-diagnostics.json', evidence)

    def __call__(self, workspace, directory):
        data = workspace / 'output/adam/datasets'
        result = {'status': 'evaluated', 'correctness': None, 'conformance': None,
                  'semantic_reproduced': None, 'byte_reproduced': None}
        expected = {s.lower()+'.xpt' for s in self.c['expected_datasets']} | {'define.xml'}
        actual = {p.name.lower() for p in data.iterdir()} if data.exists() else set()
        result['required_artifacts'] = {p: (workspace / p).is_file() for p in
            ('output/adam/programs/rebuild.py', 'output/adam/manifest.json', 'output/adam/notes.md')}
        result['missing_files'], result['extra_files'] = sorted(expected-actual), sorted(actual-expected)
        result['dataset_set_complete'] = {s.lower()+'.xpt' for s in self.c['expected_datasets']} == {p for p in actual if p.endswith('.xpt')}
        result['deliverables_complete'] = not result['missing_files'] and not result['extra_files'] and all(result['required_artifacts'].values())
        result['content_profile'] = profile(data, self.c['expected_datasets'])
        # Each endpoint records its own failure; never turn unavailable into zero.
        for name, task in [('correctness', lambda: score(Path(self.c['inputs']), data)),
                           ('conformance', lambda: self.p21(workspace, directory))]:
            try:
                result[name] = task()
            except Exception as exc:
                result[name] = {'status': 'unavailable', 'reason': str(exc)}
                if name == 'conformance':
                    result[name]['failure_code'] = getattr(exc, 'code', 'evaluation_error')
                    result[name]['diagnostics'] = 'p21-diagnostics.json'
                if name == 'conformance':
                    result[name].update(report_usable=False, dataset_rule_pairs=None,
                                        finding_instances=None, distinct_rules=None,
                                        validated_datasets=None, validation_coverage_complete=False)
        try:
            replay = directory / 'replay'
            programs = workspace / 'output/adam/programs'
            shutil.copytree(programs, replay / 'output/adam/programs')
            execution = self.rebuild_runtime.rebuild(replay, ['python', 'output/adam/programs/rebuild.py'],
                                          directory / 'rebuild.log', self.c['rebuild_timeout_seconds'])
            result['rebuild'] = execution
            rebuilt = replay / 'output/adam/datasets'
            complete = not result['missing_files'] and not result['extra_files']
            result['byte_reproduced'] = complete and execution['exit_code'] == 0 and manifest(data) == manifest(rebuilt)
            result['semantic_reproduced'] = complete and execution['exit_code'] == 0 and semantic(data, rebuilt)
        except Exception as exc:
            result['rebuild_error'] = str(exc)
        save(directory / 'evaluation.json', result)
        return result
