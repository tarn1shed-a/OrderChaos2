"""本地美术目录与校验传输包；不包含 APK、原资源包或角色存档。仅用 Python 标准库。"""
import argparse
import collections
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import stat
import struct
import tempfile
import unicodedata
import uuid
import zipfile
import zlib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERTED = ROOT / 'game-data/converted'
MAX_UNPACKED_BYTES = 512 * 1024 * 1024
MAX_FILES = 50000
MAX_JSON_BYTES = 16 * 1024 * 1024
CATALOG_FORMAT = 'oc2-art-catalog-v1'
BUNDLE_FORMAT = 'oc2-local-assets-bundle-v1'
BUNDLE_MANIFEST = 'bundle-manifest.json'
LIBRARY_FILES = {'library/catalog.json', 'library/index.html', 'library/style.css'}
GROUPS = [('ui','界面美术'),('skillIcons','技能图标'),('fonts','字体'),('textures','贴图'),
          ('models','模型'),('maps','地图'),('effects','特效'),('rendering','光影配置'),('indexes','资源清单')]
SOURCE_DIRS = {'ui','textures','models','maps','effects','rendering'}
SOURCE_SUFFIXES = {'.json','.png','.woff','.woff2'}
FONT_SAMPLE = '冒险者在微光试炼中施放火球术与冰霜爆破。0123456789'


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _tag():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]


def _json(raw):
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('JSON 清单过大')
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('JSON 包含重复键')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('JSON 包含非有限数值')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _safe_path(name):
    if (not isinstance(name,str) or not name or len(name)>1024 or name.startswith('/')
            or any(c in name for c in '\\:\x00%?#') or any(ord(c)<32 for c in name)
            or any(part in ('','.','..') for part in name.split('/'))):
        raise ValueError('不安全的资源相对路径')
    return name


def _allowed(name):
    _safe_path(name)
    if name in LIBRARY_FILES or name == 'manifest.json':
        return
    path = Path(name)
    if path.parts[0] not in SOURCE_DIRS or path.suffix.lower() not in SOURCE_SUFFIXES:
        raise ValueError('资源目录含不允许传输的文件：' + name)


def _canonical(name):
    return unicodedata.normalize('NFC',name).casefold()


def _converted(path, exists=True):
    root = Path(path).expanduser().absolute()
    if (root.name != 'converted' or root.parent.name != 'game-data'
            or root.is_symlink() or root.parent.is_symlink()):
        raise ValueError('路径必须是 game-data/converted，且不能是符号链接')
    root = root.resolve()
    if root.name != 'converted' or root.parent.name != 'game-data':
        raise ValueError('实际目标必须是 game-data/converted')
    if exists and not root.is_dir():
        raise ValueError('转换资源目录不存在')
    if root.exists() and not root.is_dir():
        raise ValueError('converted 必须是目录')
    return root


def _source_root(path):
    root=Path(path).expanduser().absolute()
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError('素材源目录不能是符号链接')
    if not root.is_dir():
        raise ValueError('转换资源目录不存在')
    return root.resolve()


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):
            digest.update(chunk);size += len(chunk)
    return size,digest.hexdigest()


def _files(root):
    result, canonical = [],set()
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs.sort();names=sorted(name for name in names if name!='.DS_Store' and not name.startswith('._'))
        for name in dirs + names:
            path = Path(base)/name
            if path.is_symlink():
                raise ValueError('素材目录不能包含符号链接')
        for name in names:
            path=Path(base)/name
            if not path.is_file():
                raise ValueError('素材目录只能包含普通文件')
            relative=path.relative_to(root).as_posix();_allowed(relative)
            key=_canonical(relative)
            if key in canonical:
                raise ValueError('资源路径存在大小写或 Unicode 冲突')
            canonical.add(key)
            size,digest=_hash_file(path)
            result.append({'path':relative,'bytes':size,'sha256':digest})
    if len(result)>MAX_FILES:
        raise ValueError('素材文件数量超过限制')
    return sorted(result,key=lambda item:item['path'])


