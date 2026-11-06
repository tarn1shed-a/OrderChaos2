# 重返营地

本地多人网页原型，以及《混沌与秩序 2》Android 3.1.3a 客户端和资源格式的研究工具。

**仓库不包含游戏资源、原版源码、账号数据或数据库。** 网页客户端、协议、服务端与转换工具为本项目编写，不连接原游戏服务器。

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

目前已验证的新手区域为 3×3 地块、192×192 世界单位，含 39 个场景摆放。森林精灵 NPC、狼和熊使用本地解析的静态源网格与贴图；人类男性基体也已转换。

- WASD / 方向键移动，点击地面直线前进。
- 三维场景可右键拖动旋转镜头、滚轮缩放；窄屏提供触屏方向键。
- 每房间最多 8 人，服务端同步移动；二维、三维使用独立房间空间。
- 当前无战斗、任务、账号或持久化存档。重启清空房间，重连以新身份回到出生点。
- 三维角色仍是静态姿势；骨骼动画、装备、原版混合地表材质和建筑碰撞尚未恢复，可穿过场景物件。

资源单独复制到另一台 Mac、首次安装和局域网联机步骤见 [本地服务器指南](docs/LOCAL_SERVER.md)。服务器只开放转换后的资源，不开放原始导出目录或数据库。

## 目录

```text
prototype/              网页、Node 服务端、锁文件与自动测试
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
```

基础资源工具测试使用自制数据，无需游戏文件；模型集成测试在缺少本地素材时明确跳过。GitHub Actions 运行这两组 Python 检查及 Node 联机测试，不上传或下载游戏资源。

## 本地研究与转换

已获得对应本地文件时，可按需运行：

```sh
# 原始下载文件放在 game-data/com.gameloft.android.ANMP.GloftO2HM/files/
.venv/bin/python tools/build_resource_preview.py
.venv/bin/python tools/verify_resource_preview.py
.venv/bin/python tools/terrain_convert.py --validate-all

# APK 分析额外依赖 Androguard
.venv/bin/python -m pip install -r tools/requirements-analysis.txt
.venv/bin/python tools/analyze_apk.py /path/to/game.apk
```

转换入口按需校验和提取 15,119 个文件；当前样例生成 20 个模型、23 张 PNG 和一块地图。原始包不修改，生成文件保存在被忽略的本地目录。

## 文档与当前验证

- [上传 GitHub 的约定](docs/GITHUB.md)
- [另一台 Mac 的安装与资源迁移](docs/LOCAL_SERVER.md)
- [APK 资源加载分析](analysis/APK资源加载分析.md)
- [资源解包与网页接入结果](analysis/资源解包与网页接入.md)
- [Vercel 架构调研与准备](analysis/Vercel部署准备.md)（当前以本地开服为主，尚未部署）

已通过 6 项 Node 联机/地形测试、3 项资源工具测试、5 项本地模型集成测试；三维样例已在两个独立浏览器会话中验证。尚未在朋友的 Mac Pro、两台物理设备或跨公网环境验证。

当前没有附加代码许可证；仓库公开或代码再分发前需另行确定。第三方依赖和研究参考保留各自的许可与归属，原作资源不随仓库提供。
