import os
import gradio as gr
import random
import datetime
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import gradio as gr
import requests
from datetime import datetime, timedelta
from pydub import AudioSegment 


def generate_travel_plan(place1, date1, place2, date2):
    """生成查票网址和旅行规划"""
    try:
        # 验证日期格式
        dep_date = datetime.strptime(date1, "%Y-%m-%d")
        ret_date = datetime.strptime(date2, "%Y-%m-%d")
        
        # 计算旅行天数
        days = (ret_date - dep_date).days + 1
        
        # 生成查票网址（示例使用携程API格式，需替换为真实API）
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{place2}-{date1}-{date2}"
        
        # 创建可点击的HTML链接
        ticket_link = f'<a href="{ticket_url}" target="_blank">{ticket_url}</a>'
        
        # 模拟生成旅行计划，格式化为表格数据
        travel_plan_data = []
        attractions = [f"上海景点{i}" for i in range(1, 11)]  # 模拟景点列表
        morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
        afternoon_activities = ["游览", "购物"]
        evening_activities = ["体验夜景", "品尝特色晚餐"]
        
        for day in range(1, days + 1):
            # 上午活动
            activity_time = "上午"
            activity_place = random.choice(attractions)
            activity_action = random.choice(morning_activities)
            activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
            travel_plan_data.append([f"Day{day}", activity_time, activity_place, activity_action, activity_transport])
            
            # 下午活动
            activity_time = "下午"
            activity_place = random.choice(attractions)
            activity_action = random.choice(afternoon_activities)
            activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
            travel_plan_data.append([f"Day{day}", activity_time, activity_place, activity_action, activity_transport])
            
            # 晚上活动（除最后一天）
            if day < days:
                activity_time = "晚上"
                activity_place = random.choice(attractions)
                activity_action = random.choice(evening_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day}", activity_time, activity_place, activity_action, activity_transport])
        
        return ticket_link, travel_plan_data
    
    except ValueError:
        return "日期格式错误，请使用YYYY-MM-DD格式", "请检查输入"
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划"
    
    
def generate_city_map(place, date):
    """生成城市地图（模拟图片API调用）"""
    if not place:
        return None, "请输入城市名称"
    
    # 模拟获取地图图片（使用picsum.photos示例服务）
    map_url = f"https://picsum.photos/seed/{place}/600/400"
    try:
        img = Image.open(requests.get(map_url, stream=True).raw)
        return img, f"{place} {date} 景点地图"
    except Exception as e:
        print(f"获取图片失败: {e}")
        return None, "无法加载地图"

def speech_to_text(audio_path, api_key):
    """调用语音转文字API（示例使用百度语音识别）"""
    # 替换为你的API配置
    API_URL = "https://vop.baidu.com/server_api"
    APP_ID = "你的_APP_ID"
    API_KEY = api_key
    SECRET_KEY = "你的_SECRET_KEY"

    # 读取音频文件并转换为WAV格式（部分API要求特定格式）
    audio = AudioSegment.from_file(audio_path)
    wav_path = "temp.wav"
    audio.export(wav_path, format="wav")

    # 构造请求参数
    with open(wav_path, "rb") as f:
        speech_data = f.read()
    
    params = {
        "dev_pid": 1536,  # 1536为普通话识别
        "format": "wav",
        "rate": 16000,
        "channel": 1,
        "cuid": "travel-assistant",
        "token": get_access_token(API_KEY, SECRET_KEY)
    }
    
    headers = {"Content-Type": "audio/wav; rate=16000"}
    response = requests.post(API_URL, params=params, headers=headers, data=speech_data)
    result = response.json()
    
    if result.get("err_no") == 0:
        return result["result"][0]
    else:
        return "语音识别失败，请重试"

def get_access_token(api_key, secret_key):
    """获取百度语音API访问令牌"""
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    response = requests.get(token_url)
    return response.json()["access_token"]

