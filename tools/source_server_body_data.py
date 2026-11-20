"""Explicit server-only projection of verified converted body metadata.

The original full JSON and its identity remain unchanged. A pinned projection
is a distinct input, never a replacement body/motion binding or Native buffer.
Default callers still load the full input. No Native module is imported here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import weakref

FORMAT = 'oc2-server-body-data-index-v1'
PROJECTION = 'oc2-server-body-data-v1'
_TOKEN = object()
_VERIFIED = {}


def _canonical_bytes(value):
    # Exactly the existing full-dictionary canonical serialization.
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _private_path(root, value, *, output=False):
    root = Path(root).resolve()
    if not isinstance(value, (str, Path)):
        raise ValueError('Explicit private resource path required')
    path = Path(value)
    if '..' in path.parts:
        raise ValueError('Private resource traversal is not allowed')
    if not path.is_absolute():
        path = root / path
    raw = root / 'analysis' / 'raw'
    try:
        relative = path.relative_to(raw)
    except ValueError as error:
        raise ValueError('Server body input must remain in analysis/raw') from error
    cursor = root
    for part in ('analysis', 'raw', *relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError('Symlink server body inputs are not allowed')
    resolved = path.resolve()
    if not resolved.is_relative_to(raw):
        raise ValueError('Server body input escaped analysis/raw')
    if not output and not resolved.is_file():
        raise ValueError('Server body input file is missing')
    return resolved


def _descriptor(root, value):
    if not isinstance(value, dict) or not {'path', 'sha256'} <= set(value) or set(value) - {'path', 'sha256', 'bytes'}:
        raise ValueError('Exact pinned server body descriptor required')
    if not _sha256(value['sha256']) or ('bytes' in value and (type(value['bytes']) is not int or value['bytes'] < 0)):
        raise ValueError('Valid resource SHA/size required')
    return _private_path(root, value['path'])


def _read_pinned(root, descriptor):
    path = _descriptor(root, descriptor)
    raw = path.read_bytes()
    if _digest(raw) != descriptor['sha256'] or ('bytes' in descriptor and len(raw) != descriptor['bytes']):
        raise ValueError('Pinned server body bytes differ')
    return path, raw


def _verify_stream(root, descriptor):
    path = _descriptor(root, descriptor)
    digest = hashlib.sha256(); size = 0
    with path.open('rb') as source:
        while True:
            block = source.read(65536)
            if not block:
                break
            digest.update(block); size += len(block)
    if digest.hexdigest() != descriptor['sha256'] or ('bytes' in descriptor and size != descriptor['bytes']):
        raise ValueError('Original full body source changed')
    return path, size


class VerifiedBodyData(dict):
    """Loader-branded data; ordinary JSON or copied instances have no proof."""
    __slots__ = ('__weakref__',)

    def __new__(cls, payload, *, _token=None):
        if cls is not VerifiedBodyData or _token is not _TOKEN:
            raise ValueError('Only the verified server body loader may create this input')
        return dict.__new__(cls)

    def __init__(self, payload, *, _token=None):
        if _token is not _TOKEN:
            raise ValueError('Verified server body source required')
        dict.__init__(self, payload)


def body_data_canonical(data):
    """Full input: original canonical; projected input: verified source identity.

    The latter is available only for this live loader-created object, after
    checking its complete current payload again. No JSON marker grants it.
    """
    if type(data) is VerifiedBodyData:
        proof = _VERIFIED.get(id(data))
        if proof is None or proof[0]() is not data:
            raise ValueError('Server projection has no loader provenance')
        if _digest(_canonical_bytes(data)) != proof[1]:
            raise ValueError('Verified server body payload was modified')
        return proof[2]
    if isinstance(data, VerifiedBodyData):
        raise ValueError('Unsupported server projection subclass')
    return _digest(_canonical_bytes(data))


def source_server_body_data_index(root):
    """Trusted optional host switch; an enabled but invalid plan never falls back."""
    flag = os.environ.get('OC2_SERVER_BODY_DATA', '0')
    if flag not in ('0', '1'):
        raise ValueError('OC2_SERVER_BODY_DATA must be 0 or 1')
    if flag == '0':
        return None
    root = Path(root).resolve(); path = root / 'tools/source_world_python.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError('Pinned server body plan declaration is missing')
    declaration = json.loads(path.read_text())
    plans = declaration.get('plans') if isinstance(declaration, dict) else None
    plan = plans.get('serverBodyData') if isinstance(plans, dict) else None
    if not isinstance(plan, dict) or set(plan) != {'path', 'sha256', 'bytes'}:
        raise ValueError('Enabled server body projection requires a pinned plan')
    relative = Path(plan['path']) if isinstance(plan['path'], str) else None
    if relative is None or relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Server body plan requires a private relative runtime path')
    descriptor = {**plan, 'path': str(root / 'analysis/raw/portable/running-preview' / relative)}
    _descriptor(root, descriptor)
    # Actual bytes are checked before any projected resource is returned.
    return descriptor


def reuse_animation_reader(root, descriptor, reader):
    """Reuse a proven read-only Python reader, never its writable Native VM.

    Current own animation files are raw BRES. A wrapped/compressed input whose
    decoded bytes differ from the pinned source does not satisfy this contract.
    No constructor/parse/queue/clock/RNG operation is performed here.
    """
    from bdae_animation import BDAEAnimation
    if type(reader) is not BDAEAnimation:
        raise ValueError('Exact existing BDAEAnimation immutable byte reader required')
    path, size = _verify_stream(root, descriptor)
    if _private_path(root, reader.path) != path:
        raise ValueError('Existing animation reader differs from the pinned source')
    if type(reader.b) is bytes:
        if _digest(reader.b) != descriptor['sha256']:
            raise ValueError('Existing animation reader differs from the pinned source')
    else:
        from source_immutable_inputs import require_source
        require_source(reader.b, path, expected_sha=descriptor['sha256'])
        if len(reader.b) != size:
            raise ValueError('Existing authenticated animation size differs')
    if reader.info != reader.q(40) or reader.version != reader.string(reader.q(reader.info)):
        raise ValueError('Existing animation reader metadata was modified')
    return reader


def load_server_body_data(root, original_descriptor, mask_descriptor, index_descriptor=None):
    """Read full legacy data, or an independently pinned server projection."""
    if index_descriptor is None:
        _, raw = _read_pinned(root, original_descriptor)
        return json.loads(raw)
    index_path, index_raw = _read_pinned(root, index_descriptor)
    index = json.loads(index_raw)
    if not isinstance(index, dict) or set(index) != {'format', 'sources'} or index['format'] != FORMAT or not isinstance(index['sources'], dict):
        raise ValueError('Exact server body projection index required')
    original_path, original_size = _verify_stream(root, original_descriptor)
    row = index['sources'].get(original_descriptor['sha256'])
    if not isinstance(row, dict) or set(row) != {'source', 'mask', 'payload', 'projection'} or row['projection'] != PROJECTION:
        raise ValueError('No exact server projection for original body source')
    source = row['source']
    if not isinstance(source, dict) or set(source) != {'sha256', 'bytes', 'canonicalSHA256'} or not _sha256(source['canonicalSHA256']):
        raise ValueError('Exact original full-body provenance required')
    if source['sha256'] != original_descriptor['sha256'] or type(source['bytes']) is not int or source['bytes'] != original_size:
        raise ValueError('Server projection source differs from requested original')
    mask_path, mask_raw = _read_pinned(root, mask_descriptor)
    if not isinstance(row['mask'], dict) or set(row['mask']) != {'sha256'} or row['mask']['sha256'] != mask_descriptor['sha256']:
        raise ValueError('Server projection belongs to another property mask')
    mask = json.loads(mask_raw)
    if mask.get('bodyDataSHA256') != source['sha256'] or mask.get('bodyDataCanonicalSHA256') != source['canonicalSHA256']:
        raise ValueError('Original mask/full canonical provenance differs')
    payload_descriptor = row['payload']
    if not isinstance(payload_descriptor, dict) or not isinstance(payload_descriptor.get('path'), str):
        raise ValueError('Explicit pinned projection payload required')
    relative_payload = Path(payload_descriptor['path'])
    if relative_payload.is_absolute() or '..' in relative_payload.parts:
        raise ValueError('Projection payload must be relative to its pinned index')
    payload_path, payload_raw = _read_pinned(root, {**payload_descriptor, 'path': str(index_path.parent / relative_payload)})
    if payload_path in (original_path, mask_path):
        raise ValueError('Server projection must be a distinct resource')
    payload = json.loads(payload_raw)
    _check_projection_shape(payload)
    data = VerifiedBodyData(payload, _token=_TOKEN)
    identity = id(data)
    def expired(ref):
        current = _VERIFIED.get(identity)
        if current is not None and current[0] is ref:
            del _VERIFIED[identity]
    _VERIFIED[identity] = (weakref.ref(data, expired), _digest(_canonical_bytes(payload)), source['canonicalSHA256'])
    return data


def _check_projection_shape(data):
    if not isinstance(data, dict) or not {'meshes', 'rig'} <= set(data) or set(data) - {'meshes', 'rig', 'source', 'sourcePlayerChoiceBody'}:
        raise ValueError('Only explicit server model fields are allowed')
    meshes = data['meshes']; rig = data['rig']
    if not isinstance(meshes, list) or len(meshes) != 1 or not isinstance(meshes[0], dict) or set(meshes[0]) != {'name', 'vertexCount'}:
        raise ValueError('Exact original mesh0 metadata required')
    if not isinstance(meshes[0]['name'], str) or not meshes[0]['name'] or type(meshes[0]['vertexCount']) is not int or meshes[0]['vertexCount'] <= 0:
        raise ValueError('Valid original mesh name/count required')
    if not isinstance(rig, dict) or set(rig) != {'nodes', 'skins'} or not isinstance(rig['nodes'], list) or not rig['nodes'] or not isinstance(rig['skins'], list) or not rig['skins']:
        raise ValueError('Complete original node and bone-name tables required')
    names = {}
    for i, node in enumerate(rig['nodes']):
        if not isinstance(node, dict) or not isinstance(node.get('name'), str) or not isinstance(node.get('aliases'), list):
            raise ValueError('Literal original nodes required')
        for name in [node['name'], *node['aliases']]:
            if not isinstance(name, str) or (name in names and names[name] != i):
                raise ValueError('Ambiguous original node alias')
            names[name] = i
    for skin in rig['skins']:
        if not isinstance(skin, dict) or set(skin) != {'boneNames'} or not isinstance(skin['boneNames'], list) or any(name not in names for name in skin['boneNames']):
            raise ValueError('Original skin bone-name lookup differs')


def project_server_body_data(full):
    """Offline field projection; every literal node/attachment is retained."""
    projected = {k: full[k] for k in ('source', 'sourcePlayerChoiceBody') if k in full}
    projected['meshes'] = [{k: full['meshes'][0][k] for k in ('name', 'vertexCount')}]
    projected['rig'] = {'nodes': full['rig']['nodes'],
                        'skins': [{'boneNames': skin['boneNames']} for skin in full['rig']['skins']]}
    _check_projection_shape(projected)
    return projected


def build_server_body_projection(root, original_descriptor, mask_descriptor, payload_path, index_path):
    """Offline build from pinned full sources. Refuse to overwrite old outputs."""
    source_path, source_raw = _read_pinned(root, original_descriptor)
    mask_path, mask_raw = _read_pinned(root, mask_descriptor)
    full = json.loads(source_raw); mask = json.loads(mask_raw)
    canonical = body_data_canonical(full)
    if mask.get('bodyDataSHA256') != _digest(source_raw) or mask.get('bodyDataCanonicalSHA256') != canonical or mask.get('sha256') != _digest(_canonical_bytes({k:v for k,v in mask.items() if k != 'sha256'})):
        raise ValueError('Full original body/mask canonical proof differs')
    projected = project_server_body_data(full)
    # Mask order/weights and all aliases remain actual source fields; no new
    # property/motion binding is generated by this projection.
    aliases = {name for node in projected['rig']['nodes'] for name in [node['name'], *node['aliases']]}
    order = mask['sourcePropertyOrder']; weights = mask['compatible']['sourcePropertyWeights']
    if len(order) != len(weights) or not mask['compatible']['propertiesCompatible']:
        raise ValueError('Complete compatible original property mask required')
    for i, (row, weight) in enumerate(zip(order, weights)):
        if row['index'] != i or row['node'] not in aliases or row['type'] not in (1,5,10) or weight not in (0.,.5,1.):
            raise ValueError('Original property order/alias/weight differs')
    payload_path = _private_path(root, payload_path, output=True)
    index_path = _private_path(root, index_path, output=True)
    if payload_path == index_path or payload_path in (source_path, mask_path) or index_path in (source_path, mask_path) or payload_path.exists() or index_path.exists():
        raise ValueError('Server projection needs distinct new output files')
    payload_raw = _canonical_bytes(projected) + b'\n'
    try:
        relative_payload = payload_path.relative_to(index_path.parent).as_posix()
    except ValueError as error:
        raise ValueError('Build projection payload within its index directory') from error
    row = {'source': {'sha256': _digest(source_raw), 'bytes': len(source_raw), 'canonicalSHA256': canonical},
           'mask': {'sha256': _digest(mask_raw)},
           'payload': {'path': relative_payload, 'sha256': _digest(payload_raw), 'bytes': len(payload_raw)},
           'projection': PROJECTION}
    index_raw = _canonical_bytes({'format': FORMAT, 'sources': {row['source']['sha256']: row}}) + b'\n'
    payload_path.parent.mkdir(parents=True, exist_ok=True); index_path.parent.mkdir(parents=True, exist_ok=True)
    with payload_path.open('xb') as output:
        output.write(payload_raw)
    with index_path.open('xb') as output:
        output.write(index_raw)
    return {'path': str(index_path), 'sha256': _digest(index_raw), 'bytes': len(index_raw)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-descriptor', type=Path, required=True)
    parser.add_argument('--mask-descriptor', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    args = parser.parse_args()
    result = build_server_body_projection(args.root, json.loads(args.source_descriptor.read_text()),
        json.loads(args.mask_descriptor.read_text()), args.payload, args.index)
    print(json.dumps(result))
