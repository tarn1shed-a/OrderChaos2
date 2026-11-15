# 227原NPC与鳄鱼：本地浏览器资源验收

本批把已核原资源实际交给浏览器显示，仍未创建活动NPC、怪物、任务资格或掉落。既有角色存档与线上玩法保持；独立审阅页面不进入游戏菜单。

## 实际看到的内容

| 原资源 | 浏览器核对 | 已知边界 |
| --- | --- | --- |
| NPC872，原SC名“卢西安哪” | 原Model32默认Face1/Hair1/Chest100009/Boots100012；116节点、16合成mesh中的11个原可见mesh、1878三角形、5材质、23贴图；0、1.25、4.2666666667秒待机取样，正/侧/背面验收 | 复用原部位遮挡、float皮肤和材质参数。没有替代玩家衣服、补灯或改原角色名。没有世界GUID或任务状态。 |
| 原目标鳄鱼638 | 原37节点、27骨、1266顶点、1798三角形；6张原图及原palette/normal材质；34993、35123、36600毫秒三个原CPU姿势，正/侧面验收 | 浏览器骨矩阵最大差2.39e-7，顶点最大差3.04e-7，未改原.002核对门。三个有限姿势不是完整连续动画。 |

两页实际WebGL渲染均无console warning/error。NPC为11次draw、鳄鱼为1次draw；这证明本地Three适配器实际显示，不证明原Android GPU创建或原服活动演员存在。相机和光线沿用既有独立材质审阅设置，不能当作原地图光照或像素级1:1游戏帧。

同轮随后完成鳄鱼完整待机与行走的浏览器播放：idle为34993～36600毫秒（1.607秒），walk_forward为-7～1333毫秒（1.34秒）。11,432个原键通过原virtual60解码；保留44轨、Camera、重复关键时间及分段顺序，采用独立核过的原缓存查键和新鲜时钟，不使用Three普通keyframe。实际观察两个动作连续推进和多次回环、从待机切行走再切回，始终1次draw/1798三角形、无console warning/error。对应35个原CPU样本、25次调色板及6次全顶点控制由 [完整原动画](ORDINARY_638_ANIMATION_COMPLETE.md) 单列，不把截图当作数值核对。

## 具体修正与原依据

鳄鱼旧独立绑定工具曾因Bip01子树里含Camera01附件引用，跳过整棵骨树。实际原代码仍构造Camera01通用TRS节点；该BDAE的原camera资源段数量为0，附件查询自然走空表分支，不需要删除节点或伪造相机创建。原27骨查找、44属性setter、世界矩阵、调色板和全部顶点散射已执行。详见 [原鳄鱼绑定](ORDINARY_CROCODILE_BINDING.md)。

NPC872默认外观来自原记录与部位/遮挡代码，原五材质参数完整，不用默认标量填空。其胸衣贴图短名经原格式化得到真实tga资源；身体、衣服和头发的组合没有照搬旧玩家模型。详见 [872原资源组合](ORDINARY_NPC872_ASSET.md)。

当前材质接口可由调用者注入既有原NPC材质builder；资产factory不创建活动身份。墓碑交互分支已证：查询请求、原服任务列表、背包到账及任务进度消息分别独立，不能从“画出NPC”推导它可接交227。227尚未走完接取→战斗掉落→交回整链。

## 重跑

原文件和可校验候选只在忽略目录。以下命令需本机既有私有原资料，输出使用新目录：

```sh
.venv/bin/python tools/ordinary_crocodile_review_assets.py \
  --rig analysis/raw/ordinary-crocodile-binding-20261116/rig-final-v1 \
  --output analysis/raw/quest227-visual-review-20261116/new-croc-review
.venv/bin/python tools/ordinary_npc872_review.py \
  --candidate analysis/raw/ordinary-npc872-candidate-20261116/candidate-v2 \
  --output analysis/raw/quest227-visual-review-20261116/new-npc872-review
.venv/bin/python tools/ordinary_crocodile_review_assets.py \
  --rig analysis/raw/ordinary-crocodile-binding-20261116/rig-final-v1 \
  --animation analysis/raw/ordinary-638-animation-complete-20261116/cpu-final-v1/animation-v1.json \
  --output analysis/raw/quest227-visual-review-20261116/new-animated-croc-review
```

在各自输出目录用仅监听127.0.0.1的静态服务打开index.html。factory、材质helper、Three文件、原数据和实际截图的SHA均随私有交接保存，不上传GitHub。

872原源检查12项、原鳄鱼绑定8项已独立复跑；另有真实Three宿主426项断言，仍与浏览器GPU验收分开。父级重建的872站点与已验站点61文件完全相同；鳄鱼站点18文件中只有model.json的来源路径字段不同，原geometry、rig、pose、材质、贴图和页面字节一致。

本批没有修改游戏入口、任务批准、奖励、碰撞、场景灯光、角色位置或存档。下一步继续墓碑交回的原UI流程，以及已核两种玩家身体的真实入场接线；原服判定仍缺时不把资源显示或本地控制标成完整任务已恢复。
