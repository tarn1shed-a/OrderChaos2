# 新手脚本：原容器与扫描覆盖审计

本批只检查“前一轮究竟扫到了什么，哪些原格式还没有展开”。没有恢复任务脚本正文，没有修改任务规则、地图、角色、存档或线上服务，也没有重新扫描全部 39,665 份文件正文。本文已按原优化 ABC 的 tag300 修正为 v2；v1 报告、原文和原工具副本均保留私有，不覆盖旧证据。

## 已确认的覆盖范围

`tools/resource_packs.py::index` 只遍历导出 `files/` 顶层的 `*.bin`，并要求头为 `GBMP`。本批重新核对目录元数据，得到 41 包、40,979 条记录，其中 39,665 文件、1,314 目录。这与冻结的全量正文扫描范围一致，没有发现一个已经在该目录中、但被这个条件遗漏的 GBMP 包。

原 `*_i.bin` 是索引，不是另一份正文包。27 份实际索引共 35,924 条，所有字段与 GBMP 本地头逐条一致；另 14 包没有这份旁置索引，当前读取器已经从其本地记录得到内容，没有因此漏掉包。这一步只校验索引，不把未重读的所有正文再报成一次 CRC 全检。

原 ARM64 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。已有原加载证据：

- `54cabc` 读取旁置索引及本地目录；`54c604` 按规范化名字查找。
- `54da70` 是实际条目解压消费者；已核方法 0、8、14 的读取器仍按原长度和 CRC 校验。
- `54bc84` 先查已缓存名字，再按原容器列表查找，最后在相应开关下走 `1270178` 的外部文件流。它没有证明当前导出已经包含 Android 上的全部挂载路径。

冻结的旧扫描可复用：`analysis/raw/tutorial-quest-mvp-20261114/script-content-inventory.json`。原 APK 的 863 个 ZIP 成员、138,885,748 字节及 CRC 已在 `analysis/raw/tutorial-mainline-script-consumers-20261115/apk-script-scan-v1.json` 留证，本批没有重跑该全文扫描。APK 成员表没有额外 ZIP/OBB/Lua 文件；“外部 OBB”不在 APK 成员扫描范围内。

## 本批实际展开的新候选

### UI 的内部压缩

420 份原 SWF 中，415 为 `FWS`、5 为 `CWS`。先前 GBMP 全文扫描检查的是 SWF 原字节，确实没有展开这 5 份内部 zlib。

本批只在 `CWS` 真正文件头出现时展开，验证 zlib 校验、完整结束、无尾随数据及 SWF 声明长度；外层 GBMP 的长度、CRC 同样通过。5 份为 AgeGating、CharacterChooseClass、CharacterChoosePart、CharacterChooseRace、SelectServer。

v1 只数标准 Action/DoABC 标签，统计为 8 份，**不能当作全部有 ActionScript 的文件**。本项目真实优化 ABC 在 tag300，`tools/optimized_abc.py` 已有该原格式读取器。v2 补核后：419 份 SWF 含已识别动作/ABC 标签，其中 8 份含标准标签、411 份含 tag300。tag300 共 1,775 块；现有 ABC 46.16 常量池读取器全部成功，字符串和多名池也无上述 6 个目标名命中。这是常量池核对，不是完整方法语义或原脚本执行；未解析的方法长度仍保留。本批没有执行或替写这些界面脚本。

展开后的 ASCII、UTF-16LE、UTF-16BE 中，没有找到 `tutorial_quest202`、`tutorial_npc972_ai`、`tutorial_obj188_trigger`、`tutorial_obj190_khalin_hammer`、`Skill240_OnSkillHit`、`Skill228_OnSkillHit`。这只排除了这组明确名字在该展开内容中的字面命中，不能证明它们没有混淆或其他无名称调用。

### 本地设置文件

`LocalConfig.cnfg` 的真实格式入口为完整的 `%sLocalConfig.cnfg`，不是文件名后缀。Ghidra 的后缀无 xref 不能当成“没人读取”。

原读者 `a7a430` 固定读 `0x4000` 字节，以 8 字节步长调用 `a7a978`，解后按 `key value\n` 放入设置 map；原写者 `a7aaf4` 反向调用 `a7ad64`。

本批实际执行这两个原块函数，使用原调用者的 16 轮、字节序标志及原常量输入。解码结果在第一个 NUL 前只有 45 字节、3 条设置；原函数回编码后与 16,384 字节源文件逐字节相同，没有上述 6 个名字。配置值和解码文件仅留忽略目录，不打印进文档、界面或 GitHub。没有把此解码器尝试应用到别的未知文件。

另单独检查 8 份实际散装文本输入：两个 Controller XML、DLC 两份 JSON、SNS JSON、预载贴图清单、下载日志及音频 `project_info.json`。这些不在 GBMP 正文扫描里，原字节中也没有上述 6 个名字。音频 JSON 的说明文本有旧式非 UTF-8 字节；本批按原字节检查，没有强制换编码后冒称恢复脚本。

### 音频归档

