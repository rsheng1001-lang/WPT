# 横向与纵向科研图：审查优化版

- `landscape/WPT_Exploded_Refined.ai / .pdf / .png`：横向论文排版，180 × 135 mm，4:3。
- `portrait/WPT_Exploded_Refined.ai / .pdf / .svg / .png`：纵向完整叠层图，与 v6 文件逐字节一致。
- `figure_caption.txt`：英文图注，包含 nominal、derived、独立放大及示意尺度说明。
- `layout_audit.json`：纵向文件哈希与横向几何保留检查。
- `review_audit.json`：最终 PDF 尺寸、字号、栅格和局部裁切检查。
- `landscape/illustrator_audit.json`：实际 Illustrator 图层、对象与文字边界检查。

## 本轮审查与修正

1. v7 局部图放大 3 倍造成顶侧器件贴边或裁切，降至 2.4 倍，完整保留中央电路器件。
2. 内层附近由约 47 pt 间距调整至 53 pt，重新安排元件层位置，减轻局部遮挡。
3. 局部图增加按原始 PCB 坐标换算的 2 mm 比例尺；比例尺只适用于 b/c 面板。
4. 小注释字号提高，Illustrator 内等比缩放到 180 mm 宽后最小字号实测 7.14 pt。
5. 主图只显示必要层名和厚度，详细来源、derived 与示意尺度说明集中到独立图注。

底层数据、元件位置、开窗规则均不改；无位号。横向图的 a 面板为示意层距，b/c 为同源俯视矢量局部图，不应把不同面板当作同一比例。
横向 SVG 保留 1000 × 750 pt 的构图工作尺寸；AI/PDF/PNG 在 Illustrator 内等比缩放为 180 × 135 mm。若更换论文栏宽，需重新核对实际字号，不能直接缩成单栏后沿用本轮可读性结论。

## 重建

使用现有 Illustrator skill 虚拟环境运行：

```powershell
$skillPython = 'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent\.venv\Scripts\python.exe'
& $skillPython scripts/build_layout_variants.py --output-dir 新目录
& $skillPython 'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent\examples\progressive_svg.py' --source-svg 新目录/landscape/WPT_Exploded_Refined.svg --output-dir 新目录/landscape/illustrator_main --mode instant
& $skillPython scripts/export_illustrator.py --output-dir 新目录/landscape --main-only --width-mm 180
```

构图器拒绝覆盖现有目录。使用了 Illustrator skill 的矢量导入方式与原生缩放，未使用栅格重绘。导入时出现 SVG Tiny 裁切兼容性提示；最终 PDF 已复核裁切显示，32 个器件轮廓均位于各自局部图裁切边界内。
