"""素材目录和传输包的自制临时数据测试；不读取真实游戏资源或存档。"""
import hashlib
import json
import os
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
import zlib
from pathlib import Path
from unittest import mock

from art_library import (build_catalog,export_bundle,verify_bundle,import_bundle,
                         BUNDLE_MANIFEST,LIBRARY_FILES,_render)


def png():
    def chunk(name,raw):
        return struct.pack('>I',len(raw))+name+raw+struct.pack('>I',zlib.crc32(name+raw)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
            +chunk(b'IDAT',zlib.compress(b'\0\xff\x80\0\xff'))+chunk(b'IEND',b''))


def fixture(root):
    root.mkdir(parents=True)
    for directory in ('ui','textures','models','maps','effects','rendering'):
        (root/directory).mkdir()
    def write(name,value):
        (root/name).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    write('manifest.json',{'format':'oc2-web-preview-v1',
        'ui':{'format':'oc2-original-ui-v2','url':'/assets/ui/profile.json'},
        'effects':{'format':'oc2-combat-effects-v3','url':'/assets/effects/combat.json'},
        'rendering':{'format':'oc2-scene-render-v1','url':'/assets/rendering/tutorial.json'},
        'player':{'url':'/assets/models/player.json'},'map':{'url':'/assets/maps/test.json'},
        'textures':{'test':'/assets/textures/stone.png'}})
    write('ui/profile.json',{'format':'oc2-original-ui-v2',
        'assets':{'button':{'url':'/assets/ui/button.png','sourcePath':'ui/Texture/raw.png',
                           'sourceSymbol':'<img src=x onerror="alert(1)">'}},
        'fonts':{'faces':{
            'chineseText':{'url':'/assets/ui/chineseText.woff','family':'原字体<script>bad()</script>','glyphCount':2},
            'chineseDisplay':{'url':'/assets/ui/chineseDisplay.woff','family':'原标题字','glyphCount':2}}},
        'skillIcons':{'icons':{
            'fireball':{'url':'/assets/ui/skill-fireball.png','sourcePath':'ui/icons/skill/fire.png'},
            'frost_blast':{'url':'/assets/ui/skill-frost_blast.png','sourcePath':'ui/icons/skill/frost_blast.png'}}}})
    write('models/player.json',{'format':'synthetic-model','source':'model/test.bdae'})
    write('maps/test.json',{'format':'synthetic-map','positions':[0,0,0]})
    write('effects/combat.json',{'format':'oc2-combat-effects-v3','effects':{}})
    write('rendering/tutorial.json',{'format':'oc2-scene-render-v1','zones':[]})
    for name in ('ui/button.png','ui/skill-fireball.png','ui/skill-frost_blast.png','textures/stone.png'):
        (root/name).write_bytes(png())
    # Catalogs use existing profile metadata; import/verify never parse a font.
    for name in ('chineseText','chineseDisplay'):
        (root/f'ui/{name}.woff').write_bytes(b'wOFF-self-made-test-'+name.encode())
    return root


def rewrite(source,target,changes=None,extra=None,update_manifest=False):
    changes=changes or {};extra=extra or []
    with zipfile.ZipFile(source) as archive:
        contents={info.filename:archive.read(info) for info in archive.infolist()}
    for name,value in changes.items():
        if value is None:contents.pop(name)
        else:contents[name]=value
    if update_manifest:
        manifest=json.loads(contents[BUNDLE_MANIFEST])
        for record in manifest['files']:
            raw=contents['converted/'+record['path']]
            record['bytes']=len(raw);record['sha256']=hashlib.sha256(raw).hexdigest()
        manifest['totalBytes']=sum(record['bytes'] for record in manifest['files'])
        contents[BUNDLE_MANIFEST]=json.dumps(manifest).encode()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,raw in contents.items():archive.writestr(name,raw)
            for name,raw in extra:archive.writestr(name,raw)
    return target


