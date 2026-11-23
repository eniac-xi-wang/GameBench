# 用游戏素材播放已有评测

这些工具读取已经结束的评测，只生成观看用的文件。可以给其他人一个 HTML，或给安装了 Mindustry 的人一个存档。它们不调用模型。各命令均从本仓库根目录运行，输出文件使用新名字。

| 游戏 | 观看方式 | 本地需要什么 |
| --- | --- | --- |
| 2048 | 原版网页棋盘、移动与合并动画。回放逐步使用记录里的新方块，并核对每步棋盘和得分。 | 放在 `2048/` 的固定版本源码，含 `index.html`、`js/`、`style/` 和 `LICENSE.txt` |
| shapez | 浏览器中以原版运输、加工逻辑重跑蓝图，使用原游戏建筑、传送带和颜色 PNG，以及原游戏的形状绘制函数。支持播放、倍速和拖动。 | 放在 `shapez/` 的固定版本源码，含 `res_raw/sprites/`，以及评测准备阶段编译的引擎 |
| Mindustry | 把已摆放好的工厂导入桌面游戏，从第一个生产 tick 前开始运行，可以移动视角、查看建筑。 | 导出端需要该任务的 JDK 和固定版服务端；观看端安装 Mindustry v160.7 即可 |
| Pokémon Showdown | 打开单局 `engine/replays/game-…-animated.html`，官方播放器读取记录的对战日志。 | 动画页当前联网加载官方播放器和素材；同目录普通 HTML 支持离线逐回合查看 |

已有游戏 Git 仓库可以放在上述路径，也可以按主 README 使用 `GAMEBENCH_SOURCE_CACHE`。源码版本见 [固定提交](../benchmarks/upstream.json)。运行相应任务时，`./bench` 会准备依赖。2048 和 shapez 的导出命令还接受 `--game-dir /path/to/game`。游戏素材只在本地导出时读取，开源源码包只包含适配工具。

## 2048

假设 `engine` 是本次策略的引擎输出目录，选择其中一局：

```sh
python3 tools/replay_2048.py "$engine/games/game-0001.json" 2048-replay.html
```

在浏览器里打开 HTML。它内嵌该局动作和实际生成的方块，使用原版 GameManager 与 HTMLActuator。局内游戏得分和评测计分可能不同，例如策略在运行中途超限时。页面保留两种数值。

## shapez

使用 `./bench --tasks shapez-cut` 准备游戏素材和本地引擎，或直接使用已经配置好的工作树。选择含 `tasks.json`、`candidate/`、`records/` 和 `result.json` 的引擎目录：

```sh
python3 tools/replay_shapez.py "$engine" cut_rotate cut-replay.html
```

另外两关的名称是 `paint` 和 `stack`。HTML 内嵌所需图片和模拟代码，导出后可离线打开。游戏按 60 Hz 推进；观看时显示的交付数会与评测记录对照。地图背景、镜头和播放控件由回放页绘制。这个 HTML 适用于网页观看，桌面游戏的「导入存档」需要另一种格式。

## Mindustry

使用含 `task.json`、`blueprint.json` 和 `result.json` 的有效 v3 工厂评测目录：

```sh
python3 tools/mindustry_save.py "$engine" factory.msav
```

在桌面游戏 v160.7 中选择「开始游戏 → 加载游戏 → 导入存档」，选中 `factory.msav`，再加载新存档。无需安装模组。导出器捕获第零 tick 的地图、矿区、建筑、传送带和配置；它随后在一个新的官方服务端进程中读档，核对布局并推进到规定 tick，输出该次读档的产量。桌面端按自身的时间和建筑更新顺序运行，玩家也能修改工厂。正式成绩以原评测记录为准。
