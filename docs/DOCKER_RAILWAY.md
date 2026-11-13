# Docker 迁机与 Railway 试玩部署

2026-11-13。只迁移当前已核对的试玩运行资料，不恢复新的游戏机制，也不改变地图、光源、角色、碰撞公式或原始出生位置。自动任务 2 保持暂停。原开局、神殿楼层和完整 1:1 显示的既有缺口仍以原文档为准。

## 包含什么

- `Dockerfile`：固定 Node 22 Linux 镜像摘要，安装 Python 与既有原指令执行依赖；不需要 GPU、Android 模拟器或 Ghidra。
- `.dockerignore`：构建内容采用白名单。原 APK、分析目录、私有存档、环境文件、备份、Git 历史和旧未跟踪草稿不进普通 Git 构建。
- `deploy/bootstrap.py`：先检查 Linux 的 `/data` 实际挂载，再校验私有资料包、拒绝路径越界和链接文件，逐文件核对后解出临时运行目录；以 Linux 文件锁限制一个存档写入者。未挂磁盘不写临时存档，进程崩溃后锁由操作系统释放，不根据旧 PID 猜测。
- `deploy/server.mjs`：沿用本地 MVP 相同的服务工厂及选项，只将监听地址换为 `0.0.0.0:$PORT`，存档换为 `/data/saves/characters.json`。不加载 Mac 本地存档。
- `tools/package_deployment.py`：只打包 127 份已核对运行文本、转换素材、8 份碰撞/动作输入、原 SO 和 135 个 PHY 引用（按内容去重）；不复制整个分析目录或原资料全集。52 份 Python 依赖文本来自已跟踪文件并单独校验。
- `.railway/railway.ts`：只管理现有游戏服务和它的独立磁盘，保留其他变量。使用 Railway 当前的 IaC 配置，未使用即将停止读取的 `railway.toml`。根目录的 `package.json` 仅供 Railway 配置工具，不是游戏启动项目。

原游戏及本地原型代码的 SHA 保持不变。部署独立将 `ws` 从旧运行依赖 8.18.3 固定为 8.23.0，修复已公开的内存泄露/耗尽问题；没有修改消息格式或游戏代码。本地旧服务的依赖未升级。Three.js 仍为 0.187.0。两端联机和持久化检查覆盖这份部署依赖。

## 私有迁机包

先在原资料所在的 Mac 上核对并打包：

```sh
.venv/bin/python tools/package_deployment.py --output backups/deployment/oc2-runtime-20261113.tar.gz
```

工具拒绝覆盖已有包。需另打包时指定新文件名。当前包 142,363,493 字节，载荷共 393,409,640 字节、2697 份文件（另含一份包清单），SHA256：

```text
90223e60957de33315c3fa85a5d4d095aebb63515c8c6b22bc7310f95878186e
```

原路径只在复制出的配置里改为 Linux 路径；现有 `native-physics.json` 和原资料均不改。资料包及其 receipt 留在忽略的 `backups/deployment/`。没有角色存档、恢复码、浏览器状态或 Railway 凭据。

## 本地 Linux 启动

Docker Desktop 启动后，在项目根目录执行；`OC2_BUNDLE_PATH` 使用私有包的绝对路径：

```sh
export OC2_BUNDLE_PATH="$PWD/backups/deployment/oc2-runtime-20261113.tar.gz"
export OC2_BUNDLE_SHA256=90223e60957de33315c3fa85a5d4d095aebb63515c8c6b22bc7310f95878186e
docker compose up --build -d
```

打开 `http://127.0.0.1:8880/explore-map.html?room=LINUX-01&sourceProfile=APK_Default`。端口只映射至本机。命名磁盘 `oc2-test-saves` 与 Mac 的 `runtime/mvp` 完全分开；不要把原本地存档目录绑定到 `/data`。普通 `docker compose down` 保留测试磁盘；不要用 `down -v` 删除想保留的角色。

容器内是 Linux x86_64；Mac 上由 Docker 执行该镜像，原 ARM64 指令仍由 Unicorn 执行。跨平台验收比较的是原指令结果，不把 Mac 上的模拟耗时当成 Railway 实机性能。

## 首次上传 Railway

Git 仓库没有完整运行资料，因此首次不能仅靠 GitHub 自动部署。生成独立白名单上下文：

```sh
.venv/bin/python tools/package_deployment.py \
  --output backups/deployment/oc2-runtime-20261113.tar.gz \
  --context backups/deployment/railway-context-new
```

这个忽略目录包含部署代码和 `deploy/private-runtime.tar.gz`；它只上传至用户指定 Railway 游戏服务的私有构建，不进入 GitHub 或公共容器仓库。不要对项目根目录执行 `railway up --no-gitignore`，否则会把不相关的本地资料一起发送。

本机 Railway CLI 安装在 `~/Applications/OC2Tools/railway-v5.71.1/railway`。首次登录应核对工作区是用户的 `tarn1shed-a's Projects`，服务为 `OrderChaos2`，不操作另一个 Chrome 登录会话的其他项目。CLI 凭据留在用户配置目录。

