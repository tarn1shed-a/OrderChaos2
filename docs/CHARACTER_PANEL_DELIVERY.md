# 原人物面板交付接线（2026-11-14）

冻结可见候选见 `CHARACTER_PANEL_CANDIDATE.md`。本批仅新增部署 overlay、追加打包工具和测试，不改此前冻结 8 文件、共享 `deploy/`、原 127 文件、地图接线或存档。

## 私有完整包

- 基底：`backups/deployment/oc2-runtime-four-inside-20261114.tar.gz`，SHA256 `a2b224a85878934e0003b46afaf79f78b8d70ff03f977b568b9ab37fb5ff1cf7`。
- 新包：`backups/deployment/oc2-runtime-character-panels-20261114.tar.gz`，SHA256 `f1dc28154f890f3e3eccd39e927130e51daa693f215d8cd0936bbc4c063d4569`，155,630,719 字节。
- 收据：同路径加 `.receipt.json`。包和收据均位于忽略目录。

2753 个基底成员全部逐字不变，包括原 127 文件、四室内模型/碰撞、原 native 输入和所有旧素材。仅追加 104 个成员：`game-data/converted/character-source/` 下101份原绘图/原图/清单，以及 `prototype/public/character-source-panels.mjs`、`character-source-state.mjs`、`character-source-panels.css`。新 manifest 有2857个文件和独立 `characterIntegration` 记录。

没有添加 standalone QA 模块、测试 HTML、新游戏入口、数据库或角色恢复文件。原技能/经验服务并未恢复，真实 `source` 恒为 `null`。

现有依赖保留原包字节：`prototype/public/source-ui-svg.js`、`game-data/converted/ui/{chineseText.woff,chineseDisplay.woff,leagueGothic.woff,igm-atlas-1.png,igm-atlas-8.png}`。对应 SHA 保存于收据。旧 source-entry 登录/人物选择素材未覆盖。

## 主任务唯一接点

`tools/preview/character-panel-runtime-overlay.mjs` 导出 `stageCharacterPanelsEntry`、`stageCharacterPanelsPlan` 和 `CHARACTER_PANEL_MANIFEST`。应在现有 `deploy/prepare_delivery.mjs` 的 `stageEntry(...,{entryUI})`、`stageInsideEntry` **之后**、生成 staged-entry 字节 **之前**，由主任务追加：

```js
import {
  stageCharacterPanelsEntry, stageCharacterPanelsPlan, CHARACTER_PANEL_MANIFEST,
} from '../tools/preview/character-panel-runtime-overlay.mjs';

// 现有 stageEntry / stageInsideEntry 之后：
if (files[CHARACTER_PANEL_MANIFEST]) {
  entrySource = stageCharacterPanelsEntry(entrySource);
}

// 现有 stagePlan / stageInsidePlan 得到最终计划后：
plans['/explore-map.js'] = stageCharacterPanelsPlan(plans['/explore-map.js']);
```

旧包没有此清单，不触发人物 overlay。新包未经过 `entryUI:true` 或四室内 stage 时，overlay 明确拒绝；同一 overlay 重复调用、缺失或重复任一替换锚点也拒绝。原 `stageEntry` 和原 `explore-map.js` 无须改动。现有公开文件清单自动映射 `prototype/public/` 与 `game-data/converted/`，已有 `.mjs/.css/.svg` 类型足够服务新增内容。

v2 计划适配只把 `/assets/character-source/` 下101份人物素材从 `critical` 移到 `background`，去重保留全部依赖供后台预取/打开时读取；`character-source-*.mjs` 与 `source-ui-svg.js` 导入保持 critical。没有这类 critical 资源时返回原计划对象。地图/secondary texture 的 critical 列表顺序与 `scope`（含地图窗口）不变，不改渲染驻留或任何地图计划数据。

v2 overlay 不在上述私有包内，故 `f1dc28…` 包及其收据不重打；包内 `overlaySHA256` 是 v1 构建时的审计记录。实际 v2 外置4文件 SHA 另存 `analysis/raw/character-progression-20261114/panel-delivery-batch5-v2/SHA256.json`，由根任务随部署代码整合。

### 预览回调

源接点：`deploy/attribute_preview.mjs` 的 `renderAttributePreview`，由 `deploy/stage_runtime.mjs` 中 `stageEntry` 注入的 `createAttributeUI` 初始化调用。新 overlay 只替换工厂名称并保留回调文本：

```js
preview: (role,size) => renderAttributePreview(
  THREE, renderer, sourcePreviewResources, modelFactories.get(modelTemplate),
  role, bakedLighting,
  {
    width:Math.floor(size.width*renderer.getPixelRatio()),
    height:Math.floor(size.height*renderer.getPixelRatio()),
  },
)
```

源模型、现有角色外观/装备、原灯光、像素比和预览窗口保持原参数。候选的 `preview` 签名直接兼容，不用新增人物模型或相机。

### 角色、菜单、关闭与输入

overlay 去掉旧 `createAttributeUI/createSkillBook` 的 import/初始化，建立单个 `characterPanels`，通过 `createCharacterPanelHandles` 保留现有 `attributeUI` / `skillBook` 句柄接口：

- `hud.character(data)` 后原有 `attributeUI.update(data)` 调用继续工作。句柄只读当前 `field-xp.value/max`，传入 `{source:null,trialProgress}`；退出角色时原有 `attributeUI.update(null)` 清空并关闭，不读取试玩总XP重新计算比例。
- `attributeUI.open()` 路由属性，`skillBook.open()` 路由当前职业技能；原 `field-skills` 菜单继续使用同一事件绑定。两句柄的 `isOpen` 仅对所属页面为真，现有门禁覆盖两页。
- 两句柄的 `close()` 均关闭共用 dialog，原任务/背包/热键/会话关闭路径继续有效；`openSession` 额外先关闭此 dialog。新 `beforeOpen` 只关闭其它窗口，避免取消自身打开。
- `C/K` 在原键盘 handler 内路由属性/技能；同键关闭当前页，异键切换。按住重复不反复开关；输入框、组合输入、修饰键、任务窗口、热键编辑和登录弹窗保留阻挡。没有额外注册游戏入口或改变攻击/移动/升级/存储路径。

## 复跑

```sh
.venv/bin/python tools/character_panel_delivery_tests.py \
  --package backups/deployment/oc2-runtime-character-panels-20261114.tar.gz -v
```

5 项全部通过：所有基底成员及原 native 输入不变；104追加文件和6个既有依赖闭合；实际 staged-entry 的唯一锚点/JS语法/原预览回调及真实生成的K/C处理器（显式DOM事件夹具）/角色更新与关闭；实际四室内计划的地图/secondary sampler关键依赖保持、101份人物素材后台移动/去重/不丢依赖/无素材时原样；完整归档每个成员、manifest和收据SHA。另已通过 Python 编译与 Node 语法检查。

需要重新构建时选择新的忽略路径，工具拒绝覆盖已有归档：

```sh
.venv/bin/python tools/character_panel_delivery.py \
  --output analysis/raw/character-progression-20261114/character-panels-recheck.tar.gz
```

本批没有运行生产或本地存档、没有部署。下一步由主任务在共享部署处追加上述接点后，使用完整包做 Linux/真实浏览器验收：原角色模型显示；职业目录与铭文；C/K及原菜单；切页/关窗和移动门禁；退出登录/刷新/换角色/双连接。通过前只称可交付候选，不能称整个人物系统已恢复。
