import os
import requests
import json
from pathlib import Path
from pydub import AudioSegment
import gradio as gr
import io
import time
import tempfile
import threading
import numpy as np

# 全局状态管理
class VoiceAssistantState:
    def __init__(self):
        self.recognition_text = ""
        self.is_processing = False
        self.last_audio_path = ""
        self.chat_history = []
        self.audio_file_path = ""
    
    def reset(self):
        self.recognition_text = ""
        self.is_processing = False
        self.last_audio_path = ""
        self.chat_history = []
        self.audio_file_path = ""

# 创建全局状态实例
assistant_state = VoiceAssistantState()

def get_access_token(api_key, secret_key):
    """获取百度语音API访问令牌"""
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    try:
        response = requests.get(token_url, timeout=5)
        return response.json().get("access_token", "")
    except Exception as e:
        print(f"获取访问令牌失败: {e}")
        return ""

def speech_to_text(audio_data, baidu_api_key, baidu_secret_key):
    """调用语音转文字API"""
    if not baidu_api_key or not baidu_secret_key:
        return "错误：未配置百度语音API密钥"
    try:
        # 处理不同类型的音频输入
        if isinstance(audio_data, str):  # 文件路径
            audio = AudioSegment.from_file(audio_data)
        elif isinstance(audio_data, bytes):  # 原始字节流
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
        elif hasattr(audio_data, "read"):  # file-like object
            audio = AudioSegment.from_file(audio_data)
        elif isinstance(audio_data, np.ndarray):  # gradio 可能传递 numpy 数组
            # 假设为16k采样单声道float32
            audio = AudioSegment(
                (audio_data * 32767).astype(np.int16).tobytes(),
                frame_rate=16000,
                sample_width=2,
                channels=1
            )
        else:
            return "不支持的音频输入类型"
        
        # 转换为百度API要求的格式
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # 创建临时WAV文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            audio.export(temp_wav.name, format="wav")
            temp_wav_path = temp_wav.name
        with open(temp_wav_path, "rb") as f:
            speech_data = f.read()
        os.unlink(temp_wav_path)  # 删除临时文件
        
        # 获取访问令牌
        token = get_access_token(baidu_api_key, baidu_secret_key)
        if not token:
            return "无法获取API访问令牌"
        
        # 调用语音识别API
        API_URL = "https://vop.baidu.com/server_api"
        params = {
            "dev_pid": 1537,  # 1537-带标点普通话，1737-英语
            "format": "wav",
            "rate": 16000,
            "channel": 1,
            "cuid": "travel-assistant",
            "token": token
        }
        
        headers = {"Content-Type": "audio/wav; rate=16000"}
        response = requests.post(API_URL, params=params, headers=headers, data=speech_data, timeout=10)
        result = response.json()
        
        if result.get("err_no") == 0:
            return result["result"][0]
        else:
            return f"语音识别失败: {result.get('err_msg', '未知错误')}"
    except Exception as e:
        return f"语音处理错误: {str(e)}"

def text_to_speech(text, baidu_api_key, baidu_secret_key):
    """调用百度语音合成API"""
    try:
        if not text:
            return None
        
        # 获取访问令牌
        token = get_access_token(baidu_api_key, baidu_secret_key)
        if not token:
            return None
        
        url = "https://tsn.baidu.com/text2audio"
        params = {
            "tex": text[:1024],  # 限制长度
            "tok": token,
            "cuid": "travel-assistant",
            "ctp": 1,  # 客户端类型
            "lan": "zh",
            "per": 0,  # 0-女声，1-男声
            "spd": 5,  # 语速 (0-9)
            "pit": 5,  # 音调 (0-9)
            "vol": 5   # 音量 (0-9)
        }
        
        response = requests.post(url, data=params, stream=True, timeout=10)
        if response.headers.get('Content-Type', '').startswith('audio/'):
            # 保存临时音频文件
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                temp_audio.write(response.content)
                temp_audio_path = temp_audio.name
            return temp_audio_path
        return None
    except Exception as e:
        print(f"语音合成失败: {e}")
        return None

def chat_with_agent(text, chat_history, openai_api_key):
    """调用智能对话API"""
    if not text:
        return "请提供问题内容", chat_history, ""
    
    try:
        # 准备消息历史
        messages = [{
            "role": "system",
            "content": "你是一个专业的旅行助手，可以帮助用户规划行程、查询景点、天气等信息。回答要简洁专业。"
        }]
        
        # 添加历史消息
        for item in chat_history:
            messages.append({"role": item["role"], "content": item["content"]})
        
        # 添加当前消息
        messages.append({"role": "user", "content": text})
        
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            response_data = response.json()
            assistant_msg = response_data["choices"][0]["message"]["content"]
            
            # 更新聊天历史
            new_history = chat_history.copy()
            new_history.append({"role": "user", "content": text})
            new_history.append({"role": "assistant", "content": assistant_msg})
            
            return "", new_history, assistant_msg
        else:
            error_msg = f"API错误 ({response.status_code}): {response.text}"
            return error_msg, chat_history, ""
    except Exception as e:
        error_msg = f"对话处理错误: {str(e)}"
        return error_msg, chat_history, ""

def process_speech(audio_data, chat_history, baidu_api_key, baidu_secret_key, openai_api_key):
    """处理语音输入并调用对话"""
    if audio_data is None:
        return "请先录制或上传语音", chat_history, "", None
    
    # 更新状态为处理中
    assistant_state.is_processing = True
    
    # 语音转文字
    recognition_text = speech_to_text(audio_data, baidu_api_key, baidu_secret_key)
    assistant_state.recognition_text = recognition_text
    
    # 如果识别失败，直接返回
    if recognition_text.startswith("语音识别失败") or recognition_text.startswith("语音处理错误"):
        return recognition_text, chat_history, recognition_text, None
    
    # 调用对话API
    error_msg, new_chat_history, assistant_reply = chat_with_agent(
        recognition_text, 
        chat_history, 
        openai_api_key
    )
    
    # 语音合成
    audio_path = None
    if assistant_reply:
        audio_path = text_to_speech(assistant_reply, baidu_api_key, baidu_secret_key)
        assistant_state.last_audio_path = audio_path
    
    # 更新状态
    assistant_state.is_processing = False
    assistant_state.chat_history = new_chat_history
    
    return error_msg, new_chat_history, recognition_text, audio_path