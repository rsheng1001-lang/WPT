function [I_bus, I_bone] = bus_load_current(V_bus, R_bone)
%BUS_LOAD_CURRENT  VBUS 端口等效负载 —— 整流输出右侧整块电路（8V LDO + 3.3V LDO +
%恒流沉 + 骨负载）的集总准静态模型，供 Simulink 里的整流器/无线供电模型当负载用。
%
%   [I_bus, I_bone] = bus_load_current(V_bus)              % 骨阻默认 10 kOhm
%   [I_bus, I_bone] = bus_load_current(V_bus, R_bone)      % 标量或同尺寸向量
%
% 结构（每一步都是实测标定过的，不是拼凑）：
%
%   V_BONE_P = min(V_bus, 8.0016)          8V LDO：母线低于 8V 时进 dropout 直通
%   V_3V3    = min(V_BONE_P, 3.3)          3.3V LDO：同理
%
%   I_bone   = min( I_set , I_limit )      恒流沉：取"设定值"与"电阻极限"的较小者
%     I_set   = V_3V3/(11*R10) - 218nA     设定电流 = 3.3V 轨 / (11*3k)，比例式；
%                                          218nA 是 R9=10M 从栅极节点灌进采样节点的
%                                          误差电流（Vgs~2.48V），故骨端比设定值低 0.22%
%     I_limit = V_BONE_P/(R_bone + R10)    顺从区外 FET 全开，只剩纯电阻通路
%
%   I_bus    = I_bone + min(V_bus,8.0016)/666.8k + V_3V3/110k + 23.03uA
%     666.8k = R1+R2+R3，8V LDO 的反馈分压串（LDO 未稳压时直接挂在母线上）
%     110k   = R5+R7，3.3V 轨上恒流沉的基准分压
%     23.03uA= U1/U2/U3 三颗器件的静态电流
%
% 标定与验证（LTspice，母线 4..16V 连续扫描 + 骨阻 10k..120k 十六点）：
%   * 母线曲线（R_bone=10k，636 点）：最大相对误差 0.017%
%   * 两端电流表（16 点，含 8V/3.3V 母线的顺从拐点）：I_bus 最大 0.07%，I_bone 最大 0.06%
%   * 顺从上限（实测）：BONE_P=8V 时约 78 kOhm（76k 仍守住 99.78uA，80k 掉到 96.36uA）
%                       BONE_P=3.3V 时约 30.5 kOhm（30k 守住 99.75uA，32k 掉到 94.23uA）
%     母线升到 12V 不提高这个上限（BONE_P 被 8V LDO 钉住）。
%
% 关键性质：顺从区内 I_bus 与骨阻无关（实测 10k..76k，164.801uA 一位数字都不变）。
%   只有骨阻大到顶出顺从区，母线电流才跟着掉，且与 I_bone 一比一同步下降。
%
% 适用与限制（详见同目录 README.md）：
%   * 8V/3.3V 两颗 LDO 与 TVS 是自制近似模型：直流电流收支可信，dropout 精确位置、
%     LDO 稳定性与保护行为不可信。真实 MCP1703A 在 3.3V 输入时已进 dropout，
%     故 V_bus 略高于 3.3V 时实际电流会比本模型低一些。
%   * 只标定在标称元件值上（1% 电阻容差、Vth 离散、温度未做corner）：R10 或 R5/R7
%     各 1% 容差 → 恒流值 1% 误差（比例式，直接传递）。
%   * 动态部分在 VBUS 上只有 C5 1u + C6 100n = 1.1uF 输入电容。

if nargin < 2
    R_bone = 10e3;
end

R10 = 3e3;

V_bone_p = min(V_bus, 8.0016);
V_3v3    = min(V_bone_p, 3.3);

I_set   = max(V_3v3 / (11*R10) - 218e-9, 0);      % 恒流沉设定值（比例式，含 R9 误差）
I_limit = V_bone_p ./ (R_bone + R10);             % 顺从区外的纯电阻极限
I_bone  = min(I_set, I_limit);

I_bus = I_bone + V_bone_p/666.8e3 + V_3v3/110e3 + 23.03e-6;
end
