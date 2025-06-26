import requests
import os
import json
import time
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

def get_chat_response_stream(messages, model_name=MODEL_NAME, api_key=API_KEY, api_url=API_URL):
    """
    通用大模型对话接口（流式输出）
    :param messages: 消息列表 [{"role": "system"/"user"/"assistant", "content": "..."}]
    :return: 逐步yield大模型回复内容
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model_name,
        "messages": messages,
        "stream": True
    }
    try:
        with requests.post(api_url, headers=headers, json=data, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            buffer = ""
            for line in resp.iter_lines():
                if not line:
                    continue
                # 强制用utf-8解码每一行
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                if not line.startswith("data:"):
                    continue
                content = line[len("data:"):].strip()
                if content == "[DONE]":
                    break
                try:
                    chunk = json.loads(content)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta:
                        buffer += delta["content"]
                        # 尝试逐步解析JSON对象（假设每一行为一个JSON对象，或以换行分隔）
                        while True:
                            json_start = buffer.find('{')
                            json_end = buffer.find('}', json_start)
                            if json_start != -1 and json_end != -1:
                                try:
                                    obj = json.loads(buffer[json_start:json_end+1])
                                    yield obj
                                    buffer = buffer[json_end+1:]
                                except Exception:
                                    break
                            else:
                                break
                except Exception:
                    continue
    except Exception as e:
        yield {"error": str(e)}

def main():
    # 读取GUI输出（目录变更）
    base_dir = os.path.join(os.path.dirname(__file__), '../../temp/travel_plans')
    gui_path = os.path.join(base_dir, "route_planning_GUIoutput.json")
    llm_path = os.path.join(base_dir, "route_planning_LLMoutput.json")
    with open(gui_path, "r", encoding="utf-8") as f:
        gui_data = json.load(f)

    # 新输入协议：departure, departure_date, return_date, destinations:[{"place": ...}, ...]
    departure = gui_data.get("departure", "")
    departure_date = gui_data.get("departure_date", "")
    return_date = gui_data.get("return_date", "")
    destinations = gui_data.get("destinations", [])

    # 构造用户需求描述（包含返程日期）
    dest_desc = []
    for dest in destinations:
        place = dest.get("place", "")
        dest_desc.append(f"{place}")
    dest_str = "，".join(dest_desc)

    user_text = (
        f"我将于{departure_date}从{departure}出发，依次前往{dest_str}，{return_date}返程。"
        "请为每个到达城市自动推荐适合的旅行景点，并为整个行程生成详细的每日行程规划。"
        "请输出一个JSON数组，每个元素包含：date, time, location, activity, transport。"
        "所有键必须为英文，且顺序为date, time, location, activity, transport。并注意仅仅是键为英文，值必须是中文，因为你的用户是中国人。"
        "请不要输出除JSON以外的内容。"
    )

    # 构造消息
    messages = [
        {"role": "system", "content": "你是一个专业的中文旅行规划助手，善于为用户自动推荐景点并生成详细行程。"},
        {"role": "user", "content": user_text}
    ]

    # 仅保留流式获取大模型回复
    with open(llm_path, "w", encoding="utf-8") as f:
        for item in get_chat_response_stream(messages):
            if isinstance(item, dict) and not item.get("error"):
                # 保证输出协议
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
                normed = normalize_item(item)
                f.write(json.dumps(normed, ensure_ascii=False) + "\n")
                f.flush()
            elif isinstance(item, dict) and item.get("error"):
                print(f"流式大模型错误: {item['error']}")
    print(f"流式行程规划已保存至: {llm_path}")

if __name__ == "__main__":
    main()