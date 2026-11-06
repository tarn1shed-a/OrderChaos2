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
        └── textures/
```

资源到位后打开 `http://localhost:8787/explore.html`。不需要把 APK、原始 960 MiB 数据包、解包目录或 Python 环境传到服务器，仅运行网页所需的转换产物约 12 MB。

如需在目标机器重新研究或转换，才需要另传原始导出目录 `game-data/com.gameloft.android.ANMP.GloftO2HM/files/`，并安装 Python 3.12、创建 `.venv`、安装 `tools/requirements-resources.txt` 后运行 `tools/build_resource_preview.py`。

## 朋友连接服务器

同一局域网：朋友使用服务器 Mac 的局域网 IP，例如 `http://192.168.1.20:8787`。不要发送 `localhost`。默认监听 `0.0.0.0`，主机需要允许该端口的本地网络访问。

不同网络：需要另行设置虚拟局域网、穿透或公网部署；本项目尚未配置这些服务。服务器运行期间保持 Mac 开机、服务不退出并避免休眠。

## 更新与数据

更新时先停止服务，拉取匹配版本的代码、更新依赖，并另行同步对应版本的 `converted/`，然后启动。不要同步正在变化的整个工作目录，也不要复制 `node_modules/` 或 `.venv/`；Intel 与 Apple Silicon 机器应各自安装依赖。

当前没有账号或数据库存档，重启会清空房间，重连会以新身份回到出生点。将来加入存档时，应放入被忽略的 `runtime/` 并独立备份，不能用 Git 覆盖。
