# 重返营地

本地多人网页原型，以及《混沌与秩序 2》Android 3.1.3a 客户端和资源格式的研究工具。

**仓库不包含游戏资源、原版源码、账号数据或数据库。** 网页客户端、协议、服务端与转换工具为本项目编写，不连接原游戏服务器。

本项目以学习为优先目标：资源逆向沿“线索 → 假设 → 字节/调用证据 → 实验验证”推进；框架开发沿“输入 → 网络 → 服务端规则 → 存档 → 画面”理解。先读 [学习路线](docs/LEARNING.md)，区分原程序的证据与我们新写的实现。

## 第一版可玩循环

进入营地，靠近野狼，按 **空格 / F** 或地图内攻击按钮。野狼被攻击后追击并反击；参与击杀且仍存活、在线的角色各获得 **30 经验、10 金币、1 张狼皮**。累计每 60 经验升一级并恢复生命。野狼 8 秒后重新出现，倒下的玩家 4 秒后在出生点恢复。

二维营地和三维试炼都可完成此循环。服务器决定距离、冷却、伤害和奖励；客户端仅发送攻击目标，不计算掉落。

使用同一浏览器、同一服务器网址，输入原来的角色名，可恢复角色。服务器将进度写入被忽略的 `runtime/characters.json`，浏览器另存恢复凭据。离开、刷新或正常重启服务器后可以继续；不同名字是独立角色，同一角色不能同时登录两个窗口。

## 快速开始

需要 Node.js 22.13+、pnpm 11.25.0。仓库的 `.nvmrc` 和 `prototype/package.json` 声明了运行版本。

```sh
cd prototype
pnpm install --frozen-lockfile
pnpm start
```

打开 <http://localhost:8787>，两个浏览器窗口使用不同名字、相同营地编号即可测试同图移动。二维营地使用自制场景，克隆代码后无需另备资源即可运行。

安装依赖后，Mac 上也可以双击根目录的 `start.command`。端口和监听地址可通过根目录 `.env` 配置，模板见 [.env.example](.env.example)。

## 三维资源实验场

另行准备 `game-data/converted/` 后，打开 <http://localhost:8787/explore.html>。**只克隆 GitHub 仓库不会得到此目录**，资源未准备时页面会明确提示加载失败。

目前已验证的新手区域为 3×3 地块、192×192 世界单位，含 39 个场景摆放。森林精灵角色已接入恢复的骨骼、蒙皮与原始精灵行走/待机片段；狼、熊及人类男性基体仍使用静态源网格。

- WASD / 方向键移动，点击地面直线前进。
- 三维场景可右键拖动旋转镜头、滚轮缩放；窄屏提供触屏方向键。
- 每房间最多 8 人，服务端同步移动；二维、三维使用独立房间空间。
- 当前有基础战斗、奖励、等级和本地角色存档，尚无任务、完整账号系统和装备。
- 房间与怪物是临时状态；服务器重启后怪物重置，角色进度与分场景位置保留。
- 三维角色按服务器位置变化切换行走/待机，其他玩家也能看见；每个角色独立维护骨架与动作。原始片段已按目标骨架适配，不是用整体摆动代替关节动作。
- 攻击仍使用位移/闪光反馈；装备、原版混合地表材质和建筑碰撞尚未恢复，可穿过场景物件。

资源单独复制到另一台 Mac、首次安装和局域网联机步骤见 [本地服务器指南](docs/LOCAL_SERVER.md)。服务器只开放转换后的资源，不开放原始导出目录或数据库。

## 目录

```text
prototype/              网页、Node 服务端、锁文件与自动测试
  game/                 角色存档层与服务端战斗规则
  public/               二维与三维客户端、自制占位场景
  test/                 WebSocket 联机与地形采样测试
tools/                  只读 APK 分析、解包、模型/地形/贴图转换工具
docs/                   GitHub 与本地服务器说明
analysis/               格式研究文字和验证结论
.github/workflows/      不依赖游戏素材的源码检查
start.command           Mac 启动入口
.env.example            可提交的配置模板
```

以下目录只在本地存在，均不上传：

```text
game-data/
  com.gameloft.android.ANMP.GloftO2HM/files/  用户提供的原始导出
  extracted/                               校验后按需解包
  converted/                               网页所需 JSON / PNG
analysis/raw/                              完整反汇编、索引、验证输出
.venv/                                     Python 环境
runtime/                                   本地服务器角色存档，不随 Git 更新
```

## 检查代码

```sh
cd prototype
pnpm test
```

Python 工具建议使用 Python 3.12：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/requirements-resources.txt
.venv/bin/python tools/resource_tests.py
.venv/bin/python tools/bdae_tests.py
.venv/bin/python tools/bdae_skin_tests.py
.venv/bin/python tools/bdae_animation_tests.py
```

基础资源和动画格式测试包含自制数据，无需游戏文件；原始模型/动画集成测试在缺少本地素材时明确跳过。GitHub Actions 运行这些 Python 检查及 Node 联机、角色动画测试，不上传或下载游戏资源。

## 本地研究与转换

已获得对应本地文件时，可按需运行：

```sh
# 原始下载文件放在 game-data/com.gameloft.android.ANMP.GloftO2HM/files/
# 先只读检查一个资源条目的偏移、解压和 CRC
.venv/bin/python tools/inspect_resource_entry.py

.venv/bin/python tools/build_resource_preview.py
.venv/bin/python tools/verify_resource_preview.py
.venv/bin/python tools/terrain_convert.py --validate-all

# APK 分析额外依赖 Androguard
.venv/bin/python -m pip install -r tools/requirements-analysis.txt
.venv/bin/python tools/analyze_apk.py /path/to/game.apk

# 已确认构建的 ARM64 原生资源读取函数：静态反汇编，不执行 APK
.venv/bin/python -m pip install -r tools/requirements-native.txt
.venv/bin/python tools/analyze_native_resources.py /path/to/game.apk
```

转换入口校验原始配套索引，使用恢复的名称查找规则提取当前样例必需的 57 个源文件（包括原动画与其骨架参考模型），生成 20 个模型、23 张 PNG 和一块地图。原始包不修改，生成文件保存在被忽略的本地目录。更新到骨骼动画版本后需重新运行构建器，或单独复制匹配版本的转换产物。

## 文档与当前验证

- [上传 GitHub 的约定](docs/GITHUB.md)
- [学习路线：资源逆向证据与框架数据流](docs/LEARNING.md)
- [另一台 Mac 的安装与资源迁移](docs/LOCAL_SERVER.md)
- [APK 资源加载分析](analysis/APK资源加载分析.md)
- [资源解包与网页接入结果](analysis/资源解包与网页接入.md)
- [Vercel 架构调研与准备](analysis/Vercel部署准备.md)（当前以本地开服为主，尚未部署）

测试覆盖联机、服务端攻击判定、协作奖励、角色身份、重启恢复、损坏存档和写盘失败处理。三维实测两位角色共同击杀后各获奖励；真实重启本地服务后，角色经验、金币、狼皮和位置成功恢复。尚未在朋友的 Mac Pro、两台物理设备或跨公网环境验证。

当前没有附加代码许可证；仓库公开或代码再分发前需另行确定。第三方依赖和研究参考保留各自的许可与归属，原作资源不随仓库提供。
