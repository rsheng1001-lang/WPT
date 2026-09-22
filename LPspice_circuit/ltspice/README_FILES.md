# ltspice/ 文件地图(只看这里就够了)

入口(双击打开,图里已带仿真指令):
- `full_bus.asc` —— 全链路 6 模块:输入/8V 稳压/3.3V/恒流调节/恒流控制/BONE 负载
- `sink_vendor.asc` —— 只含恒流沉三块(恒流调节/恒流控制/BONE 负载)+理想电源

必须和 .asc 同目录(不要动,LTspice 靠这个找符号):
- `*.asy` (5 个)——子电路符号:`MCP1703A33_APPROX` / `N7002` / `OPAx333` / `ST715_APPROX` / `VESD16_APPROX`
- `*.net` (2 个)——LTspice 从 .asc 导出的网表,`tools/compare_netlists.py` 拿它和 decks/ 比对用,删了会自动重生成(`run_all.py` 第 7 节会调 `-netlist` 重导)

仿真源(文本网表,真正跑的东西):
- `decks/*.cir` (9 个)——`core_op` / `core_compliance` / `core_gate_cliff` / `core_gate_margin` / `core_reconnect` / `core_startup` / `full_bus_dc` / `opa333_validation` / `tvs_compare`
- `inc/*.inc` (4 个)——被 include 的片段:`sink` / `core` / `power` / `solver`
- `models/*.lib` (5 个)——器件模型:OPA333 原厂 + 2N7002 两种 + 自制近似 `APPROX_NOT_VENDOR` + Vth 变体

工具(一键复现):
- `tools/run_all.py` —— 跑全部 8 节,输出同时写入 `summary.txt`
- `tools/run_one.py` / `tools/read_raw.py` / `tools/compare_netlists.py` —— 单跑 / 读波形 / 网表逐元件比对
- `tools/make_schematic.py` —— 生成 .asc(第 7 节数值等价校验前会重跑它)

输出(不要手改,跑脚本自动更新):
- `runs/` —— 仿真输出(.raw/.log/.db),由 `run_all.py` 的 `collect()` 自动归集
- `summary.txt` —— 最近一次完整验证的输出留档
- `preview/*.svg` —— 不方便开 LTspice 时用浏览器看的原理图预览
- `Data/` —— 归档的结果数据与图,一次运行一个文件夹,规范见 `Data/README.md`

工具缓存(不管它):
- `.ltspice-mcp/` —— MCP 服务的实验/锁/渲染缓存
- 顶层再出现 `.db` / `.log` / `.raw` / `.op.raw` 就是 LTspice GUI 随手落的,下次跑 `run_all.py` 会自动收进 `runs/`,或手动搬到 `archive/manual_gui_byproducts_*/`
