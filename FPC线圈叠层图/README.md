# FPC 接收端叠层图

当前版本：

- **optimized_v10** — 完整叠层图（竖版主图 + 俯视细节图），2026-09-21 视觉优化版
- **optimized_v10_compact** — 紧凑版：层距收紧到约 40% 重叠、标签精简成两行，单栏 90 mm 宽
- **optimized_v10_paper** — 论文排版版（横版 180×135 mm 双面板 + 竖版副本 + 英文图注与评审审计）
- **optimized_v10_horizontal** — 横向排列版：整幅图旋转 90°，11 层从左到右，按论文双栏 180 mm 宽出图

各版本均提供 AI、PDF、SVG、PNG；历史版本全部保留。

- [主图预览](optimized_v10/WPT_Exploded_Refined.png) · [Illustrator](optimized_v10/WPT_Exploded_Refined.ai)
- [紧凑版预览](optimized_v10_compact/WPT_Exploded_Refined.png)
- [论文横版预览](optimized_v10_paper/landscape/WPT_Exploded_Refined.png) · [英文图注](optimized_v10_paper/figure_caption.txt)
- [横向排列版预览](optimized_v10_horizontal/WPT_Exploded_Refined.png)
- 数据审计：`optimized_v10/geometry_audit.json`、`illustrator_audit.json`、`pdf_audit.json`
- 排版审计：`optimized_v10_compact/layout_audit.json`、`optimized_v10_paper/layout_audit.json`、
  `review_audit.json`、`optimized_v10_horizontal/layout_audit.json`

## 目录

```text
FPC线圈叠层图/
├─ optimized_v10/        完整图（当前基线）
├─ optimized_v10_compact/    紧凑版：紧层距 + 精简标签（单栏 90 mm）
├─ optimized_v10_paper/  论文排版版：landscape/ + portrait/ + 图注与审计
├─ optimized_v10_horizontal/  横向排列版：整幅旋转 90°，层从左到右
├─ optimized_v4 … v9/    历史版本（v7-v9 为论文横版迭代记录）
├─ inputs/               2026-09-20 导出：分层 PDF、原始 ZIP、贴片坐标 CSV、
│                        顶/底面自动位号图、BOM、接收端原理图
├─ data/                 重建必需的铜层、板框、封装模板与校验基线
├─ scripts/              提取、构图、Illustrator 导出、排版变体、评审、一键流程
└─ README.md
```

`inputs/BUTTON` 是原始导出中的底铜层目录名称，未改名。当前装配层在 `inputs/装配`。
`data/component_templates.json` 提供封装尺寸等模板；其中 `x`、`y`、`own_pads`
是建档时的记录值，**不作为当前落点使用**（构图时按 CSV 重新配准并从铜层重新取焊盘）。
模板里保留的 C11、C15-C17、D6、Q2、Q3、U4、U5 是上一版板上去掉元件的记录，不影响出图。

## 工作流程

1. **确认输入。** 铜几何来自 `data/geom.json`，板框和 8 个挖槽来自
   `data/outline_contours.json`；元件位置来自 `inputs/PickAndPlace*.csv`
   （UTF-16、制表符分隔）。
2. **配准与构图。** `scripts/build_figure.py` 拟合 CSV 原点，生成元件、11 个结构层和两个
   SVG。覆盖膜开窗沿用焊盘外扩 0.1 mm 的 derived 规则（过孔不开口），主图弱化开窗反差，
   俯视图保留完整孔洞。器件数、清单与图注文字均由数据推导，不写死。
3. **Illustrator 矢量导入。** 使用 scientific-illustrator-agent skill 的
   `examples/progressive_svg.py`，将 SVG 导入为实际可编辑矢量对象。
4. **命名分层与导出。** `scripts/export_illustrator.py` 整理独立图层，输出 AI、高清 PNG、
   PDF（`--width-mm` 可等比缩放到最终宽度），检查对象数量、栅格、图层次序和文字边界。
