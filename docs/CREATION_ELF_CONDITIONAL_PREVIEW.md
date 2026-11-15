# 精灵男性种族页：原材质就绪后保留已有输入

这一项只处理原种族页 display **2046 / model 33**。原胸衣 `100342` 的 `st222` 材质请求了一张缺失的 brown 覆盖图；没有补图、换衣服、调颜色，也没有把模型自带图声称为那张 brown 图。

原代码已经证明一个明确分支：当前覆盖缓存为空、确切路径没有文件流时，完整 `143f5c4` 同步返回 null，不创建纹理任务；后面的覆盖消费者跳过材质 setter，也不写覆盖缓存。**这只允许保留已经成功建立的原材质输入，不证明模型、材质或纹理已经就绪。** 因此本批另加真实网页宿主的完成检查，缺任何输入就不显示这个人物。

## 原文件与范围

原库 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。原 stage0 请求与部位数据仍使用冻结的 `creation-race-preview-20261115/source-v2.json`，SHA256 `6c3c300912f2cc7021a3784c601a7229b327916ee89c9a34ac72390b82f680a8`，没有改写它的缺图记录。

| 内容 | 已核依据 |
|---|---|
| 人物选择 | 原创建控制器选择 display 2046、model 33、extra 1957；仍只用于种族页 |
| 原胸衣 | `model/item/armor/3_chest/oc2_elf_m_light_sunken_chest.bdae`，SHA256 `2c525bb80bb5aea758326a33380dd1bbb78e9739b981b9363a5a7cb772aba1d9` |
| 确切缺图 | `texture/oc2_human_m_light_sunken_chest_brown_d.tga`，现有原包中为 0 份；不声称加载成功 |
| 原失败分支 | 独立缺流报告 `creation-texture-failure-20261115/report-v3.json`，SHA256 `3d8aa34c783f622c45139c7a868773880b0a5589767e0297608b640842aed5db` |
| 窄复用条件 | `reuse-contract-v1.json`，SHA256 `51a825509778cec34f72369b3a57cb2cbcec2d5102954f2b5eb2b0ebc2c3dc3e`；不适用于其他缺图、已有覆盖缓存或非空异步上传失败 |
| 原动作与骨骼 | 身体、发型、胸衣、鞋自己的 16 个原控制器，64 组自身 idle 的原采样/矩阵/顶点对比，误差不超过 `.002`；未改逆绑定、姿态或浮点权重 |

原 `st222` 声明的六个输入为 `texture`、`normalMap`、`maskMap`、`diffusePal`、`specularPal`、`specularPalBack`。各自原路径、原文件 SHA/CRC、解码 PNG SHA、尺寸都随独立候选保留。它们全部来自同一原 BDAE 的已有声明；没有从相似名字挑选替代图。

## 显示门怎样工作

`tools/preview/creation_elf_source_ready.mjs` 只承认这一个 display、部位、材质、缺图路径及六个确切输入。

1. 原始候选始终写 `creationPreviewAdmitted=false`、`appearanceComplete=false`、`originalAndroidFinalAppearanceKnown=false`；另以 `hostConditionalDisplay=true` 表示需完成宿主检查。不能把它混成上一批资源齐全的候选。
2. 每张输入先实际下载 PNG 字节，核对冻结 SHA，再通过浏览器图片加载器真实解码。仅在实际 `Texture` 的尺寸、像素来源和图像完成状态通过后，私有 WeakMap 才记录凭据。JSON 中写 `ready=true` 不产生凭据。
3. 等六张图和其余模型输入全部完成，才调用生产人物工厂。随后实际构造原 `RawShaderMaterial`，核对真实蒙皮对象、原效果/宏、深度/裁面规则、寻址与六个真实 uniform 绑定。占位材质、缺输入、未验证的纹理克隆均不能通过。
4. 通过之后才允许这一个人物挂到原场景。缺流分支不调用覆盖 setter，不建立覆盖缓存，六个已有绑定保持同一对象。完成收据仅表示网页宿主原输入已建立，不声称原 Android GPU 或最终外观已恢复。

