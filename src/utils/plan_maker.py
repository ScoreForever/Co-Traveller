import os
import json
from dotenv import load_dotenv
import requests

# 加载API.env中的环境变量
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../API.env'))

API_KEY = os.getenv("SILICON_API_KEY")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

def get_chat_response(messages, model_name):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model_name,
        "messages": messages
    }
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"

def read_plan_table(llm_path):
    """
    读取route_planning_LLMoutput.json（或jsonl/伪jsonl），返回表格内容字符串和结构化数据
    支持每行一个json对象的情况（即使扩展名为.json）
    """
    table_rows = []
    table_md = ""
    # 判断是否为jsonl或每行一个json对象的json
    with open(llm_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        f.seek(0)
        try:
            # 尝试整体解析为json数组
            data = json.load(f)
            if isinstance(data, list):
                table_rows = data
            else:
                raise ValueError("旅行规划文件格式错误")
        except json.JSONDecodeError:
            # 回退为每行一个json对象
            f.seek(0)
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                table_rows.append(row)
    # 生成Markdown表格
    headers = ["日期", "时间", "地点", "活动", "交通"]
    table_md += "| " + " | ".join(headers) + " |\n"
    table_md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in table_rows:
        table_md += "| " + " | ".join([
            str(row.get("date", "") or row.get("日期", "")),
            str(row.get("time", "") or row.get("时间", "")),
            str(row.get("location", "") or row.get("地点", "")),
            str(row.get("activity", "") or row.get("活动", "")),
            str(row.get("transport", "") or row.get("交通", "")),
        ]) + " |\n"
    return table_md, table_rows

def main():
    # 路径准备
    temp_dir = os.path.join(os.path.dirname(__file__), '../../temp/travel_plans')
    llm_path = os.path.join(temp_dir, "route_planning_LLMoutput.json")
    if not os.path.exists(llm_path):
        llm_path = llm_path.replace(".json", ".jsonl")
    if not os.path.exists(llm_path):
        print("未找到旅行规划文件")
        return

    # 读取旅行规划表格
    table_md, table_rows = read_plan_table(llm_path)

    # 构建大模型提示词
    system_prompt = (
        "你是一个专业的AI旅行助手，请根据用户的旅行日程表，生成一份详细、美观、实用的旅行攻略。"
        "攻略应包括每日亮点、推荐景点、餐饮建议、注意事项等，语言生动、排版美观，适合直接给用户阅读。"
        "正文请用中文，避免冗余开头和结尾。"
        "请充分利用表格中的信息，合理串联每日行程，适当补充背景介绍和实用建议。"
        "正文后请保留“交通”“附录”两个板块，内容可先留空或简单说明，后续将补充导航、地图等元素。"
    )

    # 将表格内容作为用户输入
    user_content = (
        "以下是用户的旅行日程表，请基于此生成攻略：\n\n"
        + table_md +
        "\n\n请严格按照上述表格内容生成攻略。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    print("正在生成旅行攻略，请稍候...\n")
    ai_response = get_chat_response(messages, MODEL_NAME)

    # 拼接最终Markdown内容
    md_path = os.path.join(temp_dir, "tourGuide.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(ai_response)
        f.write("\n\n")
        f.write("## 交通\n\n（本节后续将补充导航、地图等内容）\n\n")
        f.write("## 附录\n\n（本节后续将补充相关附录内容）\n")
    print("AI旅行攻略已保存至 tourGuide.md")

if __name__ == "__main__":
    main()