def _asset_relative(url):
    if not isinstance(url,str) or not url.startswith('/assets/'):
        raise ValueError('清单资源 URL 必须以 /assets/ 开头')
    name=url[len('/assets/'):];_allowed(name)
    return name


def _formats(read):
    manifest=_json(read('manifest.json'))
    if not isinstance(manifest,dict) or not isinstance(manifest.get('format'),str) or not manifest['format']:
        raise ValueError('缺少网页资源清单版本')
    result={'web':manifest['format']}
    for key in ('effects','rendering','ui'):
        record=manifest.get(key)
        if not isinstance(record,dict) or not isinstance(record.get('format'),str) or not record['format']:
            raise ValueError('缺少资源版本：'+key)
        target=_asset_relative(record.get('url'))
        if Path(target).suffix!='.json':
            raise ValueError('版本清单引用必须是 JSON')
        profile=_json(read(target))
        if not isinstance(profile,dict) or profile.get('format')!=record['format']:
            raise ValueError('manifest 与实际资源版本不一致：'+key)
        result[key]=record['format']
    return result


def _brief(value,depth=0):
    if depth>3:
        return '…'
    if isinstance(value,str):
        return value[:1024] + ('…' if len(value)>1024 else '')
    if isinstance(value,dict):
        return {key:_brief(item,depth+1) for key,item in list(value.items())[:12]}
    if isinstance(value,list):
        return [_brief(item,depth+1) for item in value[:6]] + (['…'] if len(value)>6 else [])
    return value


def _references(root,records):
    refs=collections.defaultdict(list)
    def walk(value,profile,pointer='',context=None):
        if isinstance(value,dict):
            for key,item in value.items():
                walk(item,profile,pointer+'.'+key if pointer else key,value)
        elif isinstance(value,list):
            for index,item in enumerate(value):
                walk(item,profile,f'{pointer}[{index}]',context)
        elif isinstance(value,str) and value.startswith('/assets/'):
            name=_asset_relative(value)
            if name in LIBRARY_FILES:return
            details={key:_brief(item) for key,item in (context or {}).items()
                     if key.startswith('source') or key in ('family','label','glyphCount','chineseGlyphs','weight','mode','format')}
            refs[name].append({'profile':profile,'field':pointer,'details':details})
    for record in records:
        name=record['path']
        if name.endswith('.json') and name not in LIBRARY_FILES:
            walk(_json((root/name).read_bytes()),name)
    known={record['path'] for record in records}
    if set(refs)-known:
        raise ValueError('资源清单存在缺失的本地文件：'+sorted(set(refs)-known)[0])
    return refs


def _group(name):
    if name=='manifest.json':return 'indexes'
    path=Path(name)
    if path.suffix.lower() in ('.woff','.woff2'):return 'fonts'
    if name.startswith('ui/skill-'):return 'skillIcons'
    return 'ui' if path.parts[0]=='ui' else path.parts[0]


def _png_header_size(header):
    if (len(header)!=33 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[8:16]!=b'\0\0\0\rIHDR'
            or zlib.crc32(header[12:29])&0xffffffff!=struct.unpack('>I',header[29:33])[0]):
        raise ValueError('PNG 文件头或 IHDR 校验失败')
    width,height=struct.unpack('>II',header[16:24])
    if not 0<width<=16384 or not 0<height<=16384:
        raise ValueError('PNG 像素尺寸超过限制')
    return width,height


def _png_size(path):
    with path.open('rb') as handle:return _png_header_size(handle.read(33))