原 `38ab74 → 3865b0` 设置音频文件系统，`386774 → 157d8f0/157db38/157e46c` 加载 setup 和 Initial_soundpack。原 stdio 音频文件系统工厂 `1587a40` 的虚表实际指向 `1583520 → 1583b20 → 15c0418` 的归档加载路径。`15c0ffc` 逐字节核对 `Voxarch1`；`15c0418` 读取 128 字节头及原目录。

导出中真实存在的两份归档已展开目录：

| 文件 | 原成员数 | 本批核对 |
| --- | ---: | --- |
| `sound2/setup.voxpack` | 1 | 原 `.voxdata` 描述数据 |
| `sound2/Initial_soundpack.voxpack` | 1,525 | wav/mpc/vxn/vxa/vgs/fxb/voxdata |

两套目录及名字索引完全一致；所有名字、载荷范围合法。随后实际执行原 `15c0d54` 名字哈希查找和 `15c0e88` 范围获取：全部 1,526 个名字返回正确原序号、偏移和长度；原头检查拒绝坏 magic/短头，原查找拒绝不存在的名字。

在这些成员原载荷中检查上述 6 个名字仍无命中。音频编码没有冒充任务脚本 VM；没有解码 MPC/VoxN 音频，也没有声称负结果排除了未知编码中的正文。`Voxarch1` 尚未核清的校验字段不标为 CRC 已验证；本批可核对的是源 SHA、原目录查找及长度范围。`oc2_gss.vgs` 为 JSON 形式的音频数据，其原请求 `1573518` 来自同一音频初始化链，而不是已证任务脚本入口。

## 安装清单与外部容器

导出下载日志有 542 项，按原 `.split_` 后缀合并为 85 个基本文件。原 Dalvik `DownloadComponent` 将分片尾号解析后去掉后缀，并以合并文件打开；不能因为没有保留 542 个独立分片就认定资源缺失。

日志中的 sound2 和字体目录拼接有不同写法：本批保留字面路径，并单独与导出中的 `sound2/`、`ui/Font/` 做明确对照，85 组都有对应实际文件。这是导出路径比较，不是新建运行时路径规则，也不是对已合并文件的原下载校验。

原 `DLC_Info.json` 有 17 组、267 个不同文件标识；`DLC_UniversalPack.json` 有 3 组、26 标识。原 `7c1478 → 7c2144` 实际消费这些 JSON。新手 `tutorial.wld` 对应 DLC10，其 `files=[]`；selection 与 dawnwatch 在 DLC9，也为 `files=[]`。不能把其他可选地图的 DLC 文件缺失说成新手任务脚本包尚未下载。

另有真实的原外部入口：`3865b0` 请求 `main.31320.com.gameloft.android.ANMP.GloftO2HM.obb`，之后设置 `/sound2/` 路径。原 Java 安装器也单独设置 `/Android/obb/<package>/`，不同于 `files/`。当前用户提供的目录只有 `files/`，里面没有 OBB；这证明扫描边界，不证明本次运行一定成功挂载过该 OBB，更不证明它包含任务正文。不能直接据此要求重新下载整个游戏。

## 尚未排除、下一步要有的依据

1. `InitialFeed.dat`：原 `8e3864` 将其原字节作为 initial-data 送入 `ed1aac`，后者有 CrmManager 初始化消费。编码未闭合，不能按文件名排除内容。若继续，先追这个明确消费者的解码/解析调用，不试猜密钥或 XOR。
2. `OF_PP.bin`：156 字节，非 GBMP；原 ARM64 及现有 Dalvik 导出尚未找到完整文件名生产者。字符外观不是 Base64 解码授权依据，暂保留原字节与缺口。
3. 原 BDAE 的真实 ZIP 外壳已在后续有界批完成目录核对，见 `docs/TUTORIAL_SCRIPT_BDAE.md`：10,224 条外层、34,579 内层成员全部核完，内层均直接存放；额外成员只有空元数据和缩略图文件名，没有独立任务脚本或二次 ZIP 容器。没有扩成普通模型正文全文重搜，BRES 未知数据字段仍保留边界。
4. Android 内部 `getFilesDir`、外部 OBB、未导出的其他挂载目录仍没有实际现场目录清单。需出现目录或原安装/挂载日志，才有可验的新文件；不能把缺现场变成“脚本必定只在服务器”的证明。
5. `file.map` 完整字符串为 `%s/file.map`，原 `141cf60` 的提示明确说明 shader pak。它是着色器文件映射入口，不能借这个名字假设存在任务脚本归档。

## 复跑与边界

```sh
.venv/bin/python tools/tutorial_script_archive_audit.py
.venv/bin/python tools/tutorial_script_archive_tests.py
```

v2 本地 13 项检查通过；另在没有原资料和私有报告的临时公开文件树中实际复跑，7 项源格式边界运行、6 项私有用例明确跳过，未造报告或声称跳过项已通过。原函数执行、展开记录、SHA 和目录内容在 `analysis/raw/tutorial-script-archive-20261115/v2/`；v1 原结果仍在父目录，旧源副本在 `v1-public-source/`。没有完整 Android 运行、服务器消息、浏览器或 GPU 验收，因为本批没有改任何游戏运行内容；不能把取证测试数量称为任务链已经恢复或地图完成。
