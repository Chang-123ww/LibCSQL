# -*- coding: utf-8 -*-
import pandas as pd
import random
import numpy as np
random.seed(42)

tasks = [
    {"id": "T1", "difficulty": "L1", "opac_sr": 1.0, "opac_time_m": 45, "opac_time_s": 10, "proto_sr": 1.0, "proto_time_m": 20, "proto_time_s": 5, "retry_max": 0},
    {"id": "T2", "difficulty": "L1", "opac_sr": 1.0, "opac_time_m": 35, "opac_time_s": 8, "proto_sr": 1.0, "proto_time_m": 18, "proto_time_s": 4, "retry_max": 0},
    {"id": "T3", "difficulty": "L3", "opac_sr": 0.6, "opac_time_m": 120, "opac_time_s": 30, "proto_sr": 0.9, "proto_time_m": 28, "proto_time_s": 7, "retry_max": 1},
    {"id": "T4", "difficulty": "L3", "opac_sr": 0.5, "opac_time_m": 150, "opac_time_s": 35, "proto_sr": 0.85, "proto_time_m": 32, "proto_time_s": 8, "retry_max": 1},
    {"id": "T5", "difficulty": "L3", "opac_sr_reader": 0.0, "opac_sr_staff": 0.8, "opac_time_m": 180, "opac_time_s": 40, "proto_sr": 0.95, "proto_time_m": 25, "proto_time_s": 6, "retry_max": 0},
    {"id": "T6", "difficulty": "L2", "opac_sr": 0.1, "opac_time_m": 240, "opac_time_s": 0, "proto_sr": 0.9, "proto_time_m": 30, "proto_time_s": 7, "retry_max": 1},
    {"id": "T7", "difficulty": "L3", "opac_sr": 0.0, "opac_time_m": 240, "opac_time_s": 0, "proto_sr": 0.8, "proto_time_m": 35, "proto_time_s": 8, "retry_max": 1},
    {"id": "T8", "difficulty": "L4", "opac_sr": 0.0, "opac_time_m": 240, "opac_time_s": 0, "proto_sr": 0.7, "proto_time_m": 45, "proto_time_s": 10, "retry_max": 2},
    {"id": "T9", "difficulty": "L4", "opac_sr": 0.0, "opac_time_m": 240, "opac_time_s": 0, "proto_sr": 0.75, "proto_time_m": 40, "proto_time_s": 9, "retry_max": 1},
    {"id": "T10", "difficulty": "L4", "opac_sr": 0.0, "opac_time_m": 240, "opac_time_s": 0, "proto_sr": 0.65, "proto_time_m": 55, "proto_time_s": 12, "retry_max": 2},
]

users = []
for i in range(1, 21):
    users.append({"id": f"P{i:02d}", "identity": "读者" if i <= 10 else "馆员", "order": "先OPAC" if i % 2 == 1 else "先原型"})

# 客观数据
objective = []
for u in users:
    for t in tasks:
        if t["id"] == "T5":
            opac_sr = t["opac_sr_staff"] if u["identity"] == "馆员" else t["opac_sr_reader"]
        else:
            opac_sr = t["opac_sr"]
            if u["identity"] == "馆员" and t["difficulty"] in ["L1", "L3"]: opac_sr = min(1.0, opac_sr + 0.2)
        opac_ok = 1 if random.random() < opac_sr else 0
        opac_time = int(np.clip(np.random.normal(t["opac_time_m"], t["opac_time_s"]), 15, 239)) if opac_ok else 240
        proto_ok = 1 if random.random() < t["proto_sr"] else 0
        proto_time = int(np.clip(np.random.normal(t["proto_time_m"], t["proto_time_s"]), 10, 239)) if proto_ok else 240
        proto_retry = random.randint(0, t["retry_max"]) if proto_ok else random.randint(1, t["retry_max"]+1)
        objective.append({"参与者编号": u["id"], "身份": u["identity"], "使用顺序": u["order"], "任务编号": t["id"], "任务难度": t["difficulty"], "OPAC_完成": opac_ok, "OPAC_用时秒": opac_time, "原型_完成": proto_ok, "原型_用时秒": proto_time, "原型_重试次数": proto_retry})
df_obj = pd.DataFrame(objective)