def _render(catalog):
    escape=lambda value:html.escape(str(value),quote=True)
    link=lambda name:'../'+quote(_safe_path(name),safe='/')
    css='''body{margin:0;background:#101b24;color:#e5e0d4;font:15px/1.6 system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:30px 22px}h1,h2{color:#edce85}a{color:#abdcef}nav{display:flex;flex-wrap:wrap;gap:16px;padding:12px 0 24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.card{min-width:0;padding:18px;background:#172b39;border:1px solid #4f6573;border-radius:6px}.card img{display:block;max-width:100%;height:160px;object-fit:contain;margin:0 auto 14px}.card h3{font-size:15px;overflow-wrap:anywhere}code,pre{font:11px/1.7 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}.meta{font-size:12px;color:#aebdc6}.font-preview{font-size:24px;padding:14px 0;color:#f3e5bb}.download{display:inline-block;padding:8px 0}section{margin-bottom:36px}.version{font-size:12px;color:#a8bbc8}footer{font-size:12px;border-top:1px solid #4f6573;padding-top:20px}'''
    fonts={entry['path']:index for index,entry in enumerate(catalog['entries']) if entry['category']=='fonts'}
    for name,index in fonts.items():
        css+=f'\n@font-face{{font-family:catalog-font-{index};src:url("{link(name)}");font-display:swap}}.font-{index}{{font-family:catalog-font-{index},sans-serif}}'
    output=['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>本地美术素材库</title><link rel="stylesheet" href="style.css"></head><body><main>',
            '<h1>本地美术素材库</h1><p>供本地复用与单独同步。原画、字体、模型和转换产物不随 GitHub 代码上传。</p>',
            '<p class="version">资源版本：'+escape(json.dumps(catalog['sourceFormats'],ensure_ascii=False))+'</p><nav>']
    for key,label in GROUPS:
        count=sum(entry['category']==key for entry in catalog['entries'])
        if count:output.append(f'<a href="#{key}">{label} · {count} 文件</a>')
    output.append('</nav>')
    for key,label in GROUPS:
        entries=[entry for entry in catalog['entries'] if entry['category']==key]
        if not entries:continue
        output.append(f'<section id="{key}"><h2>{label}</h2><div class="grid">')
        for entry in entries:
            name=entry['path'];url=link(name)
            output.append('<article class="card"><h3>'+escape(name)+'</h3>')
            if name.endswith('.png'):
                output.append(f'<a href="{url}"><img loading="lazy" src="{url}" alt="{escape(name)}"></a>')
            if key=='fonts':
                output.append(f'<p class="font-preview font-{fonts[name]}">{FONT_SAMPLE}</p>')
            dimensions=f" · {escape(entry['width'])}×{escape(entry['height'])} 像素" if 'width' in entry else ''
            output.append(f'<p class="meta">{entry["bytes"]:,} 字节{dimensions}</p><code>SHA256 {escape(entry["sha256"])}</code>')
            references=entry.get('references',[])[:8]
            if references:output.append(f'<details><summary>来源与用途 · {len(references)}</summary>')
            for reference in references:
                output.append('<p class="meta">用途：'+escape(reference['profile'])+' → '+escape(reference['field'])+'</p>')
                if reference.get('details'):
                    output.append('<pre>'+escape(json.dumps(reference['details'],ensure_ascii=False,indent=2))+'</pre>')
            if references:output.append('</details>')
            output.append(f'<a class="download" href="{url}" download>下载文件</a></article>')
        output.append('</div></section>')
    output.append('<footer>中文字体示例按文件加载，缺失字形可能由浏览器回退。目录只列转换产物；完整来源信息可下载对应 JSON 清单查看。</footer></main></body></html>')
    return '\n'.join(output).encode('utf-8'),css.encode('utf-8')


def build_catalog(converted=DEFAULT_CONVERTED):
    root=_source_root(converted)
    records=[entry for entry in _files(root) if entry['path'] not in LIBRARY_FILES]
    formats=_formats(lambda name:(root/name).read_bytes())
    refs=_references(root,records)
    entries=[]
    for record in records:
        entry={**record,'category':_group(record['path']),'references':refs.get(record['path'],[])}
        if record['path'].lower().endswith('.png'):
            entry['width'],entry['height']=_png_size(root/record['path'])
        entries.append(entry)
    catalog={'format':CATALOG_FORMAT,'createdAtUTC':_now(),'sourceFormats':formats,
             'fileCount':len(entries),'totalBytes':sum(entry['bytes'] for entry in entries),'entries':entries}
    markup,css=_render(catalog)
    directory=root/'library';directory.mkdir(exist_ok=True)
    (directory/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'index.html').write_bytes(markup);(directory/'style.css').write_bytes(css)
    return catalog