def chat_with_agent(text, chat_history):
    """模拟智能体对话（需替换为真实LLM API）"""
    # 示例：调用OpenAI ChatGPT API
    api_key = "你的_OPENAI_API_KEY"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": text}] + chat_history
    }
    
    response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
    if response.status_code == 200:
        assistant_msg = response.json()["choices"][0]["message"]["content"]
        chat_history.append({"role": "user", "content": text})
        chat_history.append({"role": "assistant", "content": assistant_msg})
        return "", chat_history
    else:
        return "对话失败，请重试", chat_history
    

# 创建界面
with gr.Blocks() as demo:
    with gr.Tab("查票与行程规划"):
        gr.Markdown("# 输入出发地、目的地和日期，获取查票链接和旅行建议")
        with gr.Row():
            with gr.Column():
                place1 = gr.Textbox(label="出发地", placeholder="例如：北京")
                date1 = gr.Textbox(label="出发日期", placeholder="YYYY-MM-DD")
            with gr.Column():
                place2 = gr.Textbox(label="目的地", placeholder="例如：上海")
                date2 = gr.Textbox(label="返回日期", placeholder="YYYY-MM-DD")
        with gr.Row():
            clear_btn = gr.Button("清除")
            submit_btn = gr.Button("提交", variant="primary")
        with gr.Row():
            ticket_url_output = gr.HTML(label="查票网址")
        with gr.Row():
            travel_plan_output = gr.Dataframe(
                headers=["日期", "时间", "地点", "活动", "交通"],
                datatype=["str", "str", "str", "str", "str"],
                label="旅行规划",
                interactive=False
            )
        
        # 绑定事件
        def update_travel_plan(place1, date1, place2, date2):
            ticket_link, plan = generate_travel_plan(place1, date1, place2, date2)
            return ticket_link, plan
        
        submit_btn.click(
            fn=update_travel_plan,
            inputs=[place1, date1, place2, date2],
            outputs=[ticket_url_output, travel_plan_output]
        )
        clear_btn.click(
            fn=lambda: [None, None, None, None],
            inputs=[],
            outputs=[place1, date1, place2, date2]
        )
    
    with gr.Tab("语音输入"):    
        gr.Markdown("# 🗣️ 语音与智能体对话")
    
    # 聊天历史存储
        chat_state = gr.State([])
    
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="语音输入", 
                    type="filepath", 
                    elem_id="speech-input"
                )
                stt_btn = gr.Button("开始识别", variant="primary")
                clear_btn = gr.Button("清空历史")
        
            with gr.Column():
                chatbot = gr.Chatbot(
                    label="旅行助手", 
                    type="messages", 
                    height=600
                )
    
    # 语音识别 + 对话逻辑绑定
        def process_speech(audio_path, chat_history, api_key):
            if not audio_path:
                return "请先上传语音文件", chat_history
        
        # 语音转文字
            text = speech_to_text(audio_path, api_key)
        
        # 调用智能体对话
            return chat_with_agent(text, chat_history)
    
        stt_btn.click(
            fn=process_speech,
            inputs=[audio_input, chat_state, gr.Textbox(visible=False, value="你的_百度语音API_KEY")],
            outputs=[gr.Textbox(visible=False), chatbot]
        )
    
        clear_btn.click(
            fn=lambda: ([], []),
            outputs=[chat_state, chatbot]
        )

    with gr.Tab("城市景点地图"):    
        gr.Markdown("# 🌍 城市景点地图")
    
        with gr.Row():
            with gr.Column():
                place = gr.Textbox(label="所在城市", placeholder="例如：北京")
                date = gr.Textbox(label="日期", placeholder="YYYY-MM-DD")
                map_submit_btn = gr.Button("获取地图", variant="primary")
                map_clear_btn = gr.Button("清除")
        
            with gr.Column():
                map_image = gr.Image(label="城市地图", height=400)
                map_caption = gr.Textbox(label="地图说明", interactive=False)
    
        # 绑定事件
        def update_city_map(place, date):
            img, caption = generate_city_map(place, date)
            return img, caption
        
        map_submit_btn.click(
            fn=update_city_map,
            inputs=[place, date],
            outputs=[map_image, map_caption]
        )
        map_clear_btn.click(
            fn=lambda: [None, None],
            inputs=[],
            outputs=[place, date]
        )

if __name__ == "__main__":
    demo.launch()