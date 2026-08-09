# B02-G Round 2A｜正式揭盲记录 v0.1

> 日期：2026-08-10
> 状态：**正式揭盲完成。** 本文件为 tracked 文件，记录机械事实，不含质量评价。

---

## 一、揭盲时间

2026-08-10

## 二、Mapping SHA256

`329a4b97f222f527998031476741b8f48dddd9d17980e8613683b8711419d23f`

来源文件：`blind_map_presealed_r2a.json`（Local Only）
封存记录：`B02_G_Round2A_blind_map_seal_v0.1.md`（tracked）

SHA256 校验通过：重新计算值与正式 run 前封存值完全一致，mapping 文件在生成后未被修改。

## 三、各组 A/B/C → condition 映射

### G1（任务 T4 · 亲密关系 · 隐瞒与信任压力 · Repetition 1）

- A = M2
- B = D0
- C = M1

### G2（任务 T4 · 亲密关系 · 隐瞒与信任压力 · Repetition 2）

- A = D0
- B = M1
- C = M2

### G3（任务 T5 · 身份与利益 · 合伙人信任危机 · Repetition 1）

- A = M2
- B = D0
- C = M1

### G4（任务 T5 · 身份与利益 · 合伙人信任危机 · Repetition 2）

- A = M1
- B = M2
- C = D0

## 四、声明

1. **作者评审在揭盲前已封存。** 封存记录：`author_blind_review_record_r2a_SEALED.md`，封存 SHA256：`0f604478484b86d511246086311ff24a41533e6a375c2f1e62da2e3a149018c0`。
2. **Controller 独立判断在揭盲前已完成。**
3. **外部 AI 独立评审也在揭盲前完成。**
4. **旧 mapping 已因 `PRE_RUN_MAPPING_EXPOSURE` 正式作废。** 本文件只使用正式 run 前重新封存的新 mapping（上述 SHA256），不涉及已作废的旧 mapping。
5. 本文件只记录揭盲的机械事实（mapping 对应关系），不包含任何 condition 胜出判断、作者偏好统计、Controller 偏好统计、外部 AI 多数票、正文评价、机制有效性判断或下一轮实验建议。