def _manifest_file(record):
    if not isinstance(record,dict) or set(record)!={'path','bytes','sha256'}:
        raise ValueError('传输文件记录字段无效')
    _allowed(record['path'])
    if (not isinstance(record['bytes'],int) or isinstance(record['bytes'],bool) or record['bytes']<0
            or not isinstance(record['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',record['sha256'])):
        raise ValueError('传输文件长度或哈希无效')


def _verify_open(archive,max_total_bytes):
    if not isinstance(max_total_bytes,int) or max_total_bytes<=0:
        raise ValueError('展开大小限制必须为正数')
    infos=archive.infolist()
    if len(infos)>MAX_FILES+1:
        raise ValueError('ZIP 文件数量超过限制')
    seen=set();members={};total=0
    for info in infos:
        if info.orig_filename!=info.filename:
            raise ValueError('ZIP 原始文件名含 NUL 或被截断')
        name=info.filename;_safe_path(name)
        canonical=_canonical(name)
        if canonical in seen:
            raise ValueError('ZIP 存在重复或冲突条目')
        seen.add(canonical)
        mode=stat.S_IFMT(info.external_attr>>16)
        if info.is_dir() or mode not in (0,stat.S_IFREG) or info.flag_bits&1:
            raise ValueError('ZIP 包含目录、符号链接、特殊文件或加密条目')
        if info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
            raise ValueError('ZIP 压缩方法不支持')
        if name!=BUNDLE_MANIFEST:
            if not name.startswith('converted/'):
                raise ValueError('ZIP 存在转换目录外的额外文件')
            _allowed(name[len('converted/'):])
        total+=info.file_size
        if total>max_total_bytes:
            raise ValueError('ZIP 展开大小超过限制')
        members[name]=info
    if BUNDLE_MANIFEST not in members or members[BUNDLE_MANIFEST].file_size>MAX_JSON_BYTES:
        raise ValueError('缺少有效的传输清单')
    manifest=_json(archive.read(members[BUNDLE_MANIFEST]))
    if not isinstance(manifest,dict) or manifest.get('format')!=BUNDLE_FORMAT:
        raise ValueError('传输包格式不支持')
    records=manifest.get('files')
    if not isinstance(records,list) or not 1<=len(records)<=MAX_FILES:
        raise ValueError('传输文件列表无效')
    expected={};canonical=set()
    for record in records:
        _manifest_file(record);name=record['path'];key=_canonical(name)
        if key in canonical:raise ValueError('传输清单有重复路径')
        canonical.add(key);expected[name]=record
    if set(members)!={BUNDLE_MANIFEST,*('converted/'+name for name in expected)}:
        raise ValueError('ZIP 含额外文件或缺失文件')
    if not LIBRARY_FILES|{'manifest.json'}<=set(expected):
        raise ValueError('传输包缺少资源目录或网页清单')
    if manifest.get('totalBytes')!=sum(record['bytes'] for record in records):
        raise ValueError('传输清单总长度不一致')
    for name,record in expected.items():
        info=members['converted/'+name]
        if info.file_size!=record['bytes']:
            raise ValueError('ZIP 声明长度不一致：'+name)
        digest=hashlib.sha256();size=0
        with archive.open(info) as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):
                size+=len(chunk);digest.update(chunk)
                if size>record['bytes']:raise ValueError('ZIP 实际展开长度超出清单')
        if size!=record['bytes'] or digest.hexdigest()!=record['sha256']:
            raise ValueError('资源哈希或长度校验失败：'+name)
    def read(name):
        _allowed(name)
        if name not in expected or expected[name]['bytes']>MAX_JSON_BYTES:
            raise ValueError('缺少或过大的资源版本清单')
        return archive.read(members['converted/'+name])
    if _formats(read)!=manifest.get('sourceFormats'):
        raise ValueError('传输清单与网页资源版本不一致')
    catalog=_json(read('library/catalog.json'))
    if not isinstance(catalog,dict) or catalog.get('format')!=CATALOG_FORMAT or catalog.get('sourceFormats')!=manifest['sourceFormats']:
        raise ValueError('美术目录格式或资源版本不一致')
    catalog_entries=catalog.get('entries')
    if not isinstance(catalog_entries,list) or len(catalog_entries)!=len(expected)-len(LIBRARY_FILES):
        raise ValueError('美术目录文件列表不一致')
    listed=set()
    for entry in catalog_entries:
        if not isinstance(entry,dict) or entry.get('path') not in expected:
            raise ValueError('美术目录路径不在传输清单')
        name=entry['path']
        if name in LIBRARY_FILES or name in listed or entry.get('category')!=_group(name):
            raise ValueError('美术目录存在重复条目或类别错误')
        listed.add(name)
        if any(entry.get(field)!=expected[name][field] for field in ('bytes','sha256')):
            raise ValueError('美术目录与传输文件哈希不一致')
        if name.lower().endswith('.png'):
            if any(not isinstance(entry.get(field),int) or isinstance(entry.get(field),bool)
                   or not 0<entry[field]<=16384 for field in ('width','height')):
                raise ValueError('美术目录像素尺寸必须是正整数')
            with archive.open(members['converted/'+name]) as handle:
                dimensions=_png_header_size(handle.read(33))
            if (entry['width'],entry['height'])!=dimensions:
                raise ValueError('美术目录与实际 PNG 尺寸不一致')
        elif 'width' in entry or 'height' in entry:
            raise ValueError('非 PNG 文件不能带像素尺寸')
    if catalog.get('fileCount')!=len(listed) or catalog.get('totalBytes')!=sum(expected[name]['bytes'] for name in listed):
        raise ValueError('美术目录总量不一致')
    markup,css=_render(catalog)
    if read('library/index.html')!=markup or read('library/style.css')!=css:
        raise ValueError('目录页面不是清单生成的无脚本版本')
    return manifest


