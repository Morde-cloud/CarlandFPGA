# B v5研究交接检查点

COMP-20261013-DEEPEYE/v5。人类不可删改范围全部保留；B当前最优、双轴协议、全链路预算和资产验收研究已完成。本检查点的精确v4对照仍待A提供head/路径/hash，见[comparison_v4.md](comparison_v4.md)。本文件不是三机联合定案或产品验收。

|文件|用途|
|---|---|
|[review.md](review.md)|逐条范围读回、当前融合架构、保留/替换/冲突|
|[protocol.md](protocol.md)|双轴/权属/TTL、新ABI候选、全链路预算和真实IO回采|
|[assets_and_acceptance.md](assets_and_acceptance.md)|完整游戏资产、体积碰撞、整件穿圈、信息隔离和11验收卡|
|[handoff.md](handoff.md)|A新主会话与各独占实施会话交接、根书修改清单|
|[comparison_v4.md](comparison_v4.md)|待精确原稿后追加的模块差异，不虚构已读内容|
|[planning_checks.json](planning_checks.json)、[check_planning.py](check_planning.py)|可复算研究算术；脚本只读JSON，不运行产品|
|[sources.json](sources.json)、[evidence.md](evidence.md)|官方来源、支持边界、失败取证、主/子任务实际完成范围|
|[freeze.json](freeze.json)|本检查点UTF-8/LF原始字节、SHA256、时间与状态|

复核命令（仓库根目录）：

```text
python docs/competition/deepeye-2026/reviews/v5/b/check_planning.py
```

推荐完整3D Godot/Blender资产管线、B世界渲染与A AMD AI隔离部署、真实PYNQ PL观测处理、PC_DIRECT及FPGA_EXEC双合法分支。AI/传感模型以C最终证据为准；64点10Hz、1Mbps、2m立方体、80/88mm钻头/圈径及帧时都是待统一的工程候选，不是额外人类硬约束。

关键官方依据：[Godot发布标签](https://github.com/godotengine/godot/releases/tag/4.7.2-stable)只支持版本存在；[碰撞形状](https://docs.godotengine.org/en/stable/tutorials/physics/collision_shapes_3d.html)与[空间查询](https://docs.godotengine.org/en/stable/classes/class_physicsdirectspacestate3d.html)支持体积/初始重叠限制；[PYNQ DMA](https://pynq.readthedocs.io/en/v3.1/pynq_libraries/dma.html)支持PS与PL数据路径、TLAST约束；[VL53L5CX资料](https://www.st.com/resource/en/datasheet/vl53l5cx.pdf)限制测距条件，不能支持透岩读水或直接材质标签。来源不证明本项目已实现或达到性能。

产品、资产生成、模型、RTL、仿真、综合、实现、板测、系统性能、安装、采购均not_run。A唯一板操作；本轮不启动新产品会话。收到v4原文后只在本目录追加受影响项，不回改首轮/旧评析/A文件。
