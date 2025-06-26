import requests
import os
import json
from dotenv import load_dotenv  # 用于加载环境变量

# 加载API.env中的环境变量
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../API.env'))

# 配置信息
API_KEY = os.getenv("SILICON_API_KEY")  # 只从环境变量读取，不再硬编码
API_URL = "https://api.siliconflow.cn/v1/chat/completions"  # 替换为实际API地址
MODEL_NAME = "deepseek-ai/DeepSeek-V3"  # 如硅基的模型名称

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
        response.raise_for_status()  # 检查HTTP错误
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    # 读取../../temp/GUIoutput.json文件
    temp_dir = os.path.join(os.path.dirname(__file__), '../../temp')
    json_path = os.path.join(temp_dir, "GUIoutput.json")
    with open(json_path, "r", encoding="utf-8") as f:
        user_data = json.load(f)

    model_name = user_data.get("modelName", MODEL_NAME)
    budget = user_data.get("budget", "Medium")
    intensity = user_data.get("intensity", "Medium")
    user_text = user_data.get("userText", "")

    # 构建系统提示词，融合预算和强度
    prompt = (
        "你是一个体贴的AI旅行规划助手，请根据用户的需求提供旅行建议和行程安排。"
        "你需要给出一份完整的攻略，包括景点、交通、住宿、美食等信息。"
        "你可以根据用户的需求进行个性化推荐。"
        "你需要使用中文进行交流。"
        f"用户预算等级为：{budget}，旅行节奏为：{intensity}。"
        "（预算等级共有三级：Low、Medium、High；旅行节奏有三级：Relaxed、Medium、Intense）"
        "请直接输出旅行攻略正文，不要添加任何开头的说明、总结、客套语或结尾提示。但你的排版需要精美一些。"
    )

    # 初始化消息列表
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_text}
    ]

    print("正在生成旅行攻略，请稍候...\n")
    ai_response = get_chat_response(messages, model_name)
    # 生成到../../temp/tourGuide.md
    md_path = os.path.join(temp_dir, "tourGuide.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(ai_response)
    print("AI旅行攻略已保存至 tourGuide.md")

if __name__ == "__main__":
    main()