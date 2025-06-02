import os
import gradio as gr
import random
import datetime
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import requests
from datetime import datetime, timedelta
from pydub import AudioSegment
import json
from pathlib import Path
import pandas as pd
import re
import plotly.graph_objs as go
from collections import defaultdict
from dotenv import load_dotenv
import subprocess
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.rag_helper import load_pdfs_from_folder, build_retriever_from_docs, stream_search_docs
load_dotenv()

# 高德功能文件amap.py引入
import amap  # 假设amap.py在同一目录下，包含高德地图相关功能



def load_env(filepath):
    """从.env文件读取环境变量"""
    env = {}
    if os.path.exists(filepath):
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

# 读取API.env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "API.env")
env_vars = load_env(env_path)

# 高德地图 API 密钥（从API.env读取）
AMAP_API_KEY = env_vars.get("AMAP_API_KEY")
if not AMAP_API_KEY:
    raise RuntimeError("API.env 文件中缺少 AMAP_API_KEY 配置项")
amap.set_amap_api_key(AMAP_API_KEY)

# 百度语音API配置（从API.env读取）
BAIDU_API_KEY = env_vars.get("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = env_vars.get("BAIDU_SECRET_KEY", "")
BAIDU_APP_ID = env_vars.get("BAIDU_APP_ID", "")

SILICON_API_KEY = env_vars.get("SILICON_API_KEY", "")
X_QW_API_KEY = env_vars.get("X_QW_API_KEY", "")

def is_valid_date(date_str):
    """验证日期是否为YYYY-MM-DD格式且在当日或之后"""
    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return input_date >= today
    except ValueError:
        return False
    
def check_same_city(addresses):
    """检查所有地址是否在同一个市"""
    city_set = set()
    for address in addresses:
        # 使用amap模块中的geocode_address
        lng, lat, formatted_addr, _ = amap.geocode_address(address)
        if formatted_addr:
            # 提取市的名称
            match = re.search(r'([^省市]+市)', formatted_addr)
            if match:
                city = match.group(1)
                city_set.add(city)
    return len(city_set) == 1

def generate_travel_plan(place1, date1, place2, date2):
    """生成查票网址和旅行规划"""
    try:
        # 验证日期格式和有效性
        if not is_valid_date(date1):
            return "日期格式错误或日期必须在当日或之后", "请检查出发日期"
        if not is_valid_date(date2):
            return "日期格式错误或日期必须在当日或之后", "请检查返回日期"
            
        # 验证返回日期是否晚于出发日期
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            return "返回日期不能早于出发日期", "请检查日期顺序"
        
        # 计算旅行天数
        days = (ret_date - dep_date).days + 1
        
        # 验证旅行天数不超过30天
        if days > 30:
            return "旅游时间过长，建议不超过30天", "请缩短旅行日期"
        
        # 生成查票网址（示例使用携程API格式，需替换为真实API）
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{place2}-{date1}-{date2}"
        
        # 创建可点击的HTML链接
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'
        
        # 模拟生成旅行计划，格式化为表格数据
        travel_plan_data = []
        attractions = [f"{place2}景点{i}" for i in range(1, 11)]  # 模拟景点列表
        morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
        afternoon_activities = ["游览", "购物"]
        evening_activities = ["体验夜景", "品尝特色晚餐"]

        for i in range(days):
            cur_date = dep_date + timedelta(days=i)
            # 上午活动
            activity_time = "上午"
            activity_place = random.choice(attractions)
            activity_action = random.choice(morning_activities)
            activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
            travel_plan_data.append([f"Day{i+1}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

            # 下午活动
            activity_time = "下午"
            activity_place = random.choice(attractions)
            activity_action = random.choice(afternoon_activities)
            activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
            travel_plan_data.append([f"Day{i+1}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

            # 晚上活动
            activity_time = "晚上"
            activity_place = random.choice(attractions)
            activity_action = random.choice(evening_activities)
            activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
            travel_plan_data.append([f"Day{i+1}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])
        
        # 将列表转换为DataFrame
        headers = ["日期", "时间", "地点", "活动", "交通"]
        travel_plan_data = pd.DataFrame(travel_plan_data, columns=headers)
        
        return ticket_link, travel_plan_data
    
    except ValueError:
        return "日期格式错误，请使用YYYY-MM-DD格式", "请检查输入"
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划"

# 新增：支持多目的地和多日期的行程规划
def generate_travel_plan_multi(place1, date1, dests, date2):
    """
    place1: 出发地
    date1: 出发日期
    dests: 目的地列表
    date2: 返回日期
    """
    try:
        if not is_valid_date(date1):
            return "日期格式错误或日期必须在当日或之后", "请检查出发日期"
        if not is_valid_date(date2):
            return "日期格式错误或日期必须在当日或之后", "请检查返回日期"
        if not dests:
            return "请至少填写一个目的地", "请检查输入"
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            return "返回日期不能早于出发日期", "请检查日期顺序"
        total_days = (ret_date - dep_date).days + 1
        if total_days > 30:
            return "旅游时间过长，建议不超过30天", "请缩短旅行日期"
        # 均分天数给每个目的地
        days_per_dest = total_days // len(dests)
        extra_days = total_days % len(dests)
        travel_plan_data = []
        morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
        afternoon_activities = ["游览", "购物"]
        evening_activities = ["体验夜景", "品尝特色晚餐"]
        cur_date = dep_date
        day_idx = 1

        for i, dest in enumerate(dests):
            stay_days = days_per_dest + (1 if i < extra_days else 0)
            attractions = [f"{dest}景点{j}" for j in range(1, 4)]
            for _ in range(stay_days):
                # 上午活动
                activity_time = "上午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(morning_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 下午活动
                activity_time = "下午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(afternoon_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 晚上活动
                activity_time = "晚上"
                activity_place = random.choice(attractions)
                activity_action = random.choice(evening_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                cur_date += timedelta(days=1)
                day_idx += 1

        # 将列表转换为DataFrame
        headers = ["日期", "时间", "地点", "活动", "交通"]
        travel_plan_data = pd.DataFrame(travel_plan_data, columns=headers)

        # 生成查票网址
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2}"
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'

        return ticket_link, travel_plan_data

    except ValueError:
        return "日期格式错误，请使用YYYY-MM-DD格式", "请检查输入"
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划"

# 新增：支持多目的地和多日期的行程规划（改进版）
def generate_travel_plan_multi_v2(place1, date1, dests, date2):
    """
    place1: 出发地
    date1: 出发日期
    dests: 目的地列表
    date2: 返回日期
    """
    try:
        if not is_valid_date(date1):
            return "日期格式错误或日期必须在当日或之后", "请检查出发日期"
        if not is_valid_date(date2):
            return "日期格式错误或日期必须在当日或之后", "请检查返回日期"
        if not dests:
            return "请至少填写一个目的地", "请检查输入"
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            return "返回日期不能早于出发日期", "请检查日期顺序"
        total_days = (ret_date - dep_date).days + 1
        if total_days > 30:
            return "旅游时间过长，建议不超过30天", "请缩短旅行日期"
        
        # 初始化行程数据
        travel_plan_data = []
        all_attractions = []  # 收集所有景点名称
        morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
        afternoon_activities = ["游览", "购物"]
        evening_activities = ["体验夜景", "品尝特色晚餐"]
        
        cur_date = dep_date
        day_idx = 1

        # --- 新增：保存GUI输入，调用大模型，读取LLM输出 ---
        try:
            import sys, os, json
            from pathlib import Path
            import pandas as pd

            # 保证路径为绝对路径
            base_dir = Path(__file__).parent.parent.resolve()
            save_dir = base_dir / "temp" / "travel_plans"
            save_dir.mkdir(parents=True, exist_ok=True)
            gui_path = save_dir / "route_planning_GUIoutput.json"
            llm_path = save_dir / "route_planning_LLMoutput.json"

            # 保存GUI输入，增加返回日期
            gui_plan = {
                "departure": place1,
                "departure_date": date1,
                "return_date": date2,
                "destinations": [{"place": d} for d in dests]
            }
            with open(str(gui_path), "w", encoding="utf-8") as f:
                json.dump(gui_plan, f, ensure_ascii=False, indent=2)

            # 调用route_planner.py（用绝对路径，cwd=save_dir）
            route_planner_path = base_dir / "src" / "utils" / "route_planner.py"
            subprocess.run([sys.executable, str(route_planner_path)], cwd=str(save_dir), check=True)

            # 读取LLM输出
            if llm_path.exists():
                with open(str(llm_path), "r", encoding="utf-8") as f:
                    llm_plan = json.load(f)
                if isinstance(llm_plan, list) and llm_plan:
                    headers = ["日期", "时间", "地点", "活动", "交通"]
                    def norm(row):
                        return [
                            row.get("date") or row.get("日期") or "",
                            row.get("time") or row.get("时间") or "",
                            row.get("location") or row.get("地点") or "",
                            row.get("activity") or row.get("活动") or "",
                            row.get("transport") or row.get("交通") or "",
                        ]
                    df = pd.DataFrame([norm(r) for r in llm_plan], columns=headers)
                    ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2}"
                    ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'
                    return ticket_link, df
        except Exception as e:
            # 打印调试信息
            print("LLM行程生成异常：", e)

        # 如果大模型流程异常或无输出，返回空表格
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2}"
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'

        # 均分天数给每个目的地
        days_per_dest = total_days // len(dests)
        extra_days = total_days % len(dests)
        for i, dest in enumerate(dests):
            stay_days = days_per_dest + (1 if i < extra_days else 0)
            attractions = [f"{dest}景点{j}" for j in range(1, 4)]
            all_attractions.extend(attractions)
            for _ in range(stay_days):
                # 上午活动
                activity_time = "上午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(morning_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 下午活动
                activity_time = "下午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(afternoon_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 晚上活动
                activity_time = "晚上"
                activity_place = random.choice(attractions)
                activity_action = random.choice(evening_activities)
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                cur_date += timedelta(days=1)
                day_idx += 1

        # 将列表转换为DataFrame
        headers = ["日期", "时间", "地点", "活动", "交通"]
        travel_plan_data = pd.DataFrame(travel_plan_data, columns=headers)
        
        # 使用 amap.py 中的函数处理地址和生成地图
        
        # 提取景点中的地址信息
        addresses = []
        for attraction in all_attractions:
            addr_list = amap.extract_addresses_from_text(attraction)
            if addr_list:
                # 取第一个地址
                addresses.append(addr_list[0])

        if not addresses:
            return ticket_link, travel_plan_data, "未找到有效地址，无法生成地图"

        # 检查所有地址是否在同一个市
        if not check_same_city(addresses):
            return ticket_link, travel_plan_data, "景点不在同一个市，请重新选择目的地"

        # 获取地址的经纬度
        locations = []
        for addr_info in addresses:
            lng, lat, formatted_addr, address_info = amap.geocode_address(addr_info)
            if lng and lat:
                locations.append((lng, lat, formatted_addr, address_info))

        if not locations:
            return ticket_link, travel_plan_data, "所有地址都无法转换为有效坐标，无法生成地图"

        # 计算路线
        routes = []
        if len(locations) > 1:
            for i in range(len(locations) - 1):
                start_lng, start_lat, _, _ = locations[i]
                end_lng, end_lat, _, _ = locations[i + 1]
                route = amap.calculate_route(start_lng, start_lat, end_lng, end_lat)
                if route.get("success"):
                    routes.append(route)

        # 生成地图HTML
        map_html = amap.generate_map_html(locations, routes)

        return ticket_link, travel_plan_data, map_html
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划"

def generate_city_map(place, date=None):
    """使用高德静态地图API生成城市或景点地图"""
    if not place:
        return None, "请输入地点"

    if date and not is_valid_date(date):
        return None, "日期格式错误或日期必须为今天或之后"

    try:
        # 尝试从POI搜索获取地址
        addr_info = amap.search_poi(place)
        if not addr_info:
            # 如果搜索失败，使用原始输入
            addr_info = {
                'address': place,
                'name': place,
                'type': '',
                'location': '',
                'tel': '',
                'rating': '',
                'cost': ''
            }

        # 地理编码
        lng, lat, formatted_addr, _ = amap.geocode_address(addr_info)
        if not lng or not lat:
            return None, f"无法找到地点: {place}"

        static_map_url = f"https://restapi.amap.com/v3/staticmap?key={AMAP_API_KEY}&location={lng},{lat}&zoom=10&size=600*400&markers=mid,,A:{lng},{lat}"
        response = requests.get(static_map_url)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content))
            return img, f"{formatted_addr} 地图"
        else:
            return None, f"加载地图失败: HTTP {response.status_code}"
            
    except Exception as e:
        print(f"获取地图失败: {e}")
        return None, "加载地图失败"

def speech_to_text(audio_path, api_key=None):
    """调用语音转文字API（示例使用百度语音识别）"""
    API_URL = "https://vop.baidu.com/server_api"
    APP_ID = BAIDU_APP_ID
    API_KEY = BAIDU_API_KEY
    SECRET_KEY = BAIDU_SECRET_KEY

    # 确保temp目录存在
    temp_dir = Path("../temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / "temp.wav"

    audio = AudioSegment.from_file(audio_path)
    audio.export(str(wav_path), format="wav")

    with open(wav_path, "rb") as f:
        speech_data = f.read()
    
    params = {
        "dev_pid": 1536,
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

def get_access_token(api_key=None, secret_key=None):
    """获取百度语音API访问令牌"""
    if not api_key:
        api_key = BAIDU_API_KEY
    if not secret_key:
        secret_key = BAIDU_SECRET_KEY
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    response = requests.get(token_url)
    return response.json()["access_token"]

def chat_with_agent(text, chat_history):
    """模拟智能体对话（需替换为真实LLM API）"""
    api_key = SILICON_API_KEY  # 使用SILICON_API_KEY
    if not api_key:
        return "未配置SILICON_API_KEY", chat_history
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

def save_travel_plan(place1, date1, place2, date2, ticket_link, travel_plan_data, filename=None):
    """保存旅行计划到JSON文件"""
    if not filename:
        filename = f"{place1}_{place2}_{date1.replace('-', '')}.json"
    
    save_dir = Path("../temp/travel_plans")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = save_dir / filename
    
    if isinstance(travel_plan_data, pd.DataFrame):
        travel_plan_data = travel_plan_data.to_dict('records')
    
    plan_data = {
        "place1": place1,
        "date1": date1,
        "place2": place2,
        "date2": date2,
        "ticket_link": ticket_link,
        "travel_plan_data": travel_plan_data,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "short_summary": summarize_travel_plan(travel_plan_data)
    }
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)
        
        return f"旅行计划已保存为: {filename}"
    except Exception as e:
        return f"保存失败: {str(e)}"

def summarize_travel_plan(plan_data):
    """生成旅行计划摘要"""
    if not plan_data:
        return "无行程信息"
    
    summary = []
    days_seen = set()
    for item in plan_data[:6]:
        day = item["日期"]
        if day not in days_seen:
            days_seen.add(day)
            summary.append(f"{day}: {item['地点']} - {item['活动']}")
    
    if len(plan_data) > 6:
        summary.append(f"... 等共{len(plan_data)}项行程")
    
    return "\n".join(summary)

def list_saved_plans():
    """列出所有保存的旅行计划"""
    save_dir = Path("../temp/travel_plans")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    plans = []
    for file in save_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                plan = json.load(f)
                plans.append({
                    "filename": file.name,
                    "place1": plan["place1"],
                    "place2": plan["place2"],
                    "date1": plan["date1"],
                    "date2": plan["date2"],
                    "saved_at": plan["saved_at"],
                    "short_summary": plan.get("short_summary", "无行程信息")
                })
        except:
            continue
    
    plans.sort(key=lambda x: x["saved_at"], reverse=True)
    return plans

def load_travel_plan(filename):
    """加载保存的旅行计划"""
    save_dir = Path("../temp/travel_plans")
    file_path = save_dir / filename
    
    if not file_path.exists():
        return None, None, None, None, None, None, "未找到指定的旅行计划"
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        
        travel_plan_data = plan["travel_plan_data"]
        if isinstance(travel_plan_data, list) and len(travel_plan_data) > 0:
            travel_plan_data = pd.DataFrame(travel_plan_data)
        
        return (
            plan["place1"], 
            plan["date1"], 
            plan["place2"], 
            plan["date2"], 
            plan["ticket_link"], 
            travel_plan_data,
            "行程已加载"
        )
    except Exception as e:
        return None, None, None, None, None, None, f"加载失败: {str(e)}"

def delete_travel_plan(filename):
    """删除保存的旅行计划"""
    save_dir = Path("../temp/travel_plans")
    file_path = save_dir / filename
    
    if not file_path.exists():
        return "未找到指定的旅行计划", list_saved_plans()
    
    try:
        file_path.unlink()
        return "旅行计划已删除", list_saved_plans()
    except Exception as e:
        return f"删除失败: {str(e)}", list_saved_plans()
#新增函数
def generate_route_map(places_str, transport, optimize, show_details):
    """生成路线地图和路线信息"""
    if not places_str.strip():
        return "请输入景点或地址", "请输入景点或地址"
    
    # 解析景点列表
    places = [p.strip() for p in places_str.split('，') if p.strip()]
    if len(places) < 2:
        return "请至少输入两个景点或地址", "请至少输入两个景点或地址"
    
    # 获取景点经纬度
    locations = []
    valid_places = []
    invalid_places = []
    
    for place in places:
        # 先通过POI搜索获取地址信息
        poi_info = amap.search_poi(place)
        if not poi_info:
            print(f"POI搜索失败: {place}")
            invalid_places.append(place)
            continue
        
        # 地理编码
        lng, lat, formatted_addr, address_info = amap.geocode_address(poi_info)
        if lng and lat:
            # 确保传递4个元素：lng, lat, formatted_addr, address_info
            locations.append((lng, lat, formatted_addr, address_info))
            valid_places.append(formatted_addr)
        else:
            print(f"地理编码失败: {place}")
            invalid_places.append(place)
    
    if not locations:
        return "无法解析任何地址", "无法解析任何地址"
    
    # 优化路线顺序（如果需要）
    if optimize and len(locations) > 2:
        try:
            # 优化路线顺序
            locations = amap.optimize_route_order(locations)
        except Exception as e:
            print(f"路线优化失败: {e}")
    
    # 计算路线
    routes = []
    if len(locations) > 1:
        for i in range(len(locations) - 1):
            start_lng, start_lat, start_addr, start_info = locations[i]
            end_lng, end_lat, end_addr, end_info = locations[i + 1]
            
            # 确保起点和终点有效
            if not all([start_lng, start_lat, end_lng, end_lat]):
                print(f"跳过无效路线: {start_addr} -> {end_addr}")
                continue
                
            route = amap.calculate_route(
                start_lng, start_lat, end_lng, end_lat,
                transport_mode=transport.lower()
            )
            
            if route["success"]:
                routes.append(route)
                print(f"成功计算路线: {start_addr} -> {end_addr}")
            else:
                print(f"路线计算失败: {start_addr} -> {end_addr}")
    
    # 生成地图和路线信息
    try:
        map_html = amap.generate_route_map(
            locations, 
            routes,
            transport_mode=transport,
            show_details=show_details,
            optimize_route=optimize
        )
        
        # 生成路线信息文本
        route_text = "路线规划结果:\n\n"
        if invalid_places:
            route_text += f"⚠️ 无法解析以下地址: {', '.join(invalid_places)}\n\n"
        
        route_text += "✅ 有效景点:\n"
        for i, (lng, lat, addr, info) in enumerate(locations):
            route_text += f"{i+1}. {addr} (经度: {lng}, 纬度: {lat})\n"
        
        if routes:
            route_text += "\n🚗 路线详情:\n"
            for i, route in enumerate(routes):
                if route["success"]:
                    distance = float(route["distance"]) / 1000
                    duration = int(route["duration"]) // 60
                    start = locations[i][2]
                    end = locations[i+1][2]
                    route_text += f"{i+1}. {start} → {end}: {distance:.2f}公里, {duration}分钟\n"
        
        return map_html, route_text
        
    except Exception as e:
        print(f"生成地图失败: {e}")
        return f"生成地图失败: {str(e)}", "请检查输入参数"

# 创建界面
with gr.Blocks() as demo:
    gr.Markdown("# 🧳 旅行助手")
    
    # 查票与行程规划Tab
    with gr.Tab("查票与行程规划"):
        gr.Markdown("### 输入出发地、多个目的地和返程日期，获取查票链接和旅行建议")
        with gr.Row():
            with gr.Column():
                place1 = gr.Textbox(label="出发地", placeholder="例如：北京")
                date1 = gr.Textbox(label="出发日期", placeholder="YYYY-MM-DD")
            with gr.Column():
                MAX_INPUTS = 20
                current_index = gr.State(0)
                dest_inputs = []
                for i in range(MAX_INPUTS):
                    visible = i == 0
                    tb = gr.Textbox(
                        label=f"目的地 {i+1}",
                        placeholder="例如：上海",
                        visible=visible,
                        interactive=True
                    )
                    dest_inputs.append(tb)
                date2 = gr.Textbox(label="返回日期", placeholder="YYYY-MM-DD")
        
        with gr.Row():
            clear_btn = gr.Button("清除")
            submit_btn = gr.Button("提交", variant="primary")
        
        with gr.Row():
            ticket_url_output = gr.HTML(label="查票网址")
        
        with gr.Row():
            travel_plan_output = gr.Dataframe(
                headers=["日期", "时间", "地点", "活动", "交通"],
                label="旅行规划",
                interactive=False
            )
        
        with gr.Row():
            save_btn = gr.Button("💾 保存当前计划")
            filename_input = gr.Textbox(label="保存文件名", placeholder="可选，留空则自动生成")
            save_status = gr.Textbox(label="保存状态", interactive=False)
        
        # 动态显示下一个目的地和日期输入框
        def show_next_dest(text, index):
            if text.strip() and index < MAX_INPUTS - 1:
                return {
                    current_index: index + 1,
                    dest_inputs[index + 1]: gr.Textbox(visible=True),
                }
            return {current_index: index}
        
        for idx in range(MAX_INPUTS - 1):
            dest_inputs[idx].submit(
                show_next_dest,
                inputs=[dest_inputs[idx], current_index],
                outputs=[current_index, dest_inputs[idx + 1]],
            )
        
        # 收集所有已填写的目的地和日期并调用多目的地行程规划
        def update_travel_plan(place1, date1, *args):
            dests = []
            for d in args[:-1]:
                if d and d.strip():
                    dests.append(d.strip())
            date2_val = args[-1]
            if not dests or not date2_val:
                return "请至少填写一个目的地和返程日期", None
            return generate_travel_plan_multi(place1, date1, dests, date2_val)
        
        submit_btn.click(
            fn=update_travel_plan,
            inputs=[place1, date1] + dest_inputs + [date2],
            outputs=[ticket_url_output, travel_plan_output]
        )
        
        clear_btn.click(
            fn=lambda: [None, None] + [None]*MAX_INPUTS + [None, None, None, None],
            inputs=[],
            outputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, save_status]
        )
        
        save_btn.click(
            fn=lambda p1, d1, *args: save_travel_plan(
                p1, d1, args[0] if args[0] else "", args[-2] if len(args) > 1 else "", args[-3], args[-4], args[-1]
            ),
            inputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, filename_input],
            outputs=[save_status]
        )
    
    # 语音输入Tab
    with gr.Tab("语音输入"):    
        gr.Markdown("### 🗣️ 语音与智能体对话")
        chat_state = gr.State([])
    
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(label="语音输入", type="filepath")
                stt_btn = gr.Button("开始识别", variant="primary")
                clear_btn = gr.Button("清空历史")
        
            with gr.Column():
                chatbot = gr.Chatbot(label="旅行助手", type="messages", height=600)
    
        def process_speech(audio_path, chat_history, api_key):
            if not audio_path:
                return "请先上传语音文件", chat_history
            text = speech_to_text(audio_path, api_key)
            return chat_with_agent(text, chat_history)
    
        stt_btn.click(
            fn=process_speech,
            inputs=[audio_input, chat_state, gr.Textbox(visible=False, value=BAIDU_API_KEY)],
            outputs=[gr.Textbox(visible=False), chatbot]
        )
    
        clear_btn.click(
            fn=lambda: ([], []),
            outputs=[chat_state, chatbot]
        )
    
    # 城市景点地图Tab
    with gr.Tab("城市景点地图"):    
        gr.Markdown("### 🌍 城市景点地图")
    
        with gr.Row():
            with gr.Column():
                place = gr.Textbox(label="所在城市", placeholder="例如：北京")
                map_submit_btn = gr.Button("获取地图", variant="primary")
                map_clear_btn = gr.Button("清除")
        
            with gr.Column():
                map_image = gr.Image(label="城市地图", height=400)
                map_caption = gr.Textbox(label="地图说明", interactive=False)
    
        def update_city_map(place):  # 修改函数参数，移除date
            img, caption = generate_city_map(place, None)  # 调用时不传递日期
            return img, caption
    
        map_submit_btn.click(
            fn=update_city_map,
            inputs=[place],  # 仅传递place参数
            outputs=[map_image, map_caption]
        )
    
        map_clear_btn.click(
            fn=lambda: [None, None, None],
            inputs=[],
            outputs=[place, map_image, map_caption]
        )
    # 新增：路线规划标签页
    
    with gr.Tab("🗺️ 路线规划"):
        gr.Markdown("### 输入景点名称或地址，生成路线规划地图")
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("#### 输入选项")
                
                with gr.Row():
                    place_input = gr.Textbox(
                        label="景点/地址", 
                        placeholder="例如：北京故宫,八达岭长城,颐和园",
                        info="多个景点请用逗号分隔"
                    )
                    
                    transport_type = gr.Radio(
                        choices=["驾车", "公交", "步行", "骑行"],
                        value="驾车",
                        label="交通方式",
                        info="选择主要交通方式"
                    )
                
                with gr.Row():
                    optimize_route = gr.Checkbox(
                        value=True,
                        label="优化路线顺序",
                        info="根据距离自动优化景点游览顺序"
                    )
                    
                    show_details = gr.Checkbox(
                        value=True,
                        label="显示详细路线",
                        info="在地图上显示详细路线和距离"
                    )
                
                generate_btn = gr.Button("生成路线地图", variant="primary")
                clear_btn = gr.Button("清除")
            
            with gr.Column(scale=2):
                gr.Markdown("#### 地图展示")
                map_output = gr.HTML(label="路线地图")
                
        with gr.Row():
            route_info = gr.Textbox(
                label="路线信息",
                lines=10,
                interactive=False,
                info="显示景点顺序和路线详情"
            )
            
        def generate_route_map(places_str, transport, optimize, show_details):
            """生成路线地图和路线信息"""
            if not places_str.strip():
                return "请输入景点或地址", "请输入景点或地址"
            
            # 解析景点列表
            places = [p.strip() for p in places_str.split('，') if p.strip()]
            if len(places) < 2:
                return "请至少输入两个景点或地址", "请至少输入两个景点或地址"
            
            # 获取景点经纬度
            locations = []
            valid_places = []
            invalid_places = []
            
            for place in places:
                # 先通过POI搜索获取地址信息
                poi_info = amap.search_poi(place)
                if not poi_info:
                    poi_info = {
                        'address': place,
                        'name': place,
                        'type': '',
                        'location': '',
                        'tel': '',
                        'rating': '',
                        'cost': ''
                    }
                
                # 地理编码
                lng, lat, formatted_addr, address_info = amap.geocode_address(poi_info)
                if lng and lat:
                    locations.append((lng, lat, formatted_addr, address_info))
                    valid_places.append(formatted_addr)
                else:
                    invalid_places.append(place)
            
            if not locations:
                return "无法解析任何地址", "无法解析任何地址"
            
            # 如果需要优化路线顺序
            if optimize and len(locations) > 2:
                try:
                    # 优化路线顺序
                    locations = amap.optimize_route_order(locations)
                except Exception as e:
                    print(f"路线优化失败: {e}")
            
            # 生成路线信息文本
            route_text = "路线规划结果:\n\n"
            if invalid_places:
                route_text += f"⚠️ 无法解析以下地址: {', '.join(invalid_places)}\n\n"
            
            route_text += "✅ 有效景点:\n"
            for i, place in enumerate(valid_places):
                route_text += f"{i+1}. {place}\n"
            
            # 计算路线
            routes = []
            if len(locations) > 1:
                for i in range(len(locations) - 1):
                    start_lng, start_lat, _, _ = locations[i]
                    end_lng, end_lat, _, _ = locations[i + 1]
                    
                    # 根据选择的交通方式调用不同的路线规划API
                    route = amap.calculate_route(
                        start_lng, start_lat, end_lng, end_lat,
                        transport_mode=transport.lower()
                    )
                    
                    if route["success"]:
                        routes.append(route)
                        
                        # 提取路线详情
                        distance = float(route["distance"]) / 1000  # 转换为公里
                        duration = int(route["duration"]) // 60  # 转换为分钟
                        
                        route_text += f"\n🚗 从 {valid_places[i]} 到 {valid_places[i+1]}:"
                        route_text += f"\n   • 距离: {distance:.2f} 公里"
                        route_text += f"\n   • 预计时间: {duration} 分钟"
                        route_text += f"\n   • 交通方式: {transport}"
            
            # 生成美化后的地图
            map_html = amap.generate_route_map(
                locations, 
                routes,
                transport_mode=transport,
                show_details=show_details,
                optimize_route=optimize
            )
            
            return map_html, route_text
        
        # 设置事件处理
        generate_btn.click(
            fn=generate_route_map,
            inputs=[place_input, transport_type, optimize_route, show_details],
            outputs=[map_output, route_info]
        )
        
        clear_btn.click(
            fn=lambda: [None, None, None, None, None, None],
            inputs=[],
            outputs=[place_input, transport_type, optimize_route, show_details, map_output, route_info]
        )
    # 天气查询Tab
    with gr.Tab("🌦️ 地点天气查询"):
        gr.Markdown("### 输入地点，查看未来3天天气图标、描述、生活指数和地图")

        with gr.Row():
            query_place = gr.Textbox(label="输入地点", placeholder="例如：广州塔")
            weather_btn = gr.Button("查询天气", variant="primary")
            clear_weather_btn = gr.Button("清除")

        with gr.Row():
            icon_html_output = gr.HTML(label="天气图标")
        
        with gr.Row():
            weather_output = gr.Textbox(label="天气信息", lines=10, interactive=False)

        with gr.Row():
            indices_output = gr.HTML(label="生活指数")

        with gr.Row():
            map_image_output = gr.Image(label="地图", height=400)
            map_caption_output = gr.Textbox(label="地图说明", interactive=False)

        def query_weather_full(place):
            if not place.strip():
                return "", "请输入地点", "", None, ""

            # 使用amap模块进行地理编码
            poi_info = amap.search_poi(place)
            if not poi_info:
                poi_info = {'address': place}
                
            lng, lat, detail, _ = amap.geocode_address(poi_info)
            if not lng or not lat:
                return "", f"无法识别地点：{place}", "", None, ""

            location = f"{lng},{lat}"
            headers = {
                "X-QW-Api-Key": X_QW_API_KEY
            }

            # 天气图标和文本描述
            weather_url = "https://me3md84kpk.re.qweatherapi.com/v7/weather/3d"
            icon_html = ""
            try:
                weather_resp = requests.get(weather_url, headers=headers, params={"location": location})
                weather_data = weather_resp.json()
                weather_summary = ""
                if weather_resp.status_code == 200 and weather_data.get("code") == "200":
                    daily = weather_data.get("daily", [])
                    icon_html += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/qweather-icons@1.6.0/font/qweather-icons.css">\n'
                    icon_html += '<div style="display:flex;justify-content:space-around;font-size:48px;">'
                    weather_summary = f"📍 地点：{detail}\n"
                    for d in daily:
                        icon = d.get("iconDay", "999")
                        fxDate = d['fxDate']
                        desc = d['textDay']
                        tempMin = d['tempMin']
                        tempMax = d['tempMax']
                        wind = d['windDirDay']
                        icon_html += f'''
                            <div style="text-align:center;">
                                <div><i class="qi-{icon}"></i></div>
                                <div style="font-size:14px;">{fxDate}</div>
                                <div style="font-size:14px;">{desc}</div>
                            </div>
                        '''
                        weather_summary += f"\n📅 {fxDate} - {desc}，{tempMin}℃~{tempMax}℃，风向：{wind}"
                    icon_html += "</div>"
                else:
                    weather_summary = f"天气查询失败：{weather_data.get('code')}"
            except Exception as e:
                weather_summary = f"天气请求错误：{str(e)}"

            # 生活指数
            indices_url = "https://me3md84kpk.re.qweatherapi.com/v7/indices/3d"
            try:
                indices_resp = requests.get(indices_url, headers=headers, params={"location": location, "type": "1,2,3,5,6,9,14"})
                indices_data = indices_resp.json()

                indices_summary = '''
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
                <div style="font-size:15px;line-height:1.8;">
                '''

                fa_icons = {
                    "1": "fa-person-running",     # 运动
                    "2": "fa-person-hiking",      # 徒步/洗车
                    "3": "fa-shirt",              # 穿衣
                    "5": "fa-sun",                # 紫外线
                    "6": "fa-car",                # 洗车
                    "9": "fa-head-side-cough",    # 感冒
                    "14": "fa-smog"               # 晾晒/空气扩散
                }

                level_colors = {
                    "适宜": "#4CAF50",
                    "较适宜": "#8BC34A",
                    "极适宜": "#43A047",
                    "较不宜": "#B0BEC5",
                    "较强": "#FF9800",
                    "强": "#FF5722",
                    "很强": "#F44336",
                    "炎热": "#F4511E",
                    "不适宜": "#9E9E9E",
                    "较弱": "#90CAF9",
                    "弱": "#42A5F5",
                    "中等": "#FFC107",
                    "差": "#BDBDBD",
                    "少发": "#AED581"
                }

                from collections import defaultdict
                date_groups = defaultdict(list)
                for item in indices_data.get("daily", []):
                    date_groups[item["date"]].append(item)

                for date in sorted(date_groups.keys()):
                    indices_summary += f"<h4 style='margin-top:1em;'>📅 {date}</h4><ul style='list-style:none;padding-left:0;'>"
                    for item in date_groups[date]:
                        icon_class = fa_icons.get(item["type"], "fa-circle-info")
                        level = item["category"]
                        level_color = level_colors.get(level, "#607D8B")
                        indices_summary += f'''
                        <li style="margin-bottom:6px;">
                            <i class="fas {icon_class}" style="margin-right:8px;color:{level_color};"></i>
                            <b>{item["name"]}</b>（<span style="color:{level_color};font-weight:bold;">{level}</span>）：
                            {item["text"]}
                        </li>
                        '''
                    indices_summary += "</ul>"
                indices_summary += "</div>"

            except Exception as e:
                indices_summary = f"<div>指数请求错误：{str(e)}</div>"

            # 地图显示
            try:
                static_map_url = f"https://restapi.amap.com/v3/staticmap?key={AMAP_API_KEY}&location={lng},{lat}&zoom=10&size=600*400&markers=mid,,A:{lng},{lat}"
                map_resp = requests.get(static_map_url)
                if map_resp.status_code == 200:
                    map_img = Image.open(io.BytesIO(map_resp.content))
                    map_caption = f"{detail} 地图"
                else:
                    map_img = None
                    map_caption = f"地图加载失败：{map_resp.status_code}"
            except Exception as e:
                map_img = None
                map_caption = f"地图加载错误：{str(e)}"

            return icon_html, weather_summary, indices_summary, map_img, map_caption

        weather_btn.click(
            fn=query_weather_full,
            inputs=[query_place],
            outputs=[icon_html_output, weather_output, indices_output, map_image_output, map_caption_output]
        )

        clear_weather_btn.click(
            fn=lambda: ["", "", "", None, ""],
            inputs=[],
            outputs=[icon_html_output, weather_output, indices_output, map_image_output, map_caption_output]
        )
    #行程历史管理Tab
    with gr.Tab("行程历史管理"):
        gr.Markdown("### 已保存的旅行计划")
        
        with gr.Row():
            history_table = gr.Dataframe(
                headers=["文件名", "出发地", "目的地", "出发日期", "返回日期", "保存时间", "摘要"],
                label="历史行程",
                interactive=False
            )
        
        with gr.Row():
            with gr.Column(scale=1):
                file_selector = gr.Dropdown(label="选择行程")
                load_btn = gr.Button("加载行程")
                delete_btn = gr.Button("删除行程")
            with gr.Column(scale=2):
                status_msg = gr.Textbox(label="操作状态", interactive=False)
        
        # 更新历史表格和文件选择器
        def update_history_table():
            plans = list_saved_plans()
            if not plans:
                return pd.DataFrame(columns=["文件名", "出发地", "目的地", "出发日期", "返回日期", "保存时间", "摘要"]), []
            df = pd.DataFrame(plans)
            return df, df["filename"].tolist()
        
        # 初始化时加载历史行程
        demo.load(
            fn=update_history_table,
            outputs=[history_table, file_selector]
        )
        
        # 加载行程
        load_btn.click(
            fn=lambda filename: load_travel_plan(filename) if filename else (None, None, None, None, None, None, "请先选择一个计划"),
            inputs=[file_selector],
            outputs=[place1, date1, dest_inputs[0], date2, ticket_url_output, travel_plan_output, status_msg]
        ).then(
            fn=update_history_table,
            outputs=[history_table, file_selector]
        )
        
        # 删除行程
        delete_btn.click(
            fn=lambda filename: delete_travel_plan(filename) if filename else ("请先选择一个计划", []),
            inputs=[file_selector],
            outputs=[status_msg, history_table]
        ).then(
            fn=lambda: update_history_table(),
            outputs=[history_table, file_selector]
        )
    def load_env(filepath):
        env = {}
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
        return env

    env_path = Path(__file__).resolve().parent.parent / "API.env"
    env_vars = load_env(env_path)
    os.environ.update(env_vars)

    # ✅ 2. 加载 PDF 并构建检索系统（初始化一次即可）
    dataset_dir = Path(__file__).resolve().parent.parent / "dataset"
    rag_docs = load_pdfs_from_folder(dataset_dir)
    # 新增：检测GPU并打印当前设备
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] 当前向量检索模型加载设备: {device}")
    except ImportError:
        device = "cpu"
        print("[WARN] 未安装torch，默认使用CPU")
    retriever = build_retriever_from_docs(rag_docs)

    # ✅ 3. RAG 问答界面
    with gr.Tab("📚 文档问答助手"):
        gr.Markdown("### 输入关键词（如城市名），从PDF文档中检索并由大模型回答")

        with gr.Row():
            user_query = gr.Textbox(label="输入问题", placeholder="例如：北京")
            ask_btn = gr.Button("问大模型", variant="primary")

        with gr.Row():
            rag_answer = gr.Textbox(label="回答结果", lines=10, interactive=False)

        def query_docs_with_rag_stream(query):
            if not query.strip():
                yield "请输入问题"
                return
            buff=""
            for chunk in stream_search_docs(query, retriever):
                if chunk is None: continue
                else:buff+= chunk
                yield buff
            yield buff

        ask_btn.click(fn=query_docs_with_rag_stream, inputs=[user_query], outputs=[rag_answer])

if __name__ == "__main__":
    demo.launch()