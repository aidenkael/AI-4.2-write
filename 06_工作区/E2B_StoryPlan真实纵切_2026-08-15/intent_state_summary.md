# E2-B Intent / Story State 摘要

> 一次性实验数据，不属于正式 Story State。更新时间：2026-08-15。
> 完整 JSON：`author_intent.json`（Intent）、`story_state.json`（Story State）。

## Author Intent（intent_rev=1，project: e2b-sea-road）

- **work_direction**：沿海县城跨海旧路关闭前一年，经营家族小型物流站的宋宁，与失联十年后归来、代表区域物流公司竞标大宗配送合同的姐姐宋乔，在现实合作与利益对立之间被不断推向无法两全的选择。
- **reader_promise**：读者看到一个正在消失的地方性运输生态，如何不断逼迫两姐妹做出越来越无法两全的选择；家庭旧债不是单纯谜底，而要持续改变她们今天的关系和利益。
- **hard_constraints**：不写大公司黑幕阴谋；不靠凶杀案升级剧情；不出现豪门身份反转；不使用超自然；不把父亲塑造成隐藏巨恶；冲突主要来自生计、家庭旧债、不同人生选择、地方变化和人物自己做出的决定。
- **open_space**（= deliberate open space，见下）。

## Story State（state_rev=1）

### canon_facts（4 条，authority 全部 `manual_import:e2b-seed`）

1. 沿海县城将在一年后永久封闭一条连接本岛与旧港区的跨海旧路。
2. 37 岁的宋宁经营父亲留下的小型物流站，长期靠这条旧路给岛上的商户、住户和小工厂送货。
3. 失联十年的姐姐宋乔突然回来，并代表一家新的区域物流公司竞标岛上未来唯一的大宗配送合同。
4. 父亲去世前留下过一笔来源和用途都说不清的债。

### character_state（2 条）

- 宋宁认为姐姐当年的离开和这笔债有关。
- 宋乔拒绝解释当年的离开，却坚持父亲留下的物流站已经没有继续存在的价值。

### relationship_state（1 条）

- 随着旧路关闭日期逼近，两姐妹既不得不合作处理现实问题，又越来越可能站到彼此利益的对立面。

### occurred_events / open_threads

- 均空（种子没有任何已发生情节）。

### approved_plan（1 条，作者已确认的 StoryDesign 方向）

- `plan.design.direction.island`（authority `author_decision:storydesign-simulated`，occurred=false）：
  - 旧路关闭形成一年倒计时；
  - 姐妹代表两种不同生存方案；
  - 每解决一个现实物流问题，都让双方合作更必要，同时利益冲突更明显；
  - 父亲旧债持续进入现实选择，但真相未确定。

## Deliberate open space（不得写入 Canon）

- 父亲那笔债真正的用途；
- 姐姐十年前离开的全部原因；
- 姐姐这次回来是否还有未说出口的私人目的；
- 姐妹最终合作、决裂还是形成第三种关系；
- 物流站最终是否保留。

以上五项只记录在 Plan Brief 的 `deliberate_open_space` 中，未出现在任何 Canon 区域。