def verify_bundle(bundle,max_total_bytes=MAX_UNPACKED_BYTES):
    """校验全部 ZIP 成员及资源版本，不向磁盘展开文件；成功返回传输清单。"""
    try:
        with zipfile.ZipFile(bundle,'r') as archive:
            return _verify_open(archive,max_total_bytes)
    except (zipfile.BadZipFile,KeyError,UnicodeError,TypeError) as error:
        raise ValueError('传输包无效或已损坏') from error


def export_bundle(converted=DEFAULT_CONVERTED,destination=None,max_total_bytes=MAX_UNPACKED_BYTES):
    """生成目录并打包整个匹配版本 converted；默认写同级 transfers/。"""
    root=_source_root(converted);catalog=build_catalog(root);records=_files(root)
    if sum(record['bytes'] for record in records)>max_total_bytes:
        raise ValueError('转换资源总量超过传输限制')
    filename='oc2-assets-'+_tag()+'.zip'
    target=Path(destination).expanduser().absolute() if destination else root.parent/'transfers'/filename
    if target.is_dir():target=target/filename
    if target.suffix.lower()!='.zip' or target.resolve().is_relative_to(root):
        raise ValueError('ZIP 输出必须在 converted 之外')
    if target.exists():raise FileExistsError('传输包已存在，不覆盖已有文件')
    target.parent.mkdir(parents=True,exist_ok=True)
    manifest={'format':BUNDLE_FORMAT,'createdAtUTC':_now(),'sourceFormats':catalog['sourceFormats'],
              'totalBytes':sum(record['bytes'] for record in records),'files':records}
    temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            archive.writestr(BUNDLE_MANIFEST,json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
            for record in records:
                path=root/record['path']
                if path.is_symlink():raise ValueError('导出期间资源被替换为符号链接')
                archive.write(path,'converted/'+record['path'])
        verify_bundle(temporary,max_total_bytes)
        # Link without replacement so a concurrently created destination survives.
        os.link(temporary,target);temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return {'path':str(target),'fileCount':len(records),'totalBytes':manifest['totalBytes'],
            'sha256':_hash_file(target)[1],'sourceFormats':manifest['sourceFormats']}


def import_bundle(bundle,target=DEFAULT_CONVERTED,max_total_bytes=MAX_UNPACKED_BYTES):
    """完整校验后同盘暂存并替换 converted，保留旧目录；失败时回滚。"""
    root=_converted(target,exists=False);backup=None;temporary=None
    try:
        with zipfile.ZipFile(bundle,'r') as archive:
            manifest=_verify_open(archive,max_total_bytes)
            root.parent.mkdir(parents=True,exist_ok=True)
            temporary=Path(tempfile.mkdtemp(prefix='.converted-import-',dir=root.parent))
            staged=temporary/'converted';staged.mkdir()
            for record in manifest['files']:
                destination=staged/record['path'];destination.parent.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256();size=0
                with archive.open('converted/'+record['path']) as source,destination.open('xb') as output:
                    for chunk in iter(lambda:source.read(1024*1024),b''):
                        size+=len(chunk)
                        if size>record['bytes']:raise ValueError('展开时资源长度改变')
                        digest.update(chunk);output.write(chunk)
                if size!=record['bytes'] or digest.hexdigest()!=record['sha256']:
                    raise ValueError('展开时资源哈希改变')
            # Every directory rename is atomic and stays on the target filesystem.
            # The old tree is retained before installing the new one.
            if root.exists():
                backup=root.with_name('converted.backup-'+_tag());os.replace(root,backup)
            try:
                os.replace(staged,root)
            except BaseException:
                if backup is not None and not root.exists():os.replace(backup,root)
                raise
        return {'target':str(root),'backup':str(backup) if backup else None,
                'fileCount':len(manifest['files']),'totalBytes':manifest['totalBytes'],
                'sourceFormats':manifest['sourceFormats']}
    except (zipfile.BadZipFile,KeyError,UnicodeError,TypeError) as error:
        raise ValueError('传输包无效或已损坏') from error
    finally:
        if temporary is not None:shutil.rmtree(temporary,ignore_errors=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True,title='操作')
    catalog=commands.add_parser('catalog',help='整理本地素材，生成可浏览目录')
    catalog.add_argument('--converted',type=Path,default=DEFAULT_CONVERTED,help='转换资源源目录；默认 game-data/converted')
    export=commands.add_parser('export',help='导出可校验的素材 ZIP，不包含存档')
    export.add_argument('--converted',type=Path,default=DEFAULT_CONVERTED,help='转换资源源目录；默认 game-data/converted')
    export.add_argument('--output',type=Path,help='ZIP 输出文件或已有目录；默认 game-data/transfers/')
    for name,description in [('verify','只校验素材 ZIP'),('import','校验并导入，旧 converted 自动备份')]:
        command=commands.add_parser(name,help=description)
        command.add_argument('bundle',type=Path,help='素材 ZIP 路径')
        command.add_argument('--max-mib',type=int,default=512,help='允许展开的总量上限 MiB，默认 512')
        if name=='import':command.add_argument('--target',type=Path,default=DEFAULT_CONVERTED,help='目标 game-data/converted 路径')
    args=parser.parse_args()
    try:
        if args.command=='catalog':
            result=build_catalog(args.converted)
            result={'catalog':str(args.converted/'library/index.html'),'fileCount':result['fileCount'],
                    'totalBytes':result['totalBytes'],'sourceFormats':result['sourceFormats']}
        elif args.command=='export':result=export_bundle(args.converted,args.output)
        elif args.command=='verify':
            result=verify_bundle(args.bundle,args.max_mib*1024*1024)
            result={'status':'校验通过','fileCount':len(result['files']),'totalBytes':result['totalBytes'],'sourceFormats':result['sourceFormats']}
        else:result=import_bundle(args.bundle,args.target,args.max_mib*1024*1024)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(1,'失败：'+str(error)+'\n')


if __name__=='__main__':main()
