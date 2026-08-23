import type { Chapter, Character, Idea, Material, Project, ReviewIssue } from '../contracts/ui'

export const projects: Project[] = [
  { id: 'mist', title: '迷雾之城', subtitle: '迷雾笼罩港口，新的线索正在浮现。', chapter: 18, words: 2341, updated: '今天 14:32', status: '正在写作', art: 'city' },
  { id: 'moon', title: '月影回声', subtitle: '构思阶段，正在完善世界观与人物设定。', chapter: 7, words: 1732, updated: '昨天 21:15', status: '草稿中', art: 'desk' },
  { id: 'harbor', title: '旧港档案', subtitle: '资料收集中，整理线索与背景设定。', chapter: 4, words: 2105, updated: '3 天前 19:40', status: '已暂停', art: 'mountains' },
  { id: 'mirror', title: '镜塔', subtitle: '灵感记录与片段收集阶段。', chapter: 3, words: 1089, updated: '5 天前 16:28', status: '构思中', art: 'city' },
]

const prose = `雨丝敲在车窗上，细碎而绵长，像是港城在低声诉说着过往。\n\n林砚靠在靠窗的位置，目光越过氤氲的玻璃，望向那片在雾中若隐若现的旧城区。这里曾是港城最繁华的码头区，如今却被时代的潮水一点点冲刷，只留下斑驳的砖墙与锈蚀的铁轨，静静沉在时光的底部。\n\n车子驶入老码头的巷道，路面湿滑，倒映着昏黄的路灯。巷子两旁是低矮的仓库和斑驳的木窗。空气里混合着海水、铁锈与潮湿木材的气味。\n\n“你确定线索就在这里？”副驾驶的沈夜收起伞，望着前方的老建筑。\n\n林砚点点头，从背包里取出一张褪色的照片。照片上，一群穿着厚大衣的人站在同一处码头，背景是一艘蒸汽轮船。\n\n照片的边缘写着一行字：“一九四三年，港城码头，送别。”\n\n沈言沉默片刻，目光落在远处一座废弃的仓库上，屋顶半塌，墙面被爬山虎覆盖。“或许，我们可以从那里开始。”`
export const chapters: Chapter[] = [
  { id: 'p', title: '序章　迷雾初现', words: 1732, content: prose, done: true },
  { id: '17', title: '第17章　风雨将至', words: 2105, content: prose, done: true },
  { id: '18', title: '第18章　港城旧影', words: 2341, content: prose },
  { id: '19', title: '第19章　潮声人影', words: 2812, content: prose },
  { id: '20', title: '第20章　隐秘潮汐', words: 3201, content: prose },
  { id: '21', title: '第21章　暗夜来客', words: 2904, content: prose },
  { id: '22', title: '第22章　黎明前夕', words: 0, content: '' },
]

export const materials: Material[] = [
  { id: 'm1', title: '《百年孤独》', type: '参考作品', status: '已学会', date: '2024-05-12', summary: '叙事结构与时间组织参考。', knowledge: ['循环时间与家族叙事', '克制的魔幻现实笔触', '群像关系的递进'] },
  { id: 'm2', title: '京都城市风貌参考', type: '参考素材', status: '整理完成', date: '2024-05-08', summary: '城市空间、街巷与建筑资料。', knowledge: ['城市结构与阶层', '空间动线设计', '场景感官细节'] },
  { id: 'm3', title: '赛博朋克都市风格研究', type: '专题研究', status: '处理中', date: '2024-05-13', summary: '视觉风格与社会结构专题。', knowledge: ['霓虹色彩与雨雾氛围', '垂直阶层与贫富分化', '技术异化与反抗主题'] },
  { id: 'm4', title: '唐诗中的自然意象', type: '专题研究', status: '需要处理', date: '2024-05-05', summary: '自然意象与情绪表达。', knowledge: ['意象映射情绪', '季节与时间感', '留白与余韵'] },
  { id: 'm5', title: '《边城》人物关系图谱', type: '参考素材', status: '已学会', date: '2024-04-28', summary: '人物关系与地域伦理。', knowledge: ['含蓄的人物关系', '地域伦理结构', '悲剧伏笔'] },
]