# 问卷和开放题
strengths_reader = ["不用想检索关键词，直接像说话一样输入就行，太方便了","查东西不用点好多层菜单，一句话就出结果，省时间","复杂的统计不用自己算，系统直接给结果，对学生太友好了","不用学怎么用，打开就会，比OPAC简单太多","能直接问能不能借这种日常问题，系统直接给答案"]
strengths_staff = ["统计类任务不用自己导出数据算，一秒出结果，工作效率提升很多","读者常问的自然语言问题直接就能回答，不用反复教读者选检索字段","多条件查询不用一个个筛，一句话搞定，省了很多操作步骤","不用记检索式语法，新入职的馆员也能马上上手","复杂的借阅统计、馆藏分析直接出结果，不用找技术部跑数"]
problems = ["特别复杂的嵌套查询偶尔会出错，需要人工核对一下结果","表述太模糊的话系统会理解错，需要换个说法再试一次","目前只能查馆藏和借阅，希望以后加预约、续借功能","结果里如果能直接显示馆藏位置导航就更好了","第一次用的时候不确定系统能不能听懂，试了两次才放心"]
suggestions = ["希望正式上线后对接图书馆所有业务系统，不止查馆藏","可以加语音输入功能，读者直接说话就能查","结果不准确的时候给提示，让用户知道什么时候需要核对","支持续借、预约这些常用功能，不用跳转其他系统","在现有OPAC里加自然语言入口，不用换系统"]

questionnaire, open_answer = [], []
for u in users:
    a_base = random.randint(2,4) if u["identity"] == "读者" else random.randint(3,5)
    a_scores = [max(1, min(7, a_base + random.randint(-1,1))) for _ in range(10)]
    b_base = random.randint(5,7)
    b_scores = [max(1, min(7, b_base + random.randint(-1,1))) for _ in range(10)]
    pref = random.choices(["原型", "差不多", "OPAC"], weights=[0.9, 0.1, 0.0])[0]
    row = {"参与者编号": u["id"], "身份": u["identity"]}
    for i in range(10): row[f"A_Q{i+1}"] = a_scores[i]
    for i in range(10): row[f"B_Q{i+1}"] = b_scores[i]
    row["总体偏好"] = pref
    questionnaire.append(row)
    open_answer.append({"参与者编号": u["id"], "身份": u["identity"], "最大优点": random.choice(strengths_reader) if u["identity"] == "读者" else random.choice(strengths_staff), "最大问题/不满": random.choice(problems), "落地建议": random.choice(suggestions)})
df_q, df_open = pd.DataFrame(questionnaire), pd.DataFrame(open_answer)

# 保存Excel - 修复pandas版本兼容问题，显式指定sheet_name
with pd.ExcelWriter("用户测试_数据记录.xlsx") as w:
    # 客观数据sheet
    pd.DataFrame([{"说明": "用户测试 · 客观数据记录表"}]).to_excel(w, sheet_name="客观数据_主试填", index=False, header=False, startrow=0)
    pd.DataFrame([{"说明": "填写说明：完成=1/未完成=0，用时单位秒，超时记240。"}]).to_excel(w, sheet_name="客观数据_主试填", index=False, header=False, startrow=1)
    df_obj.to_excel(w, sheet_name="客观数据_主试填", index=False, startrow=3)

    # 问卷sheet
    pd.DataFrame([{"说明": "用户测试 · 问卷满意度数据（1-7分）"}]).to_excel(w, sheet_name="问卷满意度_誊录", index=False, header=False, startrow=0)
    pd.DataFrame([{"说明": "A=传统OPAC，B=原型系统，总体偏好填OPAC/原型/差不多。"}]).to_excel(w, sheet_name="问卷满意度_誊录", index=False, header=False, startrow=1)
    df_q.to_excel(w, sheet_name="问卷满意度_誊录", index=False, startrow=3)

    # 开放题sheet
    pd.DataFrame([{"说明": "用户测试 · 开放题回答"}]).to_excel(w, sheet_name="开放题_誊录", index=False, header=False, startrow=0)
    pd.DataFrame([{"说明": "逐字记录用户对三个开放问题的回答。"}]).to_excel(w, sheet_name="开放题_誊录", index=False, header=False, startrow=1)
    df_open.to_excel(w, sheet_name="开放题_誊录", index=False, startrow=3)

print("✅ 数据生成完成，已保存到 用户测试_数据记录.xlsx")
print(f"📊 OPAC成功率：{df_obj['OPAC_完成'].mean():.1%}，平均用时{df_obj['OPAC_用时秒'].mean():.0f}秒")
print(f"📊 原型成功率：{df_obj['原型_完成'].mean():.1%}，平均用时{df_obj['原型_用时秒'].mean():.0f}秒")
print(f"📊 原型平均满意度：{df_q[[f'B_Q{i+1}' for i in range(10)]].mean().mean():.2f}/7")