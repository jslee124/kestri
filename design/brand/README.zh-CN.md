# Kestri 视觉规范

[English](README.md)

主彩色标志和头像直接使用选定原图，**不重新绘制、不裁切、不简化渐变、不增加边距**。
原图保存在 [kestri-portrait-source.png](kestri-portrait-source.png)。头像和彩色图形 PNG
与该原图的文件内容逐字节相同。横向标志将完整方形原图与已有矢量字标组合。

全身吉祥物继续作为独立矢量插画使用。辅助单色图形是简化的矢量演绎，不是彩色原图的完全复刻。

## 交付文件

| 素材 | 矢量母版 | PNG 导出 | 用途 |
| --- | --- | --- | --- |
| 主标志 | [SVG](assets/kestri-logo.svg) | [1920 × 640](assets/kestri-logo.png) | 项目页头、网站 |
| 深色背景彩色标志 | [SVG](assets/kestri-logo-dark.svg) | [1920 × 640](assets/kestri-logo-dark.png) | 彩色红隼搭配暖白字标 |
| 深墨色标志 | [SVG](assets/kestri-logo-ink.svg) | [1920 × 640](assets/kestri-logo-ink.png) | 浅色背景单色使用 |
| 反白标志 | [SVG](assets/kestri-logo-reverse.svg) | [1920 × 640](assets/kestri-logo-reverse.png) | 深色背景单色使用 |
| 吉祥物 | [SVG](assets/kestri-mascot.svg) | [1440 × 1920](assets/kestri-mascot.png) | README、文档、插图 |
| 彩色图形 | [SVG](assets/kestri-mark.svg) | [1254 × 1254](assets/kestri-mark.png) | 独立产品标识 |
| 深墨色图形 | [SVG](assets/kestri-mark-ink.svg) | [1024 × 1024](assets/kestri-mark-ink.png) | 单色标识 |
| 反白图形 | [SVG](assets/kestri-mark-reverse.svg) | [1024 × 1024](assets/kestri-mark-reverse.png) | 深色背景标识 |
| 字标 | [SVG](assets/kestri-wordmark.svg) | [1024 × 366](assets/kestri-wordmark.png) | 纯文字品牌呈现 |
| 头像 | [SVG](assets/kestri-avatar.svg) | [1254 × 1254](assets/kestri-avatar.png) | Telegram 头像上传 |
| 品牌展示板 | [SVG](assets/kestri-brand-sheet.svg) | [2400 × 1650](assets/kestri-brand-sheet.png) | 审阅、分享 |

另提供 [512](assets/kestri-avatar-512.png)、[128](assets/kestri-avatar-128.png)、
[64](assets/kestri-avatar-64.png) 和 [32 像素](assets/kestri-avatar-32.png)头像。
原图、彩色图形及头像保留原有不透明暖白背景。组合标志保留原图方形区域，文字周围为空白透明区域。
吉祥物、字标与单色素材为透明背景，单色脸部留白使用真正的透明镂空。
彩色标志、图形、头像和展示板的 SVG 内嵌原图 PNG，是混合格式，不是纯矢量文件。
吉祥物、字标及单色版本使用可编辑矢量路径，没有外部字体依赖。

## 颜色

下列固定色值用于矢量吉祥物和字标。半身原图保留其原有渐变与颜色，不压缩为这些色块。

| 用途 | 色值 |
| --- | --- |
| 赭橙色头部与翅膀 | `#CA7448` |
| 奶油色脸部与胸口 | `#F6E5CC` |
| 深墨色眼睛、脸颊纹与文字 | `#30343B` |
| 灰蓝色翅膀与喙 | `#63758C` |
| 金黄色喙与脚 | `#EAAF56` |
| 暖白色背景与高光 | `#FFFCF6` |

## 使用方式

白色或暖白背景使用主标志；深墨色背景使用深色背景彩色标志，单色场景使用反白标志。保留提供的比例和间距，
不要拉伸、改色或旋转。保留原图已有渐变和身体延伸到画框边缘的构图，不添加外围边距或弧形半身裁切。
标志外部至少留出一个小写字母
高度的空白；吉祥物外部至少留出其展示高度 10% 的空白。

建议标志展示宽度不低于 180 CSS 像素，更小的位置使用独立图形或头像。
头像建议不小于 32 像素，全身吉祥物建议不小于 160 像素。这些是设计建议，
不是平台限制。上传方形头像 PNG 即可，脸部和头顶保留在圆形裁切范围内。
不要将全身吉祥物缩成很小的头像。

素材已经可以在项目中使用。已配置的 Telegram 机器人使用新版彩色头像，Telegram 已确认更新，
随后查询头像也返回了新的方形图片。项目根目录 README 将标志居中，深浅主题下均使用彩色红隼，
深色主题搭配暖白字标。此前生成的 PNG 保留为历史概念参考，不作为正式母版。

## 编辑与导出

在 [build_assets.py](build_assets.py) 中修改命名路径和共用颜色，然后执行：

```sh
python3 design/brand/build_assets.py
node design/brand/render_assets.cjs
node design/brand/check_assets.cjs
python3 scripts/check_docs.py
```

Python 构建脚本只使用标准库，并读取 `kestri-portrait-source.png`；分享构建脚本时需包含此原图。PNG 导出器需要公开 npm 包 `sharp`，可以使用已有安装，
或设置 `NODE_PATH` 指向包含该包的运行时。[render_assets.cjs](render_assets.cjs)
直接从矢量母版导出 PNG。也可以直接编辑生成的 SVG，但重新构建会覆盖这种编辑；
需要持久保留的修改应同步到构建脚本。

在浏览器打开[预览页](preview.html)，可比较深浅背景、方形与圆形头像及不同小尺寸。
静态品牌展示板提供主要视觉的集中预览，不需要启动服务。

## 验证

使用与导出器相同的 `sharp` 运行时执行 [check_assets.cjs](check_assets.cjs)。

已在本地查看 SVG 文件的栅格导出。检查覆盖 SVG 解析、唯一标识、内部引用、内嵌原图内容一致、
无外部资源和字体依赖、导出尺寸、预期透明背景以及单色镂空。头像和彩色图形 PNG
与原图进行逐字节一致性检查。文档检查器已覆盖 `design`
目录，并验证翻译配对和链接。本地裁切预览不等同于真实 Telegram 客户端的显示效果或印刷验收；
接口更新成功和头像回读证明已配置机器人的头像已更换。
