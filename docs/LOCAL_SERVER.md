# 首次安装与迁移到另一台 Mac

## 安装与启动

1. 安装适合这台 Mac 芯片架构的 Node.js 22.13+ 和 pnpm 11.25.0。
2. 克隆代码后，进入仓库根目录。
3. 安装依赖：

   ```sh
   cd prototype
   pnpm install --frozen-lockfile
   pnpm start
   ```

4. 打开 `http://localhost:8787`；使用不同名字、相同房间号测试双人移动。

之后可以双击根目录的 `start.command`。首次运行仍需先安装依赖。`NODE_BIN` 环境变量可指定 Node 可执行文件；默认使用 PATH 中的 Node。本机 Codex 的用户目录 runtime 仅为可选回退，不会复制到朋友的电脑。

若需要配置端口，将根目录 `.env.example` 复制为 `.env`，修改 `HOST` / `PORT` 后重启。两种标准启动方式都会读取根目录 `.env`。只运行 `node prototype/server.mjs` 时，需要自行通过 shell 设置环境变量。

## 资源单独传输

GitHub 仓库不含任何游戏资源。二维营地无需资源即可使用；三维实验场需要额外准备转换产物。

最小三维运行文件：将开发机的整个 `game-data/converted/` 文件夹复制到目标机器同一路径，保留子目录和文件名：

```text
仓库根目录/
├── prototype/
└── game-data/
    └── converted/
        ├── manifest.json
        ├── maps/
        ├── models/
        ├── effects/
        ├── rendering/
        ├── ui/
        ├── library/
        └── textures/
```

资源到位后打开 `http://localhost:8787/explore.html`。不需要把 APK、原始 960 MiB 数据包、解包目录或逆向环境传到服务器，仅运行网页所需的转换产物约 27 MB（含完整中文字体，随转换内容变化）。

如需在目标机器重新研究或转换，才需要另传原始导出目录 `game-data/com.gameloft.android.ANMP.GloftO2HM/files/`，并安装 Python 3.12、创建 `.venv`、安装 `tools/requirements-resources.txt` 后运行 `tools/build_resource_preview.py`。

开发机还可运行 `python3 tools/art_library.py export`，将完整转换资源整理为独立 ZIP，默认保存在 `game-data/transfers/`。目标机拉取相同版本代码、停止服务后，运行 `python3 tools/art_library.py verify /path/to/oc2-assets.zip`，再运行 `python3 tools/art_library.py import /path/to/oc2-assets.zip`。该工具仅需 Python 标准库；实际文件名以导出结果为准。校验失败不会替换现有资源；成功时旧 `converted/` 自动留为同目录下的 `converted.backup-…`，不会读写角色存档。完成后重新启动服务、刷新浏览器。

素材库入口为 `http://localhost:8787/assets/library/index.html`，也可从三维页“资源与玩法”打开。分类目录含原图、字体示例、资源用途/来源、像素尺寸与校验信息，方便另一个网页项目按相对路径复用。不要只拷某几个图标或字体文件；整套 ZIP 与代码匹配后再更新正式服。

## 朋友连接服务器

同一局域网：朋友使用服务器 Mac 的局域网 IP，例如 `http://192.168.1.20:8787`。不要发送 `localhost`。默认监听 `0.0.0.0`，主机需要允许该端口的本地网络访问。

不同网络：需要另行设置虚拟局域网、穿透或公网部署；本项目尚未配置这些服务。服务器运行期间保持 Mac 开机、服务不退出并避免休眠。

## 更新与数据

更新时先停止服务，拉取匹配版本的代码、更新依赖，并另行同步对应版本的 `converted/`，然后启动。不要同步正在变化的整个工作目录，也不要复制 `node_modules/` 或 `.venv/`；Intel 与 Apple Silicon 机器应各自安装依赖。

技能特效版本需要匹配的 `converted/models/forest-elf.json`、`wolf.json`、`effects/combat.json`、新增特效贴图与 `manifest.json`，请整体复制本次构建的 `converted/`。只有旧资源时，三维页会明确要求重建；在拥有原始包的开发机执行 `.venv/bin/python tools/build_resource_preview.py` 即可，再把产物单独传给正式服。更新代码与资源后重启服务，让战斗消息和快照包含技能与动作时间。角色存档不随资源重建改变；待结算施法、技能冷却和怪物减速为当前会话/房间状态，不写入角色存档。

当前要求 `oc2-combat-effects-v3` 与 `oc2-original-ui-v4`，包括 `rendering/`、原 LUT、`ui/profile.json`、`ui/hud.json`、`ui/portraits.json`、`ui/inventory.json`、`ui/item-icons.json`、9 张基础 UI 裁片、13 张 HUD 裁片、14 张背包/装备裁片、2 张技能图标、4 张物品图标、4 个 WOFF。请完整同步 `converted/`，旧版清单会明确要求重建。原材质库、源表和松散 TTF 只由开发机转换时读取；运行机器只需转换产物，无须 BDAE、SWF、APK 或反汇编。头像和装备全身预览在浏览器中由原模型渲染并缓存，无需另传截图。源字体覆盖常用中文，未覆盖的稀有字仍回退系统字体。

这次背包功能将角色存档升至 **version 2**。读取旧版时先验证全文件；首次落盘前，在同一个 `runtime/` 留下原字节的 `characters.json.v1-backup-….json`，再原子写入新格式。原奖励、生命、位置与恢复凭据保留，每个旧角色补入一次三件未穿戴的本地新手装备；新版重启不会重复发放。不要用旧版程序打开 v2 存档。回退时先停服，同时恢复旧代码与对应 v1 备份；备份后的新进度不会包含在旧文件里。

三维页按 B / C 或“背包与装备”打开，查看时停止自己的移动输入，世界仍继续运行。物品选择/筛选、三件装备穿脱及属性保存可用；暂未实现角色外观换装、制作、交易、分解或背包扩容。原窗口美术与原数值槽来自 SWF，装备身体部位映射、40 格容量、新手装备数值均是本地玩法。

当前角色进度保存在根目录 `runtime/characters.json`，始终不进 Git。奖励立即保存，移动定期保存，离开和正常关闭服务会保存最新状态。异常强制断电时，尚未落盘的短时间移动可能丢失；正常关闭请使用 Control-C。

服务器使用单进程原子 JSON 存档，适合当前少量朋友测试；同一份文件只给一个服务实例使用，不要让两台机器同时写共享存档。文件损坏时启动会报错并保留原文件，不会自动清空进度。

备份时先正常停止服务，然后复制整个 `runtime/` 到单独备份位置。迁到 Mac Pro 时可在新服务未启动前复制 `runtime/`，更新代码时保留它，避免用开发测试存档覆盖已有进度。

浏览器还保存角色 ID 与恢复凭据，同一浏览器访问同一服务器网址、填写原角色名才能自动恢复。清理浏览器数据、换浏览器、从 localhost 改到另一台 Mac 的 IP 时不会自动迁移凭据；当前没有跨设备账号登录或凭据导入界面，服务器存档单独复制过去不能代替浏览器身份迁移。邀请链接只包含房间号，不包含角色凭据。

`SAVE_FILE` 可在根目录 `.env` 中另设路径；相对路径以仓库根目录为基准。请放在 Git 忽略的目录或仓库外，不要放进 `prototype/public/` 或 `game-data/converted/`；服务端也会拒绝这两个静态目录。

测试调用 `createGameServer()` 默认使用内存；持久化集成测试使用独立临时目录，不会读取或修改真实 `runtime/`。
