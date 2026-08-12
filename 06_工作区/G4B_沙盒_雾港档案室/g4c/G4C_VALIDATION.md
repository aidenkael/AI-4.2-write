# G4-C 验证报告

## 结果

- `KnowledgeRetrieve` 已真实运行：`--list-books` 与 `--stats` 均成功，加载《一九八四》498 条、《三体》653 条，共 1151 条。
- Q1/Q2/Q3 均以原问题真实运行，均为 `OK` / 15 candidates；原始输出保存在 `retrieval/`。
- Q1 选 State 约 5 组、BKP 2 条；Q2 选 State 约 5 组、BKP 2 条；Q3 选 State 约 4 组、BKP 2 条。每份 Context 都显著小于全量 Intent、State 和 1151 条 BKP。

## 选择质量

- Q1 有帮助的是《一九八四》的可观察自我保护/受限行动；《三体》的文明尺度选择条目是关键词噪音。
- Q2 有帮助的是《三体》的信息分层与命名不定义；远期统一回收和文明责任条目不适用。
- Q3 有真实跨书互补：`M2` 提供信息差，`F1` 提供私人反应的可见刻度；没有可称为跨书共识的结论，也没有需要调和的冲突。
- 三个 Context 的候选方向分别改变人物行动、揭示梯度、读者信息/情绪位置，非换措辞。

## 边界与检查

- 发现 BKP gap：亲属哀伤/内疚的具体机制、其与揭示阶梯及读者弧线的直接支持不足；已原样标注，未硬凑。
- 无必须升级 Retrieval 的阻塞性问题。Q1 高排噪音与条目 scope/boundary 缺失是可记录局限，不阻止最小 Context 的语义选择。
- 未修改 `author_intent.md`、`story_state.yaml` 或 `briefs/brief-001.md`；任务前后 `story_state.yaml` SHA256 均为 `28836F64F1C186DAB13A17A425087419FE239A3CF3B786A364F0D7300757F1CF`。
- 三份 Context 均为 `authority: derived_context_only`，没有把 BKP、候选方向或未决定谜底写成 Canon；没有进入 G4-D。

## 结论

`G4-C 技术验证完成候选`：真实 Retrieval、少量语义筛选和 Context/Synthesis 能覆盖三类问题；等待作者确认，不自动进入 G4-D。
