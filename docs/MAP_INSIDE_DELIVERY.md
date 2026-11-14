# 新手地图室内主体：独立发布接线

这是四份原 type15 主模型与对应碰撞的有界阶段，不是完整地图完成。原升降台活动输入、缺失的附属模型、一处原遮罩和完整任务路线仍有缺口。

`tools/map_runtime_inside_delivery.py` 只读已固定私有包和已验收候选，生成新私有包；不改原 127 个审定文件，不复制角色存档。新内容是四主体、原节点/TRS/材质、四原 PHY、1044 条碰撞实例，以及材质适配模块。旧 1258 条可见摆放、1040 条碰撞实例和其原文件保持。

原碰撞使用 `nativeArchiveStream:true`，由已有 worker 选择原 stream 读取实现。第四 PHY 原文件尾错误仍保留其前 11 条完整形状；不改原文件头或补造第 12 条。包不启动升降台，也不添加地板、坡道、传送或出生点。

## 本地检查

```
.venv/bin/python tools/map_runtime_inside_delivery_tests.py
.venv/bin/python tools/map_runtime_inside_delivery.py --output backups/NEW-INSIDE-DELTA.tar.gz
.venv/bin/python tools/map_runtime_inside_delivery.py --complete --output backups/deployment/NEW-INSIDE-RUNTIME.tar.gz
```

测试核对审定文件不变、旧碰撞完整保留、仅四份原 PHY 增加、可移植路径、部署入口六个接点，以及分阶段加载不会漏掉第二层纹理/遮罩。完整包还需要父任务的 Linux/服务部署验收，不以打包检查冒称云端已更新。

## 部署适配接点

`tools/preview/map-runtime-inside-overlay.mjs` 只处理根部署层已经生成的入口。先调用现有 `stageEntry`，之后调用新 `stageInsideEntry`，不要先改审定源再交给固定 SHA 检查。

在部署准备层发现 `/assets/source-tutorial-inside/manifest.json` 时：

1. 把 `tools/preview/map-runtime-inside-overlay.mjs` 加入构建上下文，由 `deploy/prepare_delivery.mjs` 直接导入；`.dockerignore` 只为这一模块开例外。原 `source-inside-models.js` 已在私有包的 public 文件清单内，无须暴露原 BDAE/PHY。
2. `stageInsideEntry(stageEntry(originalSource,{entryUI}))` 替代单独的 `stageEntry` 返回值。新函数严格检查唯一锚点；不匹配即中止，不靠模糊替换。
3. `await stageInsidePlan(stagePlan,texts,closure)` 替代单独 `stagePlan(texts,closure)`。它继续使用现有准备窗口和分阶段调度，只切换本阶段 manifest 并保留原第二贴图依赖。没有候选 manifest 时仍走原流程。
4. 其余地图范围/原材质/光照/存档设置保持。`stageTrialWorld` 所用旧地形范围与新 manifest 相同，不改出生位置。

新函数不会把 type15 当 type2 改写；当前只显示原文件存在的第一份主体。原完整内部可见状态尚未接回，缺失 `*_inside.bdae` 不复制伪造。缺失 `hum_portal005.tga` 的一个原部件仍明确不绘制，不借用 `_01`。

## 已实际验收与剩余范围

父任务已在独立当前正式入口实机看见新增墙面、地板、门洞和楼梯，双连接实际行走 386.49 水平距离、刷新精确恢复，浏览器 0 warning/error。范围包括下层房间的绕障碍和台阶；升降台未通过，因此不能称整条原任务路线验收。

发布前另用完整私有包在 Linux amd64、2 CPU / 1 GiB 的隔离容器复核：双连接、原碰撞移动、位置与装备同步、私有路径拒绝、重启后的角色/装备/背包/位置恢复通过。当前正式入口的测试角色在原室内已核查坐标实际前后/横向行走，材质正常，浏览器无 warning/error。测试坐标只写独立容器的验收角色，不改变用户本地或线上角色。

本阶段可发布范围：162 模型 / 1262 摆放、1044 碰撞实例 / 2827 形状；相对于旧包仅加四个 type15 主体及对应原 PHY。私有发布包 SHA256 为 `a2b224a85878934e0003b46afaf79f78b8d70ff03f977b568b9ab37fb5ff1cf7`，2753 文件、53 个 Python 宿主，未包含角色存档。升降台研究完成的片段不等于已接到正式网页；完整活动状态、自动运行与整条任务路线继续待恢复。实际云端版本与存档核对以私有发布收据为准。

原资料、完整清单、截图和私有包的哈希收据均留在忽略目录 `analysis/raw/map-specialist-20261114/`、`analysis/raw/integration-20261114/` 和 `backups/`。只将工具、测试与这份接线说明纳入 Git。
