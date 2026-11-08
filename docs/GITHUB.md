# 仓库内容约定

当前仓库只保留离线研究工具、必要检查和证据说明。自写网页/游戏服务器、相关测试和发布入口已删除；历史原型可从审计基线提交1c77133或本地忽略备份追溯。

上传：研究脚本、依赖说明、测试、README、文档及CI配置。

不上传：APK、原生库、原始/解包/转换资源、完整表格、原生转储、截图、私有存档、凭据和备份。整个 `game-data/`、`analysis/raw/`、`runtime/`、`backups/` 保持忽略。

```sh
git status --short
git diff --cached --stat
git ls-files
git check-ignore game-data/extracted/world/tutorial.wld
```

CI只验证仓库中的研究工具。缺少私有输入时源样本测试会跳过，不能代替原文件核验或原进程观察。当前没有朋友服务器启动、数据库迁移或网页部署步骤。
