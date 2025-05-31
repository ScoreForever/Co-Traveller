import os
import queue
import requests
import json
from pathlib import Path
from pydub import AudioSegment
import gradio as gr
import io  # 添加 io 模块导入

# 语音识别结果队列，用于实时显示
speech_queue = queue.Queue()

def get_access_token(api_key, secret_key):
    """获取百度语音API访问令牌"""
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    response = requests.get(token_url)
    return response.json()["access_token"]

def speech_to_text(audio_data, baidu_api_key, baidu_secret_key):
    """调用语音转文字API"""
    try:
        # 确保temp目录存在
        temp_dir = Path("../temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        wav_path = temp_dir / "temp.wav"
        
        # 处理不同类型的音频输入
        if isinstance(audio_data, str):  # 文件路径
            audio = AudioSegment.from_file(audio_data)
        else:  # 音频数据
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
        audio = audio.set_frame_rate(16000).set_channels(1)  # 百度语音要求16kHz单声道
        audio.export(str(wav_path), format="wav")

        with open(wav_path, "rb") as f:
            speech_data = f.read()
        
        # 调用百度语音API
        API_URL = "https://vop.baidu.com/server_api"
        
        params = {
            "dev_pid": 1536,  # 普通话识别
            "format": "wav",
            "rate": 16000,
            "channel": 1,
            "cuid": "travel-assistant",
            "token": get_access_token(baidu_api_key, baidu_secret_key)
        }
        
        headers = {"Content-Type": "audio/wav; rate=16000"}
        response = requests.post(API_URL, params=params, headers=headers, data=speech_data)
        result = response.json()
        
        if result.get("err_no") == 0:
            text = result["result"][0]
            speech_queue.put(text)  # 将识别结果放入队列，用于实时显示
            return text
        else:
            return f"语音识别失败: {result.get('err_msg', '未知错误')}"
    except Exception as e:
        return f"语音处理错误: {str(e)}"

def chat_with_agent(text, chat_history, api_key):
    """调用智能对话API"""
    if not text:
        return "", chat_history
    
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "system", "content": "你是一个专业的旅行助手，可以帮助用户规划行程、查询景点、天气等信息。"}] + chat_history + [{"role": "user", "content": text}]
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            assistant_msg = response.json()["choices"][0]["message"]["content"]
            chat_history.append({"role": "user", "content": text})
            chat_history.append({"role": "assistant", "content": assistant_msg})
            return "", chat_history
        else:
            error_msg = f"对话API调用失败: HTTP {response.status_code}"
            return error_msg, chat_history
    except Exception as e:
        error_msg = f"对话处理错误: {str(e)}"
        return error_msg, chat_history

def process_speech(audio_data, chat_history, baidu_api_key, baidu_secret_key, openai_api_key):
    """处理语音输入并调用对话"""
    if audio_data is None:
        return "请先录制或上传语音", chat_history
    
    # 先显示"正在识别..."状态
    temp_msg = "正在识别语音..."
    chat_history.append({"role": "user", "content": temp_msg})
    
    # 语音转文字
    text = speech_to_text(audio_data, baidu_api_key, baidu_secret_key)
    
    # 如果识别失败，直接返回
    if text.startswith("语音识别失败") or text.startswith("语音处理错误"):
        chat_history[-1]["content"] = text
        return "", chat_history
    
    # 更新聊天历史，替换临时消息
    chat_history[-1]["content"] = text
    
    # 调用对话API
    error_msg, chat_history = chat_with_agent(text, chat_history, openai_api_key)
    
    return error_msg, chat_history

def get_speech_queue():
    """获取语音识别队列中的最新结果"""
    if not speech_queue.empty():
        return speech_queue.get()
    return None

def create_speech_ui(baidu_api_key, baidu_secret_key, openai_api_key):
    """创建语音功能的UI组件"""
    with gr.Tab("语音助手"):    
        gr.Markdown("### 🗣️ 语音助手")
        chat_state = gr.State([])
        
        with gr.Row():
            with gr.Column():
                # 实时麦克风输入
                audio_input = gr.Audio(
                    label="语音输入", 
                    type="filepath",
                    source="microphone",
                    streaming=False
                )
                
                with gr.Row():
                    stt_btn = gr.Button("开始识别", variant="primary")
                    clear_btn = gr.Button("清空历史")
                
                # 语音识别结果实时显示
                speech_text = gr.Textbox(
                    label="语音识别结果",
                    placeholder="请点击'开始识别'按钮进行语音输入...",
                    lines=2,
                    interactive=False
                )
            
            with gr.Column():
                chatbot = gr.Chatbot(
                    label="旅行助手对话", 
                    type="messages", 
                    height=500,
                    bubble_full_width=False
                )
        
        # 语音识别结果实时更新
        def update_speech_text():
            text = get_speech_queue()
            if text:
                return text
            return gr.update()
        
        # 定时检查语音队列
        speech_update = gr.Button("更新识别结果", visible=False)
        speech_update.click(
            fn=update_speech_text,
            outputs=[speech_text]
        )
        
        # 处理语音输入
        stt_btn.click(
            fn=lambda audio, chat: process_speech(audio, chat, baidu_api_key, baidu_secret_key, openai_api_key),
            inputs=[audio_input, chat_state],
            outputs=[gr.Textbox(visible=False), chatbot]
        )
        
        # 清空历史
        clear_btn.click(
            fn=lambda: ([], []),
            outputs=[chat_state, chatbot]
        )
        
        return chatbot, chat_state