5. **论文排版变体。** `scripts/build_layout_variants.py --source <完整图目录>` 组合横版：
   a 面板为全部 11 层（非等距），b/c 面板为顶/底面电路局部放大（2.4 倍、带 2 mm 比例尺），
   并生成英文图注；`scripts/review_layout.py` 复核页面尺寸、最小字号、裁切余量与栅格。
6. **横向排列版。** `scripts/build_horizontal_variant.py --source <完整图目录>` 把整幅图旋转
   90°（每层绕自身站点 rotate(-90)），层序改为从左到右、顶层在最左；文字保持水平并错行
   排在下方两行，按 180 mm 宽导出以保证最小字号 ≥7 pt。图层路径数据原样复制，只改摆放与文字。
7. **紧凑版。** `scripts/build_compact_variant.py --source <完整图目录>` 收紧层距（重叠约
   40%）、缩小图形比例、把标注精简成两行并移到右侧，按单栏 90 mm 导出；标注字号与
   图形比例配合，保证成品最小字号 ≥7 pt。
8. **核对交付。** 检查实际 PNG/PDF；查看各审计 JSON。视觉变更与数据变更分开记录。

## 命令

使用现有 skill 的 Python 环境，其中包含 pywin32、Pillow、Shapely、PyMuPDF。

```powershell
$skillPython = 'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent\.venv\Scripts\python.exe'
$skill = 'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent'

# 只检查重建一致性；不打开 Illustrator，不改变当前成品
& $skillPython 'scripts\workflow.py' --check

# 完整重建；输出目录必须不存在；--update-baseline 把本次结果记为新的校验基线
& $skillPython 'scripts\workflow.py' --output-dir 'optimized_v11' --update-baseline

# 论文横版（在完整图目录之后执行）
& $skillPython 'scripts\build_layout_variants.py' --source 'optimized_v11' --output-dir 'optimized_v11_paper'
& $skillPython "$skill\examples\progressive_svg.py" --source-svg 'optimized_v11_paper\landscape\WPT_Exploded_Refined.svg' --output-dir 'optimized_v11_paper\landscape\illustrator_main' --mode instant
& $skillPython 'scripts\export_illustrator.py' --output-dir 'optimized_v11_paper\landscape' --main-only --width-mm 180
& $skillPython 'scripts\review_layout.py' --source 'optimized_v11' --output-dir 'optimized_v11_paper'

# 横向排列版（旋转 90°，按论文双栏 180 mm 宽导出）
& $skillPython 'scripts\build_horizontal_variant.py' --source 'optimized_v11' --output-dir 'optimized_v11_horizontal'
& $skillPython "$skill\examples\progressive_svg.py" --source-svg 'optimized_v11_horizontal\WPT_Exploded_Refined.svg' --output-dir 'optimized_v11_horizontal\illustrator_main' --mode instant
& $skillPython 'scripts\export_illustrator.py' --output-dir 'optimized_v11_horizontal' --main-only --width-mm 180

# 紧凑版（紧层距 + 精简标签，按单栏 90 mm 宽导出）
& $skillPython 'scripts\build_compact_variant.py' --source 'optimized_v11' --output-dir 'optimized_v11_compact'
& $skillPython "$skill\examples\progressive_svg.py" --source-svg 'optimized_v11_compact\WPT_Exploded_Refined.svg' --output-dir 'optimized_v11_compact\illustrator_main' --mode instant
& $skillPython 'scripts\export_illustrator.py' --output-dir 'optimized_v11_compact' --main-only --width-mm 90
```

一键流程不覆盖现有目录；无需手工改脚本中的输出路径。换机器时可设置
`FPC_ILLUSTRATOR_SKILL` 指向 skill 目录，并使用安装了依赖的 Windows Python 和 Adobe
Illustrator。

基线保存在 `data/reference_audit.json`（含当前成品目录名与 3 个数据文件的 SHA-256）。
`--check` 会在系统临时目录重建 SVG 并与当前成品逐文件比对；它不重复运行 Illustrator，
不能代替新改图后的视觉检查。

## EDA 改版后的数据更新