class ArtLibraryTests(unittest.TestCase):
    def test_optional_scene_baked_profile_is_version_checked_and_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=fixture(Path(tmp)/'game-data/converted')
            manifest=json.loads((root/'manifest.json').read_text())
            manifest['sceneBakedLighting']={'url':'/assets/rendering/baked-lighting.json','format':'oc2-scene-baked-lighting-v1'}
            (root/'manifest.json').write_text(json.dumps(manifest))
            profile=root/'rendering/baked-lighting.json'
            profile.write_text(json.dumps({'format':'oc2-scene-baked-lighting-v1'}))
            bundle=export_bundle(root)
            self.assertEqual(verify_bundle(bundle['path'])['sourceFormats']['sceneBakedLighting'],'oc2-scene-baked-lighting-v1')
            profile.write_text(json.dumps({'format':'old'}))
            with self.assertRaisesRegex(ValueError,'不一致'):build_catalog(root)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='oc2-art-test-')
        self.root=Path(self.temp.name)
        self.source=fixture(self.root/'dev/game-data/converted')
        self.bundle=Path(export_bundle(self.source)['path'])

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_groups_sources_pixels_fonts_and_escapes_all_text(self):
        catalog=build_catalog(self.source)
        entries={entry['path']:entry for entry in catalog['entries']}
        self.assertEqual(entries['ui/skill-fireball.png']['category'],'skillIcons')
        self.assertEqual(entries['ui/chineseText.woff']['category'],'fonts')
        self.assertEqual(entries['models/player.json']['category'],'models')
        self.assertEqual((entries['ui/button.png']['width'],entries['ui/button.png']['height']),(1,1))
        refs=entries['ui/button.png']['references']
        self.assertEqual(refs[0]['details']['sourcePath'],'ui/Texture/raw.png')
        self.assertFalse(any(entry['path'] in LIBRARY_FILES for entry in catalog['entries']))
        page=(self.source/'library/index.html').read_text()
        css=(self.source/'library/style.css').read_text()
        self.assertIn('loading="lazy"',page)
        self.assertIn('href="../ui/skill-fireball.png"',page)
        self.assertIn('href="style.css"',page)
        self.assertIn('冒险者在微光试炼中',page)
        self.assertIn('url("../ui/chineseText.woff")',css)
        self.assertIn('&lt;img',page)
        self.assertNotIn('<script',page);self.assertNotIn('<style',page);self.assertNotIn(' style=',page)
        self.assertNotIn('https://',page)

    def test_real_zip_roundtrip_preserves_files_backup_and_runtime(self):
        manifest=verify_bundle(self.bundle)
        target=self.root/'friend/game-data/converted';target.mkdir(parents=True)
        (target/'old.json').write_text('{"old":true}')
        runtime=self.root/'friend/runtime/characters.json';runtime.parent.mkdir()
        runtime.write_text('{"private":"save"}')
        result=import_bundle(self.bundle,target)
        backup=Path(result['backup'])
        self.assertEqual(backup.parent,target.parent.resolve())
        self.assertTrue(backup.name.startswith('converted.backup-'))
        self.assertEqual((backup/'old.json').read_text(),'{"old":true}')
        self.assertEqual(runtime.read_text(),'{"private":"save"}')
        for record in manifest['files']:
            self.assertEqual((target/record['path']).read_bytes(),(self.source/record['path']).read_bytes())
        self.assertEqual(result['sourceFormats']['ui'],'oc2-original-ui-v2')
        self.assertFalse(list(target.parent.glob('.converted-import-*')))

    def test_bad_hash_is_rejected_before_target_or_staging_changes(self):
        name='converted/ui/chineseText.woff'
        with zipfile.ZipFile(self.bundle) as archive:raw=archive.read(name)
        bad=rewrite(self.bundle,self.root/'hash.zip',{name:raw[:-1]+b'X'})
        target=self.root/'friend/game-data/converted'
        with self.assertRaisesRegex(ValueError,'哈希'):
            import_bundle(bad,target)
        self.assertFalse(target.parent.exists())

    def test_path_escape_absolute_and_cross_platform_paths_are_rejected(self):
        for index,name in enumerate(('converted/../escape.json','/tmp/escape.json',
                                      'converted/ui/../../escape.png','converted\\ui\\a.png',
                                      'C:/escape.json','converted/ui/%2e%2e/escape.json')):
            with self.subTest(name=name):
                bad=rewrite(self.bundle,self.root/f'path{index}.zip',extra=[(name,b'x')])
                with self.assertRaises(ValueError):verify_bundle(bad)
        self.assertFalse((self.root/'escape.json').exists())

    def test_duplicate_extra_and_unicode_or_case_collisions_are_rejected(self):
        for index,name in enumerate(('converted/ui/button.png','converted/ui/Button.png',
                                      'converted/ui/extra.json','runtime/characters.json')):
            with self.subTest(name=name):
                bad=rewrite(self.bundle,self.root/f'extra{index}.zip',extra=[(name,b'x')])
                with self.assertRaises(ValueError):verify_bundle(bad)

    def test_symbolic_link_entry_and_expansion_limit_are_rejected(self):
        info=zipfile.ZipInfo('converted/ui/link.png');info.create_system=3
        info.external_attr=(stat.S_IFLNK|0o777)<<16
        bad=rewrite(self.bundle,self.root/'symlink.zip',extra=[(info,b'../../outside')])
        with self.assertRaisesRegex(ValueError,'符号链接'):verify_bundle(bad)
        with self.assertRaisesRegex(ValueError,'展开大小'):verify_bundle(self.bundle,max_total_bytes=100)

    def test_nul_suffix_in_raw_zip_name_is_not_silently_truncated(self):
        bad=self.root/'nul-name.zip'
        original='converted/ui/button.png'
        with zipfile.ZipFile(self.bundle) as source,zipfile.ZipFile(bad,'w',compression=zipfile.ZIP_DEFLATED) as output:
            for info in source.infolist():
                output.writestr(info.filename+'X' if info.filename==original else info.filename,source.read(info))
        raw=bad.read_bytes().replace((original+'X').encode(),original.encode()+b'\0')
        bad.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'NUL'):verify_bundle(bad)

    def test_wrong_bundle_or_inner_ui_versions_are_rejected(self):
        with zipfile.ZipFile(self.bundle) as archive:
            manifest=json.loads(archive.read(BUNDLE_MANIFEST))
        manifest['sourceFormats']['ui']='wrong-version'
        bad=rewrite(self.bundle,self.root/'version.zip',{BUNDLE_MANIFEST:json.dumps(manifest).encode()})
        with self.assertRaisesRegex(ValueError,'版本不一致'):verify_bundle(bad)
        bad=rewrite(self.bundle,self.root/'inner-version.zip',{
            'converted/ui/profile.json':b'{"format":"different-profile"}'},update_manifest=True)
        with self.assertRaisesRegex(ValueError,'版本不一致'):verify_bundle(bad)

    def test_self_consistent_script_page_still_cannot_replace_static_catalog(self):
        bad=rewrite(self.bundle,self.root/'script.zip',{
            'converted/library/index.html':b'<script>bad()</script>'},update_manifest=True)
        with self.assertRaisesRegex(ValueError,'无脚本'):verify_bundle(bad)

    def test_catalog_dimensions_cannot_inject_html_or_lie_about_png(self):
        for index,width in enumerate(('<script>bad()</script>',2,True)):
            catalog=json.loads((self.source/'library/catalog.json').read_text())
            entry=next(item for item in catalog['entries'] if item['path']=='ui/button.png')
            entry['width']=width
            markup,css=_render(catalog)
            self.assertNotIn(b'<script>',markup)
            bad=rewrite(self.bundle,self.root/f'dimensions{index}.zip',{
                'converted/library/catalog.json':json.dumps(catalog).encode(),
                'converted/library/index.html':markup,'converted/library/style.css':css},update_manifest=True)
            with self.assertRaisesRegex(ValueError,'尺寸'):verify_bundle(bad)

    def test_arbitrary_source_directory_and_finder_metadata_are_supported(self):
        source=self.root/'custom-preview-output';os.replace(self.source,source)
        before=build_catalog(source)['fileCount']
        (source/'.DS_Store').write_bytes(b'finder metadata')
        (source/'ui/._button.png').write_bytes(b'finder resource fork')
        catalog=build_catalog(source)
        self.assertEqual(catalog['fileCount'],before)
        bundle=Path(export_bundle(source,self.root/'custom.zip')['path'])
        manifest=verify_bundle(bundle)
        self.assertFalse(any('.DS_Store' in item['path'] or '/._' in item['path'] for item in manifest['files']))

    def test_invalid_import_targets_and_symlinks_are_rejected(self):
        for target in (self.root/'friend/converted',self.root/'friend/game-data/assets',self.root):
            with self.assertRaisesRegex(ValueError,'game-data/converted'):
                import_bundle(self.bundle,target)
        parent=self.root/'link/game-data';parent.mkdir(parents=True)
        outside=self.root/'outside';outside.mkdir();(outside/'keep').write_text('unchanged')
        (parent/'converted').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'符号链接'):
            import_bundle(self.bundle,parent/'converted')
        self.assertEqual((outside/'keep').read_text(),'unchanged')

    def test_failed_install_rolls_back_old_tree_and_removes_staging(self):
        target=self.root/'friend/game-data/converted';target.mkdir(parents=True)
        (target/'old.json').write_text('keep')
        replace=os.replace
        def fail_install(source,destination):
            if Path(source).parent.name.startswith('.converted-import-'):
                raise OSError('synthetic disk failure')
            return replace(source,destination)
        with mock.patch('art_library.os.replace',side_effect=fail_install):
            with self.assertRaisesRegex(OSError,'disk failure'):
                import_bundle(self.bundle,target)
        self.assertEqual((target/'old.json').read_text(),'keep')
        self.assertFalse(list(target.parent.glob('converted.backup-*')))
        self.assertFalse(list(target.parent.glob('.converted-import-*')))

    def test_export_excludes_raw_files_and_never_overwrites_an_existing_bundle(self):
        before=self.bundle.read_bytes()
        with self.assertRaises(FileExistsError):export_bundle(self.source,self.bundle)
        self.assertEqual(self.bundle.read_bytes(),before)
        (self.source/'ui/raw.ttf').write_bytes(b'raw font')
        with self.assertRaisesRegex(ValueError,'不允许传输'):export_bundle(self.source)
        (self.source/'ui/raw.ttf').unlink()
        (self.source/'runtime').mkdir();(self.source/'runtime/characters.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'不允许传输'):build_catalog(self.source)


if __name__=='__main__':unittest.main()
