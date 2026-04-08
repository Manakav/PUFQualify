# PUF Hspice .mt0 输出分析工具

本项目用于对 PUF（硬件不可克隆函数）在 Hspice 仿真后的输出电压序列进行离线分析，评估：

- 单片均匀性（Uniformity）
- 多片唯一性（Uniqueness）

当前判决门限固定为 0.5V：

- 电压 >= 0.5V 判为 1
- 电压 < 0.5V 判为 0

每个样本按 32bit 序列进行统计与对比。

## 功能说明

脚本会从 .mt0 文件中解析每条样本（index）对应的 32 个电压值，完成以下分析：

1. 二值化输出
- 按门限 0.5V 将电压序列转换为 32bit 序列。

2. 单片均匀性分析
- 统计每个样本中 1 和 0 的个数。
- 输出 balance_ratio = ones / 32。
- 计算与全零向量的相似度（代码中标注为样本内相似度），用于反映比特分布偏置情况。

3. 多片唯一性分析
- 对任意两片样本计算汉明距离 HD。
- 计算相似度 Similarity = 1 - HD / 32。
- 输出最相似和最不相似的样本对。
- 输出全体样本间平均相似度（代码打印为“多片唯一性”）。

## 指标与公式

设任意两片响应分别为 R_i、R_j，长度 N = 32，样本数为 k。

1. 归一化汉明距离：

Uniqueness = HD(R_i, R_j) / N

2. 全体平均唯一性（百分比形式）：

Uniqueness_avg(%) = (2 / (k * (k - 1))) * Σ(HD(R_i, R_j) / N) * 100%

3. 全体平均相似度：

Similarity_avg(%) = 100% - Uniqueness_avg(%)

说明：当前脚本最终输出的是样本间平均相似度百分比，用于直观观察“不同样本之间有多像”。

## 输入数据要求

- 输入文件默认是仓库根目录下的 R.mt0。
- 如果启动脚本时传入文件路径，则使用传入路径。
- 若未传参且默认文件不存在，脚本会尝试弹出文件选择窗口。

解析规则（与当前代码一致）：

- 忽略以下行：
	- 以 index、$、. 开头的行
	- 空行
- 对有效数据行要求列数至少为 36。
- 第 1 列解析为 index。
- 第 4 到第 35 列（共 32 列）解析为电压值。

## 运行方式

在项目目录执行：

```bash
python analyze_mt0.py
```

指定输入文件：

```bash
python analyze_mt0.py path/to/your_file.mt0
```

Windows 下也可将 .mt0 文件拖拽到exe可执行文件上运行。

## 运行输出

控制台会输出：

- 每个 index 的 32bit 二进制序列
- 每个样本的 1/0 个数与 balance_ratio
- 样本两两之间最相似 10 对（汉明距离最低）
- 样本两两之间最不相似 10 对（汉明距离最高）
- 全体样本间平均相似度（百分比）

## 环境依赖

- Python 3.8+

说明：当前版本核心分析逻辑已改为纯 Python 实现，不再依赖 `numpy/pandas`，可显著减小 PyInstaller 打包体积。

## 打包为 EXE

本项目已提供 PyInstaller 配置文件 `analyze_mt0.spec`，可直接按以下步骤打包。

1. 安装打包工具

```bash
pip install pyinstaller
```

2. 在项目根目录执行打包

```bash
python -m PyInstaller --noconfirm analyze_mt0.spec
```

3. 查看打包产物

- 生成的可执行文件路径：`dist/analyze_mt0.exe`
- 中间构建文件路径：`build/analyze_mt0/`

4. 运行方式

- 直接双击 `dist/analyze_mt0.exe`
- 或将 `.mt0` 文件拖拽到 `analyze_mt0.exe` 上运行

说明：当前脚本已在 EXE 模式下增加“按回车退出”提示，避免拖拽运行后窗口瞬间关闭。

体积优化说明（已在仓库配置中启用）：

- `analyze_mt0.spec` 已开启 `optimize=2` 与 `strip=True`
- 已在 `excludes` 中排除 `numpy/pandas/matplotlib`
- 保留 `upx=True`（需本机安装 UPX 才会生效）

## 项目文件

- analyze_mt0.py：主分析脚本
- R.mt0：示例/默认输入数据
- analyze_mt0.spec：PyInstaller 打包配置
- build/：打包过程输出目录

## 备注

- 当前判决门限为 0.5V，如需调整可修改代码中 threshold 参数默认值。
- 目前代码中的“样本内分析”以与全零向量的相似度来表征分布偏置，若后续需要可扩展为与理想 50% 分布目标的偏差分析。
