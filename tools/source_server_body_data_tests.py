"""Pure JSON/private-file lifecycle fixtures, not Native equivalence or art QA."""
import copy
import gc
import hashlib
import json
import os
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import source_server_body_data as model


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode() + b'\n'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class ServerBodyDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.private = self.root / 'analysis/raw/qa'
        self.private.mkdir(parents=True)
        self.full = {'source': 'fixture/model.bdae',
          'sourcePlayerChoiceBody': {'key': 'fixture', 'sourceModelId': 999},
          'rig': {'nodes': [{'name': 'root', 'aliases': ['Root'], 'parent': -1,
                    'position': [0,0,0], 'quaternion': [0,0,0,1], 'scale': [1,1,1],
                    'attachments': [{'kind': 2, 'reference': '#fixture-skin'}]}],
                  'skins': [{'boneNames': ['root'], 'skinWeights': [1.], 'skinIndices': [0]}]},
          'meshes': [{'name': 'fixture', 'vertexCount': 1, 'positions': [0,0,0], 'uv': [0,0]}],
          'materials': [{'diffuse': 'fixture.png'}],
          'clips': [{'name': 'unused', 'nativeClock': {'frames': [0,1], 'values': [0,0,0]}}]}
        self.source = self.private / 'full.json'; self.source.write_bytes(raw(self.full))
        self.original = pin(self.source)
        mask = {'bodyDataSHA256': self.original['sha256'],
                'bodyDataCanonicalSHA256': model.body_data_canonical(self.full),
                'sourcePropertyOrder': [{'index': 0, 'node': 'root', 'type': 1}],
                'compatible': {'propertiesCompatible': True, 'sourcePropertyWeights': [1.]}}
        mask['sha256'] = model.body_data_canonical(mask)
        self.mask = self.private / 'mask.json'; self.mask.write_bytes(raw(mask)); self.mask_pin = pin(self.mask)
        self.payload = self.private / 'data/lite.json'; self.index = self.private / 'index.json'
        self.index_pin = model.build_server_body_projection(self.root, self.original, self.mask_pin, self.payload, self.index)

    def load(self):
        return model.load_server_body_data(self.root, self.original, self.mask_pin, self.index_pin)

    def rewrite_index(self, change):
        data = json.loads(self.index.read_bytes()); change(data)
        self.index.write_bytes(raw(data)); self.index_pin = pin(self.index)

    def test_default_full_input_and_old_canonical(self):
        data = model.load_server_body_data(self.root, self.original, self.mask_pin)
        self.assertIs(type(data), dict); self.assertEqual(data, self.full)
        self.assertEqual(model.body_data_canonical(data), model.body_data_canonical(self.full))

    def test_projected_input_retains_exact_used_fields(self):
        data = self.load()
        self.assertIs(type(data), model.VerifiedBodyData)
        self.assertEqual(data['rig']['nodes'], self.full['rig']['nodes'])
        self.assertEqual(data['rig']['skins'], [{'boneNames': ['root']}])
        self.assertEqual(data['meshes'], [{'name': 'fixture', 'vertexCount': 1}])
        self.assertNotIn('clips', data); self.assertNotIn('materials', data)
        self.assertEqual(model.body_data_canonical(data), model.body_data_canonical(self.full))

    def test_full_source_hash_is_streamed_not_read_bytes(self):
        real = Path.read_bytes
        def guarded(path):
            if path == self.source:
                self.fail('Projected runtime must not read the complete full JSON bytes')
            return real(path)
        with patch.object(Path, 'read_bytes', guarded):
            self.assertEqual(self.load()['meshes'][0]['vertexCount'], 1)

    def test_copied_plain_json_cannot_claim_original_canonical(self):
        data = self.load(); copied = json.loads(json.dumps(data))
        self.assertNotEqual(model.body_data_canonical(copied), model.body_data_canonical(self.full))

    def test_direct_constructor_and_forged_instance_are_rejected(self):
        with self.assertRaises(ValueError): model.VerifiedBodyData({})
        forged = dict.__new__(model.VerifiedBodyData); dict.__init__(forged, self.load())
        with self.assertRaises(ValueError): model.body_data_canonical(forged)

    def test_nested_mutation_is_detected_each_time(self):
        data = self.load(); self.assertEqual(model.body_data_canonical(data), model.body_data_canonical(self.full))
        data['rig']['nodes'][0]['position'][0] = 1
        with self.assertRaisesRegex(ValueError, 'modified'): model.body_data_canonical(data)

    def test_proof_does_not_retain_released_data(self):
        data = self.load(); identity = id(data); self.assertIn(identity, model._VERIFIED)
        del data; gc.collect(); self.assertNotIn(identity, model._VERIFIED)

    def test_corrupt_source_is_not_hidden_by_small_payload(self):
        self.source.write_bytes(self.source.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'source changed'): self.load()

    def test_corrupt_payload_and_index_are_rejected(self):
        self.payload.write_bytes(self.payload.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'bytes differ'): self.load()
        self.index.write_bytes(self.index.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'bytes differ'): self.load()

    def test_wrong_mask_and_canonical_are_rejected(self):
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']]['mask'].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError, 'another property mask'): self.load()
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']]['mask'].update(sha256=self.mask_pin['sha256']))
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']]['source'].update(canonicalSHA256='0'*64))
        with self.assertRaisesRegex(ValueError, 'canonical provenance'): self.load()

    def test_missing_row_and_wrong_projection_fail_closed(self):
        saved = self.index.read_bytes()
        self.rewrite_index(lambda j: j.update(sources={}))
        with self.assertRaisesRegex(ValueError, 'No exact'): self.load()
        self.index.write_bytes(saved); self.index_pin = pin(self.index)
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']].update(projection='wrong'))
        with self.assertRaisesRegex(ValueError, 'No exact'): self.load()

    def test_symlink_file_and_parent_and_outside_root_rejected(self):
        link = self.private / 'link.json'; link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            model.load_server_body_data(self.root, {**self.original, 'path': str(link)}, self.mask_pin)
        directory = self.private / 'linked'; directory.symlink_to(self.private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            model.load_server_body_data(self.root, {**self.original, 'path': str(directory / 'full.json')}, self.mask_pin)
        with self.assertRaisesRegex(ValueError, 'analysis/raw'):
            model.load_server_body_data(self.root, {**self.original, 'path': str(self.root / 'outside.json')}, self.mask_pin)

    def test_index_payload_path_is_relative_and_cannot_escape(self):
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']]['payload'].update(path='../full.json'))
        with self.assertRaisesRegex(ValueError, 'relative'): self.load()
        self.rewrite_index(lambda j: j['sources'][self.original['sha256']]['payload'].update(path=str(self.payload)))
        with self.assertRaisesRegex(ValueError, 'relative'): self.load()

    def test_relocation_uses_source_sha_and_not_original_host_path(self):
        moved = self.private / 'moved-full.json'; moved.write_bytes(self.source.read_bytes())
        moved_mask = self.private / 'moved-mask.json'; moved_mask.write_bytes(self.mask.read_bytes())
        data = model.load_server_body_data(self.root, pin(moved), pin(moved_mask), self.index_pin)
        self.assertEqual(model.body_data_canonical(data), model.body_data_canonical(self.full))

    def test_builder_rejects_wrong_canonical_and_never_overwrites(self):
        with self.assertRaisesRegex(ValueError, 'distinct new'):
            model.build_server_body_projection(self.root, self.original, self.mask_pin, self.payload, self.index)
        mask = json.loads(self.mask.read_bytes()); mask['bodyDataCanonicalSHA256'] = '0'*64
        mask['sha256'] = model.body_data_canonical({k:v for k,v in mask.items() if k != 'sha256'})
        self.mask.write_bytes(raw(mask))
        with self.assertRaisesRegex(ValueError, 'canonical proof'):
            model.build_server_body_projection(self.root, self.original, pin(self.mask), self.private/'new.json', self.private/'new-index.json')

    def test_builder_rejects_missing_source_alias(self):
        modified = copy.deepcopy(self.full); modified['rig']['nodes'][0]['name'] = 'other'
        self.source.write_bytes(raw(modified)); source = pin(self.source)
        mask = json.loads(self.mask.read_bytes()); mask.update(bodyDataSHA256=source['sha256'], bodyDataCanonicalSHA256=model.body_data_canonical(modified))
        mask['sha256'] = model.body_data_canonical({k:v for k,v in mask.items() if k != 'sha256'})
        self.mask.write_bytes(raw(mask))
        with self.assertRaises(ValueError):
            model.build_server_body_projection(self.root, source, pin(self.mask), self.private/'new.json', self.private/'new-index.json')

    def test_environment_default_is_off_without_any_manifest(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(model.source_server_body_data_index(self.root))

    def test_environment_enabled_missing_or_bad_plan_fails_closed(self):
        (self.root/'tools').mkdir(); declaration = self.root/'tools/source_world_python.json'
        with patch.dict(os.environ, {'OC2_SERVER_BODY_DATA':'1'}):
            with self.assertRaises(ValueError): model.source_server_body_data_index(self.root)
            for value in ({}, {'plans':{'serverBodyData':{}}}, {'plans':{'serverBodyData':{'path':'../x','sha256':'0'*64,'bytes':1}}}):
                declaration.write_bytes(raw(value))
                with self.assertRaises(ValueError): model.source_server_body_data_index(self.root)
        with patch.dict(os.environ, {'OC2_SERVER_BODY_DATA':'yes'}):
            with self.assertRaises(ValueError): model.source_server_body_data_index(self.root)

    def test_enabled_plan_is_descriptor_only_then_load_verifies_bytes(self):
        runtime = self.root/'analysis/raw/portable/running-preview/native-inputs/server-body-data-v1'
        runtime.mkdir(parents=True); installed_index = runtime/'index.json'; installed_payload = runtime/'data/lite.json'
        installed_payload.parent.mkdir(); installed_payload.write_bytes(self.payload.read_bytes())
        installed_index.write_bytes(self.index.read_bytes())
        (self.root/'tools').mkdir()
        declaration = {'plans':{'serverBodyData':{'path':'native-inputs/server-body-data-v1/index.json',**{k:v for k,v in pin(installed_index).items() if k!='path'},'bytes':installed_index.stat().st_size}}}
        (self.root/'tools/source_world_python.json').write_bytes(raw(declaration))
        with patch.dict(os.environ, {'OC2_SERVER_BODY_DATA':'1'}):
            descriptor = model.source_server_body_data_index(self.root)
            result = model.load_server_body_data(self.root, self.original, self.mask_pin, descriptor)
            self.assertEqual(model.body_data_canonical(result), model.body_data_canonical(self.full))
            installed_index.write_bytes(installed_index.read_bytes() + b' ')
            with self.assertRaises(ValueError): model.load_server_body_data(self.root, self.original, self.mask_pin, descriptor)

    def animation_fixture(self):
        from bdae_animation import BDAEAnimation
        data = bytearray(128); data[:8] = b'BRES\xfe\xff\x00\x00'
        struct.pack_into('<II', data, 8, 64, len(data)); struct.pack_into('<Q', data, 40, 64)
        struct.pack_into('<Q', data, 64, 80); data[80:90] = b'0,0,0,946\0'
        path = self.private/'animation.bdae'; path.write_bytes(data)
        return path, BDAEAnimation(path)

    def test_animation_reader_reuse_has_no_parse_read_bytes_or_mutation(self):
        from bdae_animation import BDAEAnimation
        path, reader = self.animation_fixture(); descriptor = pin(path)
        before = dict(reader.__dict__); real = Path.read_bytes
        def guarded(value):
            if value == path: self.fail('Reuse must hash the source file as a stream')
            return real(value)
        with patch.object(Path, 'read_bytes', guarded), patch.object(BDAEAnimation, '__init__', side_effect=AssertionError('No new reader')):
            self.assertIs(model.reuse_animation_reader(self.root, descriptor, reader), reader)
        self.assertEqual(reader.__dict__, before)

    def test_animation_reader_wrong_path_type_bytes_or_metadata_rejected(self):
        path, reader = self.animation_fixture(); descriptor = pin(path)
        duplicate = self.private/'duplicate.bdae'; duplicate.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'differs'): model.reuse_animation_reader(self.root, pin(duplicate), reader)
        with self.assertRaisesRegex(ValueError, 'Exact existing'): model.reuse_animation_reader(self.root, descriptor, object())
        original = reader.b; reader.b += b'x'
        with self.assertRaisesRegex(ValueError, 'differs'): model.reuse_animation_reader(self.root, descriptor, reader)
        reader.b = original; reader.info += 4
        with self.assertRaisesRegex(ValueError, 'metadata'): model.reuse_animation_reader(self.root, descriptor, reader)


if __name__ == '__main__':
    unittest.main()
