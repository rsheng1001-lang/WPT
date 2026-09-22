# FPC 爆炸图 v4：视觉优化

主图：`WPT_Exploded_Refined.ai / .pdf / .svg / .png`

完整俯视细节图：`WPT_Geometry_Details.ai / .pdf / .svg / .png`

使用 scientific-illustrator-agent 的矢量 SVG 导入及 Illustrator COM 桥生成，原有版本保留。本轮只改变视觉表现，未改变铜层、板框、器件位置、覆盖膜开窗或名义厚度数据，不添加位号。

## 主图视觉调整

- 11 个结构层统一采用 102 pt 中心间距，v3 约为 67–73 pt；相对典型的 71 pt 增加约 44%。画布增高至 690 × 1236 pt，投影缩放 4.45 和压缩系数 0.32 不变。
- 覆盖膜由 `#C9B36F` 改为低饱和浅米灰 `#E6DFC7`，不透明度仍为 100%。铜层和内层 PI 配色不变。
- 主图去除覆盖膜中央焊盘开窗的小轮廓描边，保留真实开窗复合路径，并在其下添加 `#F6F4EB` 浅色视觉衬底，降低窗口反差。只描出板框及原有 8 个挖槽的边界，不绘制开窗侧壁。
- 视觉衬底仅用于展示，不表示额外物理材料。可以在 AI 的 `TOP_COVERLAY` / `BOTTOM_COVERLAY` 图层内隐藏名称含 `WINDOW_VISUAL_TINT` 的子组，恢复透空显示。
- 引线统一置于图形右侧的留白带，x=416–444 pt，文字从 x=456 pt 开始；标签、厚度和 derived 提示按同一基线体系排布。
- `Coverlay PI`、`12.5+15um nominal` 和 derived 标注保留；增加完整开窗见细节图的提示。

## 俯视细节图

保留顶铜+元件、底铜+元件、真实板框三个原有视图，并增加顶/底覆盖膜的独立俯视图。
两张覆盖膜俯视图显示完整的真实矢量孔洞，无视觉衬底、无窗口合并简化或删减；轮廓描边用于查看开窗细节。
开窗仍采用 v3 的推导规则：铜层实心焊盘候选外扩 0.1 mm，合并交叠并裁切至真实板框，排除已识别的圆形过孔标记。顶面为 25 个区域，底面为 26 个区域。derived 表示推导结果，不是已确认的制造开窗文件。

## 数据不变与审计

`geometry_audit.json` 记录主图配色、层距、窗口表现方式，以及与 v3 的数据核对。
以下文件与 v3 的 SHA-256 完全一致：

- `components_registered.json`
- `TOP_COVERLAY_windows.json`
- `BOTTOM_COVERLAY_windows.json`

覆盖膜候选数量、窗口数量、面积、外扩量和名义厚度审计与 v3 完全一致，铜层路径/实心形状数量也保持一致。
主图结构层顺序未改；仍为 14 个 Illustrator 图层（11 个结构层，加背景、标题、标注）。
`illustrator_audit.json` 记录实际导出对象数量、图层顺序、零栅格检查和文字越界检查。

## 重建（整理后）

在项目根目录使用 PowerShell：

```powershell
$skillPython = 'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent\.venv\Scripts\python.exe'
& $skillPython 'scripts\workflow.py' --check
& $skillPython 'scripts\workflow.py' --output-dir rebuild_20260920
```

工作流拒绝覆盖现有输出目录。旧版、试验脚本和临时导入文档已经移出；当前重建只依赖 inputs、data、scripts 和外部 Illustrator skill。历史审计中的 v3 字样是原核对记录，运行时使用 data/reference_audit.json 保存的基线，不需要恢复 v3。详见项目根目录 README.md。
