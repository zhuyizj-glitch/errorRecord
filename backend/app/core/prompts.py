"""AI 分析 Prompt 模板"""

ANALYZE_QUESTION_PROMPT = """你是一位经验丰富的教师，擅长分析学生的作业与试卷。

请分析这张图片，**按题号把每一道题分别拆出来**，返回 JSON 格式的分析结果。

【最重要：按题号拆分】
一张照片里通常有好几道题（例如第 10、11、12…题）。规则：

- **每个题号对应 questions 里的一项**。图中是第 10、11、12 题 → 数组里就有 3 项
- **同一题号下的多个小问算作同一道题，必须合并成一项**：
  例如第 21 题有 (1)(2)(3) 三个小问 → 只产出 **1 项**，
  把那三个小问的完整内容（含各自的括号与条件）都写进这一项的 question_text 里
- **绝对不要**把不同题号合并成一项
- **绝对不要**只输出第一道题就结束
- 如果整张图确实只有一道题，questions 就只有一项
- 如果图中某道题完全看不清，也要保留一项，在 question_text 里写明"无法识别"

【判断孩子是否做对】
- looks_correct：根据孩子的作答判断**看起来**对不对。
  这只是给家长参考的初判，后续会有人工复核。
  ⚠️ 一道题有多个小问时，**只要有任意一个小问做错，整道题就算 false**。
- has_correction：孩子这道题**有没有订正痕迹**（划掉重写、红笔修改、涂改等）。
  订正过的题即使最终答案是对的，也可能说明孩子原本没掌握 —— 这个信息家长需要知道。
- 有订正痕迹时，looks_correct 按**订正前**的作答判断。

【分析深度】
- 只有 looks_correct 为 false 的题，才需要认真填写 error_analysis（错因诊断）与 solution_steps
- looks_correct 为 true 的题，solution_steps 可以简短，error_analysis 填 null

【数学公式格式要求】
- 所有数学公式统一用 LaTeX：行内公式用 $...$ 包裹，独立成行的公式用 $$...$$ 包裹
- 分数：\\frac{3}{4}
- 乘方与下标：x^2、x_1
- 根号：\\sqrt{4}
- 希腊字母：\\alpha、\\beta、\\gamma、\\pi
- 乘除号：\\times、\\div
- 只有数学表达式才用 $...$ 包裹；纯文字（如"解方程""因为""所以"）不要包裹
- 每个公式的 $ 前后用空格或换行与普通文字隔开，避免粘连
- 保证 LaTeX 语法完整合法：\\frac、\\sqrt 等命令的花括号必须成对闭合

示例：
- 好："解方程 $x^2 - 5x + 6 = 0$，得 $x = 2$ 或 $x = 3$"
- 好："$15 \\div \\frac{3}{4} = 15 \\times \\frac{4}{3} = 20$"
- 差："解方程 x² - 5x + 6 = 0"（数学公式没用 $...$ 包裹）
- 差："15 ÷ 3/4 = 15 × 4/3 = 20"（数学公式没用 $...$ 包裹）

【学科判断】
根据题目内容判断它属于哪一门课，只能是以下九个之一：
语文、数学、英语、物理、化学、生物、政治、历史、地理
拿不准就填空字符串 ""，不要猜。

返回以下 JSON 结构（不要包含 markdown 代码块标记）：

{
  "subject": "数学",
  "questions": [
    {
      "number": "题号，如 10、11、12；图中没有标号就填空字符串",
      "looks_correct": true/false,
      "has_correction": true/false,
      "source_type": "手写题 | 印刷题 | 图片题 | 纯文本",
      "question_text": "这道题的题目文字（数学公式用 LaTeX）",
      "has_diagram": true/false,
      "diagram_description": "图形描述（如有）",
      "student_answer": {
        "detected": true/false,
        "text": "识别出的孩子作答内容（数学公式用 LaTeX）",
        "confidence": "high | medium | low"
      },
      "correct_answer": "正确答案（数学公式用 LaTeX）",
      "solution_steps": "解题过程（数学公式用 LaTeX，每步用换行分隔）",
      "error_analysis": {
        "error_point": "具体错在哪里",
        "error_type": "概念不清 | 计算错误 | 审题错误 | 知识遗忘 | 方法错误 | 粗心大意",
        "root_cause": "错误的根本原因分析",
        "suggestion": "针对性的学习建议"
      },
      "metadata": {
        "topic": "所属章节/知识点主题",
        "knowledge_points": ["知识点1", "知识点2"],
        "difficulty": "简单 | 中等 | 较难"
      },
      "confidence": "high | medium | low"
    }
  ]
}

补充说明：
- 没检测到孩子作答时，student_answer.detected 填 false，error_analysis 填 null
- looks_correct 为 true 的题，error_analysis 填 null
- 图片整体模糊无法识别时，confidence 设为 "low"，并在对应题目的 question_text 中说明"""


# ── v2.0 真题卷分析提示词（三形态模型，分学科，2026-11-17 校验定稿）──

# 历史时代轴词汇表（朝代/时期级，保证标签统一）
ERA_VOCAB = [
    "史前·文明起源", "夏", "商", "西周", "春秋", "战国", "秦", "西汉", "东汉",
    "魏晋南北朝", "隋", "唐", "五代十国", "宋", "元", "明", "清",
    "中国近代史", "中国现代史", "世界古代史", "世界近代史", "世界现代史",
]

# 政治必修1《中国特色社会主义》主题轴词汇表
POLITICS_THEMES = [
    "社会形态演进", "科学社会主义与新民主主义革命", "社会主义建设与改革开放", "新时代与中国梦",
]