1. `railway link` 选中现有游戏项目、`production` 和 `OrderChaos2`。
2. 根目录 `npm ci` 安装配置工具后运行 `railway config plan`，检查仅修改游戏服务、创建并挂载 `/data` 磁盘；再执行 `railway config apply`。不使用删除或全局变量接管。
3. 只设置两个变量，保留其他值：`OC2_BUNDLE_SHA256` 为包 SHA，`MAX_PLAYERS_PER_ROOM=8`。容量范围仍为 1–32；这不是已通过 32 人负载测试。
4. 对生成的私有上下文执行 `railway up 路径 --path-as-root --no-gitignore --service OrderChaos2 --detach`，等待实际健康状态，不能把上传成功当作部署成功。
5. 生成 Railway HTTPS 域名，验证 `/health`、真实 WebSocket、页面加载和云端重启恢复。

启动时资料包缓存到 `/data/bundles/<SHA>.tar.gz`，角色放在 `/data/saves/`。这样之后仅修改宿主部署代码/文档的 Git 构建可从同一磁盘校验并恢复资料，不需要把原资源提交 Git。若游戏运行文本、Python 原指令宿主或素材改变，须重新核对、生成资料包并更新 SHA；不能继续使用旧缓存冒充新内容。缺包或校验不符直接启动失败，不启用替代碰撞或空场景。

当前账号是 Trial，初次使用单实例、1GiB 内存上限、2 vCPU 上限、500MB 磁盘；没有升级付费套餐。试用额度/期限用完会影响可用性，长期保留需用户自行选择套餐。资料缓存约 142MB，不能把原 829MB 全资源及研究转储塞进这份磁盘。持续多人性能仍需观察真实云端数据。

## 本次核查

- Source-only 部署边界检查 8 项通过；既有 MVP 参数/存档目录保护检查通过。
- Linux x86_64 实际加载 251 地形块、1040 碰撞实例、2702 形状。墙、台阶、静止跳、桥面下落、区块接缝共 275 帧，与 Mac 相同请求的结果在 0.0001 容差内逐项一致。
- 真实双 WebSocket：单人进入、第二人加入、原碰撞移动、坐标广播、装备广播、静态素材和私有路径隔离通过。
- 删除并重建测试容器、保留同一命名磁盘后，两名角色的位置、装备、物品、职业与进度恢复通过。同一磁盘的第二个写入服务被明确拒绝。
- 再切到完全没有原资源的 Git 构建镜像，仅挂同一测试磁盘，资料从校验缓存恢复、两人存档恢复通过。损坏存档会拒绝启动，测试文件前后 SHA 相同，没有重置成空档。
- 双浏览器实际加载角色与地图、同图两人和交互按钮；浏览器无 warning/error。连续行走的主要迁移回归由真实联机输入和上述原指令重放验证；不将它说成全图原版可达性验收。
- 第一版验收脚本的测试房间名超过既有 16 字符限制，已改短；游戏限制未改。旧镜像中的验收脚本导致首次恢复验收失败，修正测试脚本后恢复通过；不是改游戏绕过失败。

## 云端结果

现有 `mellow-endurance / production / OrderChaos2` 已以私有上下文部署，首轮部署 `5be599ed-483d-4356-849a-cd8ff24b2bfa` 健康检查成功。访问：

https://orderchaos2-production.up.railway.app/explore-map.html?room=RAILWAY-01&sourceProfile=APK_Default

真实公网 HTTPS、WebSocket、两人移动/装备广播及云端重启恢复通过。首次恢复检查过早命中重启期间的不可用窗口，等待健康状态后重新检查通过，未修改游戏或存档来绕过。原 Mac 的三份活动/历史存档前后 SHA 全部相同。

注意原预览逐个加载很多小图片和模型，在本地不明显，外网首次载入较慢。当前服务仍用原加载代码，不把上传成功或 `/health` 成功等同整张地图立即可玩。浏览器画面及最终 Git 对应部署复核记录在本地交接中。

云端完整加载后，已在真实浏览器以独立测试角色进入 `RAILWAY-01`，原地图、角色、状态栏和战斗操作区显示，浏览器无 warning/error。首载需要数分钟，未为缩短等待而改写游戏加载逻辑；未把这次迁机验收说成地图 1:1 缺口已解决。

Railway 当前显示约 0.94GB（含服务文件缓存）的内存用量，试用上限 1GB，余量有限；未据此承诺 8 人负载已通过。长期联机建议 Hobby 后放宽到 2GB，需由用户选择付费套餐，本轮没有升级。Mac Docker 的工作集读数约 0.45GB，不可直接与含缓存的云端总量混为同一指标。

完整包、逐帧结果、日志、云端配置快照和独立测试存档只保存在 `analysis/raw/railway-migration-20261113/`、Docker 测试磁盘和 `backups/deployment/`。云端实际部署结果及最终存档保持核对见目录最新交接。