`build_figure.py` 从已提取并校验的 `data/*.json` 开始，不重新解析 EDA 导出。
**PCB 改版后必须先更新几何缓存与元件模板，再重建**，顺序如下：

```powershell
# 1) 新导出的 ZIP 解到 inputs\（保持中文目录名），替换同名 PDF 与 CSV
# 2) 铜层几何（四层；提取器按旧 geom.json 校准过：填充多边形逐点一致）
& $skillPython 'scripts\extract_geometry.py' --out 'data\geom.json' `
    L1_TOP 'inputs\TOP\Top Layer.pdf' L2_GND 'inputs\GND\GND.pdf' `
    L3_POWER 'inputs\POWER\POWER.pdf' L4_BOTTOM 'inputs\BUTTON\Bottom Layer.pdf'
# 3) 板框与挖槽（Multi-Layer 层；应得 outer 1 + holes 8）
& $skillPython 'scripts\extract_outline.py' --src 'inputs\板框\Multi-Layer.pdf' --out 'data\outline_contours.json'
# 4) 按新 CSV 刷新模板中的换面、旋转、封装、二极管阴极方向
& $skillPython 'scripts\refresh_templates.py'
# 5) 重建并记录新基线
& $skillPython 'scripts\workflow.py' --output-dir 'optimized_v11' --update-baseline
```

新封装（如 SOT-323-5）需要在 `refresh_templates.py` 的 `PACKAGE` 表中补尺寸；
通过孔直径变化时，`build_figure.py` 的覆盖膜过孔判定窗口（当前 1.4–2.0 pt 正方圆）
也要一起核对。

## 无人值守运行 Illustrator 的注意事项（2026-09-21 实测）

脚本化导入/导出时，Illustrator 的模态对话框会让 COM 调用**无限等待**，看起来像卡死。
本机遇到两类，均可用 `PostMessage(hwnd, WM_CLOSE=0x0010)` 关闭（等效于点默认/取消按钮；
UI Automation 的 Invoke、BM_CLICK、WM_KEYDOWN 都无效）：

1. **崩溃恢复提示**（"Illustrator 刚刚从崩溃中恢复正常"）：应用级模态，会挡住后续所有
   脚本调用。必须优先关掉，否则即使关掉别的提示，导入也不再继续。
2. **SVG 导入兼容性提示**（"往返至 Tiny 时剪贴将丢失"）：每次导入带裁切路径的 SVG 都会出现
   （横版图有 clipPath，竖版图没有，所以只有横版会触发）。

建议在跑导入/导出前先启动 Illustrator 并清空所有 `#32770` 对话框，或挂一个轮询脚本
（枚举该进程的可见 `#32770` 窗口并逐个 WM_CLOSE）。另外：强制结束 Illustrator 后下次启动
必然弹恢复提示，属正常现象。

## 2026-09-21 论文版视觉优化记录（v9 → v10）

Codex 在 v7-v9 完成了论文横版（180×135 mm 双面板、2.4 倍局部图、2 mm 比例尺、英文图注、
最小字号 7.14 pt），并在整理阶段留下三项视觉建议。本轮完成其中两项（第三项在 v9 已完成）：

- **内层铜加深**：L2/L3 在缩到论文版面后过淡，新增 `copperInner` 渐变
  （#8B5D32 → #C9A87E → #875729，比主铜色深约 15%），仅用于 L2_GND / L3_POWER。
- **覆盖膜材质化**：coverlay 由平涂 `#E6DFC7` 改为很弱的同色竖向渐变
  （`#EDE7D3 → #DCD2B2`），与内层 PI 的表现更一致；开窗反差保持低对比不变。
- 两项改动只影响观感：几何、元件、开窗数据与 v5/v6 完全一致（数据哈希比对通过）。
- 横版沿用竖版图层与 defs，自动继承这两项改进；`build_layout_variants.py` 与
  `review_layout.py` 已参数化（`--source` / `--output-dir`），不再硬编码版本目录。
