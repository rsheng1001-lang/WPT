# 最新输入重生成：v6

以当前 inputs/ 下的 2026-09-20 分层 PDF、Multi-Layer 板框和贴片 CSV 为输入，重新执行铜层提取、轮廓提取、元件模板刷新、坐标配准与 Illustrator 导出。使用现有 v4/v5 的视觉设置，不添加位号。

- 主图：WPT_Exploded_Refined.ai / .pdf / .svg / .png
- 细节图：WPT_Geometry_Details.ai / .pdf / .svg / .png
- 元件 32 个：顶面 21、底面 11。
- 真实板框含 8 个挖槽；11 个结构层，包括上下两片 coverlay。
- 开窗按当前焊盘外扩 0.1 mm 推导：顶部 24 个合并区域，底部 15 个，图注标 derived。
- 层距 102 pt、压缩系数 0.32；主图弱化开窗反差，俯视图保留完整孔洞；无额外封装层。
- 23 对片式元件焊盘的最大配准偏差约 0.000356 mm，仅表示导出数据之间的坐标配准误差。

geometry_audit.json、illustrator_audit.json 和 pdf_audit.json 记录本次几何、文档和 PDF 检查。基线更新为 optimized_v6，可使用 scripts/workflow.py --check 复核。

实际流程：extract_geometry.py → extract_outline.py → refresh_templates.py → workflow.py --output-dir optimized_v6 --update-baseline。输出目录必须不存在，下次重建使用新的目录名。
