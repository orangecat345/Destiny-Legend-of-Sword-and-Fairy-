# 《宿命篇》首轮静态分析结果

本目录由 [export_lcf.py](../../tools/export_lcf.py) 从用户提供的原版数据库、地图树和地图生成。使用官方 EasyRPG LCF2XML、`--2k3 --encoding CP936` 转换，293 个输入全部成功读取，原输入哈希未改变。

## 数据入口

| 文件 | 内容 |
| --- | --- |
| [summary.json](summary.json) | 输入、工具哈希、规模、起点与检查结果 |
| [maps.csv](maps.csv) | 291 张地图的名称、尺寸、父节点、事件及事件页数量 |
| [actors.csv](actors.csv)、[skills.csv](skills.csv)、[items.csv](items.csv)、[enemies.csv](enemies.csv) | 数据库槽位、原始 ID、名称和关键数值 |
| [switches.csv](switches.csv)、[variables.csv](variables.csv)、[commonevents.csv](commonevents.csv) | 状态定义与公共事件名称 |
| [event_pages.jsonl](event_pages.jsonl) | 地图、公共事件和战斗事件的指令、参数、缩进、条件与原始文本 |
| [dialogue.csv](dialogue.csv) | 合并连续消息指令的 5,931 个对话块，保留来源及命令范围 |
| [map_transfers.csv](map_transfers.csv) | 1,140 个直接地图跳转及目标坐标 |
| [state_references.csv](state_references.csv) | 页面条件、开关/变量控制与部分条件分支的状态引用 |
| [database_references.csv](database_references.csv) | 数据库中技能/物品到技能或开关的声明引用 |

`event_pages.jsonl` 的每行是一页事件。地图定位格式为 `Map编号/Event编号/Page编号`；指令序号从 1 开始。数据库槽位数包含空白和占位记录，不能直接当作有效角色或道具数量。导出的 RM 消息控制码仍保留，文本不是按剧情演出顺序排列。

对话和道具说明中的原有空格保持不变；这两份 CSV 不应用普通源码的行尾空格检查。CSV 文件关闭自动换行转换，以便重复生成时比较。

## 重新生成

从 [EasyRPG 官方工具页](https://easyrpg.org/tools/downloads/)取得 LCF2XML，确认其来源后，在仓库根目录运行：

```sh
python tools/export_lcf.py --converter PATH_TO_LCF2XML --xml-dir work/lcf-export/xml
```

工具不随仓库分发。记录于 `summary.json` 的本次转换器 SHA-256 为 `5822020672595ecc046a79be1ce7f3a4d76e33453575e271ea7c5dce6467ab8a`。指令名称表来自 [liblcf](https://github.com/EasyRPG/liblcf/blob/6854310c3432e553fd4ae672ce861899c80c3bd0/src/generated/lcf/rpg/eventcommand.h)，MIT 许可见 [LICENSE](../../tools/third_party/liblcf-LICENSE.txt)。

## 解释边界

- 转换成功与指令编号可识别，不等于所有运行时行为已经复现。
- 地图跳转表是条件约束下的静态候选边，不能直接当作剧情顺序或必然可达路径。
- 状态引用表尚不覆盖所有间接寻址、道具效果、移动路线编码与解释器行为；原始参数保留在事件索引中。
- 未运行原游戏；战斗公式、碰撞、事件页优先级、条件组合与两种结局仍需要原运行时验证。

已定位的启动链与隐藏结局条件见[逆向分析记录](../../docs/reverse-engineering.md)。