- 校验：主图 357 路径 / 31 文本 / 14 图层，零栅格、无文字越界；横版 556 路径 / 23 文本 /
  17 图层，32 个器件全部位于裁切边界内，页面 180.0×135.0 mm，最小字号 7.14 pt。

### 横向排列版（optimized_v10_horizontal）

按"整幅图旋转 90°"的方式排列：每层绕自己的站点 rotate(-90°)，层序从左到右、顶层在最左，
层与层的重叠关系与竖版一致；文字保持水平，标注按短行换行、两行错行排在各层下方（11 列互不
相撞）。按论文常规双栏宽 **180 mm** 导出：构图 794×463 pt、图层缩放 0.68 并同步收紧列距，
成品 **180.0×105.1 mm**，字号 10.3 / 7.7 / 7.1 pt（全部 ≥7 pt），零栅格、无文字越界、
15 个命名图层；图层路径数据与竖版逐字节相同（`layout_audit.json` 中逐层核对），只改摆放与文字。
换其他成品宽度时改 `build_horizontal_variant.py` 里的 `EXPORT_WIDTH_MM`（脚本会断言最小字号不低于 7 pt）。

### 紧凑版（optimized_v10_compact，对照参考图风格）

参考图上别人的做法是"层距小、层与层明显重叠、标签只有层名"的紧凑风格。据此把竖版重排：

- 层距 102 → **30 pt**（相邻层重叠约 60%，整叠读作一个紧凑整体，与参考图一致）；
- 图形在构图内缩放 0.62；标注改为**单行**（层名 · 厚度/数量），说明移到页脚；
- 按 **单栏 90 mm** 导出：成品 **90.0×114.4 mm**，字号 7.6 / 7.0 pt（≥7 pt），
  零栅格、无文字越界、15 个命名图层；
- 图层路径数据与 v10 逐字节相同（`layout_audit.json` 逐层核对），几何未改动，只改摆放、
  构图内缩放与文字。数据源仍是同一套 `data/*.json`。

层距与图形比例可在命令里覆盖：`--pitch 26 --art-scale 0.58`（层距越紧，标签行距越要留意；
脚本会断言最小字号不低于 7 pt）。

## 2026-09-20 改版重建记录（v4 → v5，数据基线）

接收端板当日改版重导，`inputs/` 全部换为 2026-09-20 版本（导出时间 19:41），据此重建：

- **元件 41 → 32**（顶 21 / 底 11）：去掉 C11、C15、C16、C17、D6、Q2、Q3、U4、U5；
  Q1 与 R2/R3/R4 换面；10 个元件旋转角变化；U1 封装 SOT-23-5 → SOT-323-5，
  U3 SOT-23-3 → SOT-23-5，D5 换为 VESD16C1-02V-G3-08（SOD-523）。
- **内层铜重布**：L2/L3 走线明显减少（GND 230 → 70 段），过孔从约 30 个/面减到约 14 个/面，
  直径 1.56 → 1.73 pt；覆盖膜的过孔排除阈值随之放宽。
- **板框与 8 个挖槽不变**（外轮廓逐点一致）。
- 配准原点 (41.7205, 41.7241) pt，23 对片式元件焊盘最大偏差 **0.00036 mm**。
- 观感自 v4 起沿用（层距 102 pt、倾斜 0.32、缩放 4.45、开窗低反差）。
- 提取器为按旧 `geom.json` 校准后重建的版本：四层填充多边形逐点一致（最大偏差 0.000 pt），
  描边线段全部无损；分链粒度与旧算法略有差异，但铜层按半宽 buffer 求并集渲染，画面等价。

## 目录历史

`inputs` 中的顶/底面自动位号图与 BOM 是 2026-09-20 导出新增的资料，当前出图未使用
（位号按确认不画）；如后续需要丝印位号或 BOM 对照，可直接取用。
`D:\Shared\FPC线圈叠层图_历史备份\` 保存整理前完整备份（zip）、移出的旧版文件，
以及 v4 基线、旧几何与 2026-09-19 坐标文件。
