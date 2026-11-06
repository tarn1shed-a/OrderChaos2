# Vercel 部署准备

当前状态：已核对平台能力、整理前端构建和独立联机端点配置，尚未部署；Vercel 账号尚未连接。

## 平台核实

截至 2026-11-07，Vercel 已正式支持 WebSocket，不能继续用“Vercel 不支持 WebSocket”作为架构依据。连接仍受函数最大时长限制；新连接不保证落到同一实例。官方要求房间、presence 和协调使用外部状态存储。[WebSocket 文档](https://vercel.com/docs/functions/websockets)、[2026-10-20 发布说明](https://vercel.com/changelog/websocket-support-is-now-generally-available)。

本项目目前的 Map、20 Hz tick 和玩家列表在单进程内存中。直接导出 HTTP server 部署到多个 Vercel Functions 实例，不能保证两位朋友互相看到。当前代码不宣称已完成 Vercel 分布式多人适配。

## 两种可用路线

1. 前端和转换资源放 Vercel；联机服务保留为独立常驻 Node 服务。迁移量较小，现有多人逻辑可复用。需要一个可访问的 WSS 后端地址，并在后端配置精确的前端 Origin。
2. 全部放 Vercel Functions；需新增共享房间状态、跨实例协调和函数回收后的恢复机制，例如通过 Redis。需要配置该存储，并完成多实例测试后才能发布为多人版本。

## 已准备的静态前端构建

当前转换资源共约 12 MB，无需上传原始约 960 MiB 数据目录。`prototype/build-vercel.mjs` 只打包 `public/`、转换资源和两个 Three.js 浏览器模块，生成 `prototype/dist-vercel/`。不包含原始包、数据库、分析目录或凭据。

构建必须提供真实后端，避免上线只有页面、没有联机服务的版本：

```sh
cd prototype
GAME_WEBSOCKET_URL=wss://你的联机服务器/ws node build-vercel.mjs
```

构建会在两个入口注入 `game-websocket` 元数据，并生成仅允许指定 WSS Origin 的 CSP。原本地页面继续使用同源 `/ws`，无需修改配置。

联机服务器启动时需配置完整前端 Origin（多个用逗号分隔）：

```sh
ALLOWED_ORIGINS=https://你的域名.vercel.app node server.mjs
```

服务器仍限制未列入的跨站连接；不通过放开所有 Origin 来部署。预览与生产域名不同，应按需要精确加入。

使用 Vercel CLI 时，从生成的 `dist-vercel` 目录部署，或通过已连接的 Vercel 插件上传该目录。不要从项目根目录上传整个工作区。账号连接和后端地址未就绪前不执行线上部署。

## 本次验证范围

已通过 Node 语法检查、`node build-vercel.mjs --check` 临时完整打包与资源引用检查，以及既有 6 项多人/地形测试；本机功能保持可用。`--check` 使用不可连接的测试域名，不是可部署产物，并在检查后清理临时输出。尚未执行真实云端部署、WSS 远程握手或跨网络双人验证。