# 各学科形态规则
_SUBJECT_RULES = {
    "数学": "全部为 independent 独立小题（选择/填空/解答），逐题打知识点标签（如「函数的奇偶性」「基本不等式」「集合交集运算」）。",
    "物理": "全部为 independent 独立小题，逐题打知识点标签。",
    "化学": "全部为 independent 独立小题，逐题打知识点标签。",
    "生物": "全部为 independent 独立小题，逐题打知识点标签。",
    "地理": "选择题若几小题共享同一则材料/图，归为一个 material_group（passage 写共享材料，sub_questions 写各小题，各自打知识点标签）；单独题用 independent；综合题为 material_group。知识点如「热力环流」「大气受热过程」「地球内部圈层」。",
    "语文": """分两类处理：
- 现代文阅读、文言文阅读、古代诗歌鉴赏 → passage 语篇整题：passage 写完整语篇原文，sub_questions 写各小题，rating 评整篇难度（简单/中等/较难），question_type 写「现代文阅读」「文言文阅读」「古代诗歌鉴赏」。这类**不需要**顶层知识点。
- 名篇名句默写 → independent，按篇目拆分（每个篇目一条），knowledge_points 写「《篇目名》默写」。
- 语言文字运用小题（标点/字形/病句/衔接/修辞）→ independent，knowledge_points 写具体考点（如「病句·搭配不当」「标点·引号特殊含义」）。
- **作文题不要输出，直接跳过。**""",
    "英语": """分两类处理：
- 阅读理解、七选五、完形填空、语法填空 → passage 语篇整题：passage 写完整语篇原文，sub_questions 写各小题，rating 评整篇难度，question_type 写「阅读理解」「七选五」「完形填空」「语法填空」。
- **子题双层打标**：语法填空的每个空，knowledge_points 写语法考点（如「定语从句·关系代词」「时态·现在完成时」「非谓语动词·过去分词」「词性转换」「介词」）；完形填空的每个空，knowledge_points 写词汇辨析类型（如「动词辨析」「名词辨析」「形容词辨析」「副词辨析」）。
- **听力题、书面表达（应用文/读后续写）不要输出，直接跳过。**""",
    "历史": """每道题打【时代 era + 事件知识点】双标签：
- era 从时代词汇表选（朝代/时期级）；跨时代题选主题所在的主时代。
- knowledge_points 写具体事件/制度（如「汉武帝·推恩令」「商鞅变法·军功爵制」「贞观之治」）。
- 单材料单题用 independent；几小题共享材料用 material_group；材料分析题为 material_group（子题各自打标）。""",
    "政治": """每道题打【主题 module + 知识点】双标签：
- 本卷属必修1《中国特色社会主义》，module 从主题词汇表选。
- knowledge_points 写具体考点（如「资本主义基本矛盾」「五四运动」「家庭联产承包责任制」「中国梦·人民主体」）。
- 单题用 independent；材料题为 material_group（子题各自打标）。""",
}

_COMMON_EXAM_SCHEMA = """
【数学公式格式】所有数学公式统一用 LaTeX：行内 $...$，独立成行 $$...$$；\\frac、\\sqrt、x^2、x_1、\\times、\\div 等命令花括号必须成对闭合；纯文字不要包裹。

【返回 JSON 结构】（不要包含 markdown 代码块标记）
{
  "subject": "学科（九门之一，拿不准填\\"\\")",
  "questions": [
    {
      "number": "题号或题组起始号",
      "question_form": "independent | material_group | passage",
      "question_type": "题型（单选/解答/阅读理解/完形填空/语法填空/文言文阅读/材料分析等）",
      "rating": "简单 | 中等 | 较难（仅 passage 必填）",
      "passage": "语篇或共享材料完整原文（material_group/passage 必填，含图形描述）",
      "question_text": "题目文字（independent 必填）",
      "correct_answer": "参考答案（independent）",
      "solution_steps": "解题分析（independent）",
      "topic": "章节/主题",
      "knowledge_points": ["知识点（independent 顶层）"],
      "era": "时代（历史必填，从词汇表选）",
      "module": "主题（政治必填，从词汇表选）",
      "difficulty": "简单 | 中等 | 较难",
      "sub_questions": [
        {"number":"子题号","question_text":"子题题目","correct_answer":"子题答案","solution_steps":"子题解析","knowledge_points":["子题知识点"],"era":"子题时代(历史)","module":"子题主题(政治)"}
      ]
    }
  ]
}

【通用规则】
- 按题号拆分，同题号多小问合并；material_group/passage 的各小题放进 sub_questions，不要拆成多个顶层项。
- 这是空白真题卷，没有学生作答，请你给出每道题的参考答案与解析；拿不准标注「答案待核对」，不要编造。
- 看不清的题保留并注明「无法识别」。
"""


def build_exam_prompt(subject: str, vocab: list[str]) -> str:
    """按学科组装真题分析提示词。

    vocab：库内已有知识点词汇表（注入提高标签复用率）。
    历史额外注入时代词汇表，政治额外注入主题词汇表。
    """
    rules = _SUBJECT_RULES.get(subject, "逐题打知识点标签；共享材料的题组用 material_group。")
    parts = [
        "你是一位经验丰富的教师，正在把一份往年真题卷数字化入库。请分析这张真题卷图片，返回 JSON。",
        f"\n【本卷学科】{subject}\n【形态规则】\n{rules}",
    ]
    if subject == "历史":
        parts.append("\n【时代词汇表】\n" + "、".join(ERA_VOCAB))
    if subject == "政治":
        parts.append("\n【主题词汇表（必修1《中国特色社会主义》）】\n" + "、".join(POLITICS_THEMES))
    if vocab:
        parts.append("\n【已有知识点词汇表】优先复用以下标签，确实没有再新建：\n" + "、".join(vocab[:200]))
    parts.append(_COMMON_EXAM_SCHEMA)
    return "\n".join(parts)
