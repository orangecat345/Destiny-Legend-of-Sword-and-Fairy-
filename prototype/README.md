# 《天问 · 回响之门》规则原型

这是本次新增的可玩试作场景，验证“探索 → 收集 → 战斗 → 有代价的回溯 → 分支结尾 → 存读档”流程。原作者《天问篇》正文当前未能读取，场景、台词、守影、回响系统及两种结尾均为新增设计，不声称复现原稿。

原型采用原版已核实的李剑灵一级气血 228、灵力 39，以及御刀术消耗 5 点灵力；战斗伤害和离散回合制为试验设计，并非原作完整公式或 ATB 复刻。数据来源位置记录在 [scenario.json](data/scenario.json) 的 `provenance` 中。

## 运行

使用 Python 3.11 或以上版本，在本目录执行：

```sh
python -m pip install -r requirements.txt
python main.py
```

Windows 版本使用系统自带的微软雅黑字体；Linux 可安装 Noto Sans CJK。当前固定窗口大小为 1280 × 800。

| 操作 | 按键 |
| --- | --- |
| 移动 | WASD 或方向键 |
| 与相邻石碑、人物、门交互 | E |
| 战斗中的挥刀、御刀术、守势、回溯 | 1 / 2 / 3 / 4，或点击按钮 |
| 结尾选择 | 1 / 2，或点击按钮 |
| 保存 / 读取 | F5 / F9 |
| 败退后重试 / 结尾后重新开始 | R |
| 退出 | Esc |

先找到三座石碑，再到南侧与守影交锋，最后前往北侧回响之门。对手第二轮及其后每三轮一次重击；守势可以减伤并恢复灵力。回溯只恢复上一轮战斗状态，消耗的一枚回响不会返还；保有三枚回响才能选择“守住旧约”。

存档位置为 Windows 的 `%LOCALAPPDATA%/TianwenPrototype/save.json`。原版游戏文件不参与原型运行，也不会被修改。

## 验证与打包

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python main.py --self-test ./work/smoke
python build_windows.py
```

`--self-test` 在无窗口模式下生成探索、战斗、结尾截图，并验证存读档与通关。Windows 打包产物位于 `dist/Tianwen-Prototype.exe`，运行不需要 Python。

本机未检测到可用 UE 编辑器，本次可执行产物为 pygame-ce 原型；[续作设计与 UE 移植方案](../docs/tianwen/game-design.md)记录后续实现边界。