加载失败时仍保留原背景，不显示上一个种族充数，不新增提示面板。完成收据只放在开发元数据中；没有把调试文字混入游戏 UI。原相机、人物位置、整数大小 5、SVG 控件、光照、服装和 idle 不改。

## 版本与校验

上一批八体的 v4 配置和 `/character_creation_race_preview_v1.mjs` 逐字节保留。本批使用独立的 **v5** 配置 `/assets/source-creation-stage/manifest-conditional-v1.json`、新 `/character_creation_race_preview_v2.mjs` 及 `/creation_elf_source_ready.mjs`。v4 不能开启该条件分支；v1/v2/v3 仍不依赖新私有模块。`allNineRacePreviewsRestored` 继续为 false。

本地工具 `tools/creation_elf_retained_candidate.py` 重建原模型和原输入；`creation_elf_conditional_delivery.py` 只追加新命名资源闭包，不覆盖八体载荷。原表、so、证据、模型、贴图和截图只放忽略目录，不上传 GitHub。

候选与检查在 `analysis/raw/creation-elf-conditional-20261115/`：

- `candidate-v1/elf-male/`：真实原模型、原材质、缺图元数据与骨骼对比。
- `host-material-ready-v1.json`：实际生产 `loadActor`、六张原 PNG SHA 和真实 `Three.DataTexture`/`RawShaderMaterial` 的 CPU 宿主构造检查。RGBA 来自真实 PNG 的 Pillow 解码，**不是浏览器或 GPU 验收**。
- `qa-static-*`：供主代理原 SVG 只读页面验收的独立静态包。没有启动服务器、浏览器、物理工作进程或角色写接口。

```sh
node --test tools/creation_elf_conditional_tests.mjs
node --test tools/creation_preview_tests.mjs tools/creation_race_preview_tests.mjs tools/character_creation_preview_proposal_tests.mjs
```

已检查：六输入真正完成前不开始模型构造；404、PNG 字节变化、未完成解码或只伪造纹理 ready 标记均不能通过；原绑定在缺流处理前后不变；新配置不能声称覆盖成功或原 Android 外观完整。实际浏览器绘制与发布由主代理另行验收。


## 父级正式策略下的实际验收（2026-11-16）

旧TextureLoader把已校验的PNG字节变为blob URL，正式`img-src 'self' data:`没有放行该URL方案。父级使用相同安全策略和同一原SVG做A/B：旧加载器仅显示背景（错误事件没有message，记录值为undefined），HTTP素材无404；仅替换新解码helper后，精灵男性2046实际显示，六张原图均有校验和真实ImageBitmap解码收据。没有放宽CSP、用Canvas2D重编码或再请求另一图片；图片原PNG无方向/色彩profile块，解码保持方向、非预乘、无颜色转换，贴图仍flipY=false/NoColorSpace。

父级还逐项实际点击其余八套原展示模型、返回并重新打开精灵男性，检查当前身份、画面和六个绑定，控制台无warning/error。龙人没有可点的性别控件，按实际DOM核对单一2052身体，不制造另一性别。此QA只读，没有创建角色、启动游戏或读写存档。私有截图、各显示身份、旧失败和新成功对照位于`analysis/raw/creation-elf-parent-strict-20261116/`。这证明网页GPU能显示原BDAE保留材质，不证明失踪brown覆盖贴图存在，也不证明原Android最终外观已知；appearanceComplete仍false。完整创角后续阶段、已存角色预览和九种身体正式可玩仍分开验收。

正式路由仅在精确v5资料和对应浏览器接口都齐备时选择条件预览；v1–v4保持旧路由，缺接口明确拒绝。新模型和图片仍按打开种族页请求，不混入新手进图预载。最终Linux、私有包、Git/CI及Railway发布状态以本批私有交接收据为准。
