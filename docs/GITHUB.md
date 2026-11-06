# 上传 GitHub 前的项目约定

仓库只管理自编代码、依赖锁文件、配置示例和研究说明。游戏资源另行传输。

| 上传 | 不上传 |
|---|---|
| `prototype/` 源码、测试、锁文件 | `node_modules/`、构建与部署产物 |
| `tools/` Python 工具与依赖说明 | `.venv/`、`__pycache__/` |
| README、`docs/`、分析文字 | `analysis/raw/`、分析截图 |
| `.env.example`、启动脚本 | `.env`、数据库、日志、备份 |
| GitHub 源码检查配置 | APK、原始/解包/转换资源，整个 `game-data/` |

新仓库不要自动生成 README、许可证或 `.gitignore`，以免与本地已有文件冲突。将你自己的仓库 URL 配置为 `origin` 后再推送；代码许可证和仓库可见性由仓库所有者确定。

检查待上传内容：

```sh
git status --short
git diff --cached --stat
git ls-files
git check-ignore game-data/converted/manifest.json
```

项目设置为 `private: true` 只防止意外发布到包仓库，并不决定 GitHub 仓库的可见性；GitHub 创建仓库时仍需选择 Private。

首次提交前配置你自己的 Git 用户名与邮箱，然后提交。朋友克隆后的启动和资源迁移步骤见 [LOCAL_SERVER.md](LOCAL_SERVER.md)。GitHub 检查不依赖游戏资源；模型集成测试在无资源时会明确显示跳过。
