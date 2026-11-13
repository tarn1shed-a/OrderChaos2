"""Inventory source map definitions/assets without claiming maps are restored.

Full original index/table details are written only to ignored local output.
The public status document contains names, counts and explicit unfinished gates.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from map_loading_evidence import Sources, read_world_container
from resource_packs import DEFAULT_SOURCE, normalize_resource_name
from skill_attachments import decode_ftable
from terrain_convert import read_instances
from tutorial_map_geometry import ROOT, local_output

DEFAULT_PREVIEW = ROOT / 'analysis/raw/showcase-20261110/running-preview'
PREVIEW_MANIFEST = 'game-data/converted/source-temple-sampling/manifest.json'
GATES = ('原加载组合', '原位置与模型变换', '原材质与贴图', '原碰撞',
         '原动态对象与状态', '完整连续路线', '实际浏览器画面', '联机与存档保全')


def group_world_records(entries):
    groups = {}
    for entry in entries:
        name = normalize_resource_name(entry['path'])
        root = re.fullmatch(r'world/([^/]+)\.wld', name)
        child = re.fullmatch(r'world/([^/]+)/(.+)', name)
        if not root and not child:
            continue
        world = (root or child).group(1)
        row = groups.setdefault(world, {'records': [], 'paths': set()})
        row['records'].append(entry); row['paths'].add(name)
    result = {}
    for world, row in sorted(groups.items()):
        paths = sorted(row['paths'])
        terrain = [p for p in paths if re.fullmatch(
            r'world/' + re.escape(world) + r'/terrain/(-?\d+)_(-?\d+)\.trn', p)]
        counts = collections.Counter(Path(p).suffix for p in paths)
        result[world] = {'resourceRecordCount': len(row['records']),
                         'uniquePathCount': len(paths), 'filesBySuffix': dict(sorted(counts.items())),
                         'baseTerrainCount': len(terrain),
                         'otherTerrainCount': counts['.trn'] - len(terrain),
                         'paths': paths, 'records': row['records']}
    return result


def map_availability(row, lookup, groups):
    path = normalize_resource_name(row['file'])
    candidates = lookup.get(path, [])
    stem = Path(path).stem
    group = groups.get(stem)
    return {'file': path, 'containerCandidates': len(candidates),
            'containerPresent': len(candidates) == 1,
            'worldGroupPresent': group is not None,
            'worldGroup': stem if group is not None else None}


def read_collision_summary(config):
    cfg = json.loads(Path(config).read_text())
    path = Path(cfg['collision']); profile = json.loads(path.read_text())
    return {'configSHA256': hashlib.sha256(Path(config).read_bytes()).hexdigest(),
            'collisionSHA256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'instances': len(profile['instances']),
            'loadedShapeCount': sum(len(profile['sources'][r['sourcePHY']]['shapes'])
                                    for r in profile['instances']),
            'scope': 'file coverage only; not dynamic admission or continuous route acceptance'}


def preview_coverage(runtime):
    runtime = Path(runtime).resolve()
    if not runtime.is_relative_to(ROOT / 'analysis/raw'):
        raise ValueError('Inspection runtime must remain in ignored analysis/raw')
    manifest = runtime / PREVIEW_MANIFEST
    if not manifest.is_file():
        return {'available': False, 'reason': 'Reviewed preview manifest absent'}
    data = json.loads(manifest.read_text())
    name = data['mapWindow']['url']
    if not name.startswith('/assets/'):
        raise ValueError('Unexpected preview map asset path')
    file = (runtime / 'game-data/converted' / name.removeprefix('/assets/')).resolve()
    if not file.is_relative_to(runtime / 'game-data/converted'):
        raise ValueError('Preview map path escapes converted input')
    terrain = json.loads(file.read_text())
    return {'available': True, 'world': terrain['world'],
            'manifestSHA256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'terrainSHA256': hashlib.sha256(file.read_bytes()).hexdigest(),
            'terrainTiles': len(terrain['sourceTiles']),
            'sceneryModels': len(data.get('scenery', [])),
            'sceneryPlacements': sum(len(m['instances']) for m in data.get('scenery', [])),
            'allGatesPassed': False,
            'scope': 'Current locally reviewed preview inputs, not observed full source frame or whole-map acceptance'}


def inventory(source=DEFAULT_SOURCE, runtime=DEFAULT_PREVIEW, candidate_config=None):
    sources = Sources(source)
    entries = [e for records in sources.lookup.values() for e in records]
    groups = group_world_records(entries)
    maps = decode_ftable(sources.read('tables/map_info.tbl'), 'map_id')
    for world, row in groups.items():
        container = f'world/{world}.wld'
        try:
            row['container'] = read_world_container(sources.read(container))
        except ValueError as error:
            row['containerError'] = str(error)
        count = 0; models = set(); types = collections.Counter(); errors = []
        for path in row['paths']:
            if not path.endswith('.itm'):
                continue
            raw = sources.read(path)
            class Buffer:
                def read_bytes(self):
                    return raw
            try:
                placements = read_instances(Buffer())
                count += len(placements)
                models.update(p['model'] for p in placements)
                types.update(p['sourceType'] for p in placements)
            except (ValueError, IndexError) as error:
                errors.append({'path': path, 'reason': str(error)})
        row.update(decodedPlacementRows=count, uniquePlacementResources=len(models),
                   placementTypes=dict(sorted(types.items())), placementDecodeErrors=errors)
    preview = preview_coverage(runtime)
    definitions = []
    for row in maps['rows']:
        availability = map_availability(row, sources.lookup, groups)
        shown = preview.get('available') and availability['worldGroup'] == preview.get('world')
        definitions.append({'id': row['map_id'], 'name': row['name'],
                            **availability,
                            'status': '部分可预览' if shown else '未开始',
                            'gates': {gate: '未验收' for gate in GATES},
                            'routeVerified': False})
    report = {'format': 'oc2-map-restoration-inventory-v1',
              'definitions': definitions, 'assetGroups': groups,
              'mapTableVerification': maps['verification'],
              'sourceProofs': sources.proofs, 'preview': preview,
              'totals': {'archiveRecords': len(entries), 'mapDefinitions': len(definitions),
                         'worldAssetGroups': len(groups),
                         'definitionsWithContainer': sum(r['containerPresent'] for r in definitions),
                         'definitionsMissingContainer': sum(not r['containerPresent'] for r in definitions),
                         'wholeMapsAccepted': 0},
              'limits': ['Only the supplied APK/downloaded archive version is inventoried.',
                         'Map definitions do not prove corresponding level assets are present.',
                         'Counts/extraction/CPU fixtures do not pass any whole-map acceptance gate.',
                         'A zero count means absent from this supplied package, not absent from the original game.',
                         'Selection/test/PvP definitions are retained; playability is not inferred.']}
    if candidate_config is not None:
        report['tutorialCollisionCandidate'] = read_collision_summary(local_output(candidate_config))
    return report


def status_markdown(report):
    totals = report['totals']; groups = report['assetGroups']; preview = report['preview']
    lines = ['# 地图还原进度', '',
             '本清单对应目前收到的原 APK 与下载包。**整张地图已验收：0 张。** 阶段检查通过不等于地图完成。', '',
             f"原 `map_info` 有 **{totals['mapDefinitions']} 条地图定义**；当前包内实际有 **{totals['worldAssetGroups']} 套地图资源**，其余 **{totals['definitionsMissingContainer']} 条定义缺对应 `.wld`**。不能用自建场景补齐这些缺口。", '',
             '优先顺序：先使 Tutorial 支撑完整新手任务链；其余已取得资源排队。缺资源的地图先保留缺口，不假装已取得完整游戏资料。', '',
             f"## 已取得的 {len(groups)} 套资源", '',
             '| 原资源目录 | 地形文件（基本 / 其他变体） | 摆放文件 / 记录 | 遮罩 / 光照等 DAT | 当前状态 |',
             '| --- | ---: | ---: | ---: | --- |']
    for name in sorted(groups, key=lambda n: (n != 'tutorial', n)):
        g = groups[name]; c = g['filesBySuffix']
        state = '部分可预览，完整路线未验收' if name == preview.get('world') else '未开始，仅完成文件盘点'
        lines.append(f"| {name} | {c.get('.trn',0)}（{g['baseTerrainCount']} / {g['otherTerrainCount']}） | {c.get('.itm',0)} / {g['decodedPlacementRows']} | {c.get('.msk',0)} / {c.get('.dat',0)} | {state} |")
    if preview.get('available'):
        lines.extend(['', f"当前本地预览只有 `{preview['world']}`：输入包含 {preview['terrainTiles']} 块地形、{preview['sceneryModels']} 种场景模型和 {preview['sceneryPlacements']} 条摆放。这是输入覆盖数，**不是 1:1 完成度**。"])
    if 'tutorial' in groups:
        types = groups['tutorial']['placementTypes']
        lines.extend(['', f"Tutorial 原摆放按类型还有 {types.get(8,types.get('8',0))} 条场景特效记录和 {types.get(15,types.get('15',0))} 条室内大模型记录。当前 1258 条可见场景清单覆盖普通 type2；特效、室内模型分别核对，不能只凭总数全部追加或宣称覆盖完整。"])
    if 'tutorialCollisionCandidate' in report:
        c = report['tutorialCollisionCandidate']
        lines.extend(['', f"独立新手碰撞候选有 {c['instances']} 条摆放、{c['loadedShapeCount']} 个载入形状；原动态升降台仍未接成完整运行流程。地下末段往返通过，不能代表接取点到终点的连续全路线通过。"])
    lines.extend(['', '## 全部原地图定义', '',
                  '保留原表名字，未擅自补译或把测试场景当正式区域。资源列“缺”指本次收到的包没有对应世界文件。', '',
                  '| ID | 原表名称 | 资源 | 状态 | 当前缺口 |',
                  '| ---: | --- | --- | --- | --- |'])
    for row in report['definitions']:
        name = row['name'].replace('|', '\\|')
        gap = ('动态升降台、前半段和整条连续路线、完整画面验收' if row['status'] == '部分可预览'
               else '加载组合、变换、材质、碰撞、动态对象与路线均待核对' if row['containerPresent']
               else '缺对应地图资源；尚未开始还原')
        lines.append(f"| {row['id']} | {name} | {'有' if row['containerPresent'] else '缺'} | {row['status']} | {gap} |")
    lines.extend(['', '## 状态与整图验收门槛', '',
                  '- **未开始**：只有文件/表定义盘点，尚未恢复可运行场景。',
                  '- **取证中**：正在关联原文件和调用；没有把反编译、解包或 CPU 夹具算成地图还原。',
                  '- **部分可预览**：部分原内容已在预览中显示，仍有明确加载、材质、碰撞或动态缺口。',
                  '- **路线待验收**：相关原加载、变换、材质、碰撞、动态对象均已接好，等待整段实际连续行走及联机验收；当前没有地图达到此阶段。',
                  '- **已验收**：以下所有门槛都有与当前文件版本对应的证据和实际验收，才能使用此状态。', '',
                  '每张地图必须核对：原加载组合与活动区域；模型位置/旋转/缩放；材质、贴图和原显示条件；原碰撞及区块边界；动态对象的真实状态与更新；从入口贯穿目标的连续路线；实际浏览器画面；双连接、刷新和存档保全。原场景不允许行走的项目，必须先以原代码证明不适用，不能自行省略门槛。', '',
                  '当前没有一张地图满足全部门槛。原始索引、完整表格和证据只留忽略目录；本文件不包含游戏资源。自动续跑保持暂停，生产与已有存档不改。', ''])
    return '\n'.join(lines)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--runtime', type=Path, default=DEFAULT_PREVIEW)
    cli.add_argument('--candidate-config', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--status-document', type=Path)
    args = cli.parse_args(); output = local_output(args.output)
    if output.exists():
        cli.error('Preserve existing inventory; choose a fresh output')
    report = inventory(args.source, args.runtime, args.candidate_config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if args.status_document is not None:
        document = args.status_document.resolve()
        if document != ROOT / 'docs/MAP_RESTORATION_STATUS.md':
            cli.error('Only the requested summary document is supported')
        document.write_text(status_markdown(report))
    print(json.dumps(report['totals']))