export const seedIdeas: Idea[] = [
  { id: 'i1', kind: '场景', content: '雨后傍晚的天台，城市霓虹刚亮起。一只橘猫跳上生锈的栏杆，回头看了我一眼，然后消失在管道阴影里。', note: '可从橘猫的视角展开一段奇遇。', time: '今天 11:28', used: false },
  { id: 'i2', kind: '对白', content: '“你总是把责任扛在肩上，可谁来问过你，想不想放下？”', note: '适合作为人物冲突的引爆点。', time: '今天 10:05', used: false },
  { id: 'i3', kind: '链接', content: '20个提升小说画面的细节技巧', note: '提炼关键技巧，可直接用于场景描写。', time: '昨天 21:43', used: true },
  { id: 'i4', kind: '场景', content: '老旧的钟表店，墙上挂满停摆的时钟。只有角落里的那座，会在雨夜发出轻微的走动声。', note: '可围绕“时间异常”展开悬疑故事。', time: '昨天 18:22', used: false },
  { id: 'i5', kind: '链接', content: '色彩情绪对照表：用颜色传递氛围与情绪', note: '参考配色，快速营造画面感。', time: '昨天 16:09', used: false },
  { id: 'i6', kind: '文件', content: '角色设定：林远初稿', note: '可补充人物背景与动机。', time: '前天 23:50', used: false },
]

export const characters: Character[] = [
  { id: 'lin', name: '林砚', role: '主角', identity: '雾港报社记者', status: '追查第18章事件的真相', relation: '苏晚晴（青梅竹马）、陆沉（旧识 / 对立）', note: '沉默寡言，观察力敏锐，背负家族旧案的秘密。', color: '#326cff' },
  { id: 'su', name: '苏晚晴', role: '协助调查', identity: '雾城图书馆管理员', status: '协助林砚调查古籍线索', relation: '林砚（青梅竹马）、陆沉（曾合作）', note: '理性细腻，擅长解读古老文本与隐秘线索。', color: '#20b681' },
  { id: 'lu', name: '陆沉', role: '正义执着', identity: '港务局特别调查官', status: '受命调查港口异动，与林砚立场冲突', relation: '林砚（旧识 / 对立）、苏晚晴（曾合作）', note: '行事果断，信奉秩序与规则。', color: '#7b61ff' },
  { id: 'shen', name: '沈夜', role: '信息提供者', identity: '情报贩子', status: '用线索换取利益', relation: '林砚（利益交换）', note: '身份成谜，熟悉港城地下网络。', color: '#111827' },
  { id: 'cheng', name: '程雾', role: '关键知情者', identity: '旧书店店主', status: '掌握旧案碎片', relation: '林砚（旧识）', note: '温和克制，似乎隐瞒重要往事。', color: '#dd8b31' },
]

export const reviewIssues: ReviewIssue[] = [
  { id: 'r1', category: 'priority', title: '情节连续冲突', detail: '第18章与第11章在同一事件的因果与结局上存在冲突。', count: 2, resolved: false, open: true },
  { id: 'r2', category: 'priority', title: '长期未解决的线索', detail: '存在 2 条线索已出现超过 15 章，未见后续进展。', count: 2, resolved: false, open: false },
  { id: 'r3', category: 'priority', title: '人物出场不一致', detail: '角色“林远”在 2 个章节的出场时间存在不一致。', count: 1, resolved: false, open: false },
  { id: 'r4', category: 'watch', title: '时间线贴合度', detail: '部分章节的时间顺序间隔较短，建议确认是否符合设定。', resolved: false, open: true },
  { id: 'r5', category: 'watch', title: '设定一致性', detail: '部分设定在不同章节的表达略有差异，建议统一。', resolved: false, open: false },
  { id: 'r6', category: 'watch', title: '命名统一性', detail: '个别专有名词存在多种写法，建议统一规范。', resolved: false, open: false },
  { id: 'r7', category: 'clear', title: '世界观设定', detail: '核心世界观设定保持一致。', resolved: true, open: false },
  { id: 'r8', category: 'clear', title: '主要人物关系', detail: '主要人物关系与设定保持一致。', resolved: true, open: false },
  { id: 'r9', category: 'clear', title: '章节衔接', detail: '章节之间的衔接自然流畅。', resolved: true, open: false },
]
