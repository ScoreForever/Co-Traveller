import requests
import os
import json
from dotenv import load_dotenv

# 加载API.env中的环境变量
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../API.env'))

API_KEY = os.getenv("SILICON_API_KEY")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

def get_chat_response(messages, model_name=MODEL_NAME, api_key=API_KEY, api_url=API_URL):
    """
    通用大模型对话接口
    :param messages: 消息列表 [{"role": "system"/"user"/"assistant", "content": "..."}]
    :param model_name: 模型名称
    :param api_key: API密钥
    :param api_url: API地址
    :return: 大模型回复内容字符串
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model_name,
        "messages": messages
    }
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    # 读取GUI输出
    base_dir = os.path.join(os.path.dirname(__file__), '../../temp')
    gui_path = os.path.join(base_dir, "route_planning_GUIoutput.json")
    llm_path = os.path.join(base_dir, "route_planning_LLMoutput.json")
    with open(gui_path, "r", encoding="utf-8") as f:
        gui_data = json.load(f)

    departure = gui_data.get("departure", "")
    departure_date = gui_data.get("departure_date", "")
    destinations = gui_data.get("destinations", [])

    # 构造用户需求描述
    dest_desc = []
    for dest in destinations:
        place = dest.get("place", "")
        arrive_date = dest.get("arrive_date", "")
        dest_desc.append(f"{place}（{arrive_date}到达）")
    dest_str = "，".join(dest_desc)

    user_text = (
        f"我将于{departure_date}从{departure}出发，依次前往{dest_str}。"
        "请为每个到达城市自动推荐适合的旅行景点，并为整个行程生成详细的每日行程规划。"
        "请输出一个JSON数组，每个元素包含：date, time, location, activity, transport。"
        "所有键必须为英文，且顺序为date, time, location, activity, transport。"
        "请不要输出除JSON以外的内容。"
    )

    # 构造消息
    messages = [
        {"role": "system", "content": "你是一个专业的中文旅行规划助手，善于为用户自动推荐景点并生成详细行程。"},
        {"role": "user", "content": user_text}
    ]

    # 获取大模型回复
    response = get_chat_response(messages)

    # 尝试解析回复为JSON
    try:
        # 只提取第一个JSON数组
        json_start = response.find('[')
        json_end = response.rfind(']')
        if json_start != -1 and json_end != -1:
            plan_list = json.loads(response[json_start:json_end+1])
        else:
            plan_list = []
    except Exception as e:
        plan_list = []
        print(f"解析大模型回复为JSON失败: {e}")

    # 保证输出协议：所有键为英文且顺序为date, time, location, activity, transport
    def normalize_item(item):
        key_map = {
            "日期": "date",
            "date": "date",
            "时间": "time",
            "time": "time",
            "地点": "location",
            "location": "location",
            "活动": "activity",
            "activity": "activity",
            "交通": "transport",
            "transport": "transport"
        }
        return {
            "date": item.get("date") or item.get("日期", ""),
            "time": item.get("time") or item.get("时间", ""),
            "location": item.get("location") or item.get("地点", ""),
            "activity": item.get("activity") or item.get("活动", ""),
            "transport": item.get("transport") or item.get("交通", "")
        }

    normalized_plan = [normalize_item(i) for i in plan_list if isinstance(i, dict)]

    # 写入LLM输出文件
    with open(llm_path, "w", encoding="utf-8") as f:
        json.dump(normalized_plan, f, ensure_ascii=False, indent=2)
    print(f"行程规划已保存至: {llm_path}")

if __name__ == "__main__":
    main()