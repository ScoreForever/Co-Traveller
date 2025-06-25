import os
import amap
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
from src.amap import set_amap_api_key, process_route, create_map_html, geocode_location, calculate_driving_route  # 补充需要的函数



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
set_amap_api_key(AMAP_API_KEY)

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
        # 使用amap模块中的geocode_location获取经纬度，并通过API补充地址信息
        coords = amap.geocode_location(address)  # 正确函数
        if not coords:
            continue
        lng, lat = coords
        
        # 补充获取完整地址（需调用地理编码API获取formatted_addr）
        url = "https://restapi.amap.com/v3/geocode/geo"
        params = {
            "key": AMAP_API_KEY,
            "address": address,
            "output": "json"
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            if data.get("status") == "1" and data.get("count", 0) > 0:
                formatted_addr = data["geocodes"][0]["formatted_address"]
                match = re.search(r'([^省市]+市)', formatted_addr)
                if match:
                    city = match.group(1)
                    city_set.add(city)
        except:
            continue
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
            # Define morning_activities if not already defined
            morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
            # Define morning_activities if not already defined
            morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动"]
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

def generate_travel_plan_multi(place1, date1, dests, date2):
    """
    流式输出旅行规划，每次yield部分DataFrame
    """
    try:
        if not is_valid_date(date1):
            yield "日期格式错误或日期必须在当日或之后", None
            return
        if not is_valid_date(date2):
            yield "日期格式错误或日期必须在当日或之后", None
            return
        if not dests:
            yield "请至少填写一个目的地", None
            return
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            yield "返回日期不能早于出发日期", None
            return
        total_days = (ret_date - dep_date).days + 1
        if total_days > 30:
            yield "旅游时间过长，建议不超过30天", None
            return

        # --- 保存GUI输入，调用大模型，读取LLM输出 ---
        import sys, os, json
        from pathlib import Path
        import pandas as pd

        base_dir = Path(__file__).parent.parent.resolve()
        save_dir = base_dir / "temp" / "travel_plans"
        save_dir.mkdir(parents=True, exist_ok=True)
        gui_path = save_dir / "route_planning_GUIoutput.json"
        llm_path = save_dir / "route_planning_LLMoutput.jsonl"

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
        # 启动子进程，异步写入llm_path
        proc = subprocess.Popen([sys.executable, str(route_planner_path)], cwd=str(save_dir))

        # 流式读取llm_path（JSONL），每次yield部分DataFrame
        headers = ["日期", "时间", "地点", "活动", "交通"]
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2}"
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'
        yielded_rows = []
        last_size = 0
        max_wait = 120  # 最多等待2分钟
        waited = 0
        while proc.poll() is None or (llm_path.exists() and os.path.getsize(llm_path) > last_size):
            if llm_path.exists():
                with open(str(llm_path), "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = lines[len(yielded_rows):]
                for line in new_lines:
                    try:
                        row = json.loads(line)
                        norm = [
                            row.get("date") or row.get("日期") or "",
                            row.get("time") or row.get("时间") or "",
                            row.get("location") or row.get("地点") or "",
                            row.get("activity") or row.get("活动") or "",
                            row.get("transport") or row.get("交通") or "",
                        ]
                        yielded_rows.append(norm)
                        df = pd.DataFrame(yielded_rows, columns=headers)
                        yield ticket_link, df
                    except Exception:
                        continue
                last_size = os.path.getsize(llm_path)
            time.sleep(0.5)
            waited += 0.5
            if waited > max_wait:
                break
        # 若无内容，返回空表格
        if not yielded_rows:
            df = pd.DataFrame([], columns=headers)
            yield ticket_link, df
    except Exception as e:
        yield f"发生错误: {str(e)}", None

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
        headers = ["日期", "时间", "地点", "活动", "交通"]
        df = pd.DataFrame([], columns=headers)
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2}"
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'

        # 均分天数给每个目的地
        days_per_dest = total_days // len(dests)
        extra_days = total_days % len(dests)
        all_attractions = []  # Define all_attractions as an empty list
        for i, dest in enumerate(dests):
            stay_days = days_per_dest + (1 if i < extra_days else 0)
            attractions = [f"{dest}景点{j}" for j in range(1, 4)]
            all_attractions.extend(attractions)
            for _ in range(stay_days):
                # 上午活动
                activity_time = "上午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(morning_activities) # type: ignore
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 下午活动
                activity_time = "下午"
                activity_place = random.choice(attractions)
                activity_action = random.choice(afternoon_activities) # type: ignore
                activity_transport = random.choice(["公交", "地铁", "步行", "出租车"])
                travel_plan_data.append([f"Day{day_idx}（{cur_date.strftime('%Y-%m-%d')}）", activity_time, activity_place, activity_action, activity_transport])

                # 晚上活动
                activity_time = "晚上"
                activity_place = random.choice(attractions)
                activity_action = random.choice(evening_activities) # type: ignore
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
                route = amap.calculate_driving_route(start_lng, start_lat, end_lng, end_lat)  # 正确函数
                if route.get("success"):
                    routes.append(route)

        
        # 构造符合amap.create_map_html要求的参数（需包含polyline、origin、destination等字段）
        # 示例：取第一条路线的polyline作为地图数据
        if routes:
            result_for_map = {
                "success": True,
                "polyline": routes[0].get("polyline"),
                "origin": f"{start_lng},{start_lat}",
                "destination": f"{end_lng},{end_lat}",
                "origin_name": "起点",
                "destination_name": "终点",
                "distance": routes[0].get("distance", 0),
                "duration": routes[0].get("duration", 0)
            }
            map_html = amap.create_map_html(result_for_map)  # 正确函数
        else:
            map_html = "<div>无有效路线数据</div>"

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

def speech_to_text(audio_path, api_key=None, secret_key=None):
    """调用语音转文字API（示例使用百度语音识别）"""
    # 检查ffmpeg/ffprobe依赖
    try:
        from pydub.utils import which
        if not which("ffmpeg") or not which("ffprobe"):
            return "语音识别失败：请确保已安装 ffmpeg 并配置到系统环境变量"
    except Exception:
        return "语音识别失败：请确保已安装 ffmpeg 并配置到系统环境变量"

    API_URL = "https://vop.baidu.com/server_api"
    APP_ID = BAIDU_APP_ID
    API_KEY = api_key if api_key else BAIDU_API_KEY
    SECRET_KEY = secret_key if secret_key else BAIDU_SECRET_KEY

    # 支持多种输入类型
    import numpy as np
    import io
    from pydub import AudioSegment

    temp_dir = Path("../temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / "temp.wav"

    try:
        if isinstance(audio_path, str) and os.path.isfile(audio_path):
            audio = AudioSegment.from_file(audio_path)
        elif isinstance(audio_path, bytes):
            audio = AudioSegment.from_file(io.BytesIO(audio_path))
        elif isinstance(audio_path, np.ndarray):
            arr = audio_path
            # 支持一维（单声道）、二维（多声道）、以及Gradio麦克风tuple格式
            if arr.ndim == 2:
                arr = arr.mean(axis=1)
            arr = arr.astype(np.float32)
            # 归一化到[-1, 1]，防止溢出
            if arr.size > 0 and (arr.max() > 1.0 or arr.min() < -1.0):
                arr = arr / np.abs(arr).max()
            # 若全为0则不处理
            if arr.size == 0 or np.all(arr == 0):
                return "语音识别失败：音频为空"
            audio = AudioSegment(
                (arr * 32767).astype(np.int16).tobytes(),
                frame_rate=16000,
                sample_width=2,
                channels=1
            )
        elif isinstance(audio_path, tuple) and len(audio_path) == 2:
            # Gradio麦克风输入格式 (sample_rate, np.ndarray)
            sample_rate, arr = audio_path
            arr = np.array(arr)
            # 修正：确保归一化到[-1,1] float32
            if arr.dtype != np.float32:
                arr = arr.astype(np.float32)
            if arr.max() > 1.1 or arr.min() < -1.1:
                arr = arr / 32768.0
            if arr.ndim == 2:
                arr = arr.mean(axis=1)
            if arr.size == 0 or np.all(arr == 0):
                return "语音识别失败：音频为空"
            audio = AudioSegment(
                (arr * 32767).astype(np.int16).tobytes(),
                frame_rate=sample_rate if sample_rate else 16000,
                sample_width=2,
                channels=1
            )
        else:
            return "语音识别失败：不支持的音频输入类型"
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(str(wav_path), format="wav")
    except Exception as e:
        return f"语音识别失败：音频解码错误，请检查ffmpeg安装。错误信息: {e}"

    with open(wav_path, "rb") as f:
        speech_data = f.read()
    
    params = {
        "dev_pid": 1537,  # 修正：3307错误为音频内容异常，1537为普通话带标点
        "format": "wav",
        "rate": 16000,
        "channel": 1,
        "cuid": "travel-assistant",
        "token": get_access_token(API_KEY, SECRET_KEY)
    }
    
    headers = {"Content-Type": "audio/wav; rate=16000"}
    try:
        response = requests.post(API_URL, params=params, headers=headers, data=speech_data)
        result = response.json()
    except Exception as e:
        return f"语音识别失败：API请求错误，{e}"
    
    if result.get("err_no") == 0:
        return result["result"][0]
    else:
        return f"语音识别失败，请重试，错误码：{result.get('err_no')}，信息：{result.get('err_msg', '')}"

def get_access_token(api_key=None, secret_key=None):
    """获取百度语音API访问令牌"""
    if not api_key:
        api_key = BAIDU_API_KEY
    if not secret_key:
        secret_key = BAIDU_SECRET_KEY
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    response = requests.get(token_url)
    return response.json()["access_token"]

def chat_with_agent(text, chat_history, openai_api_key=None):
    """模拟智能体对话（已替换为硅基流动API）"""
    api_key = openai_api_key if openai_api_key else SILICON_API_KEY
    if not api_key:
        return "未配置SILICON_API_KEY", chat_history, ""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # 修正历史格式，确保为 [{"role": ..., "content": ...}]
    messages = []
    messages.append({
        "role": "system",
        "content": "你是一个专业的旅行助手，可以帮助用户规划行程、查询景点、天气等信息。回答要简洁专业。"
    })
    for item in chat_history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            messages.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            messages.append({"role": item[0], "content": item[1]})
    messages.append({"role": "user", "content": text})
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500
    }
    try:
        # 替换为硅基流动API地址
        response = requests.post(
            "https://api.siliconflow.cn/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            assistant_msg = response.json()["choices"][0]["message"]["content"]
            new_history = chat_history.copy()
            new_history.append({"role": "user", "content": text})
            new_history.append({"role": "assistant", "content": assistant_msg})
            return "", new_history, assistant_msg
        else:
            # 针对403错误，给出更友好的提示
            try:
                err = response.json()
                err_msg = err.get("error", {}).get("message", "")
            except Exception:
                err_msg = response.text
            if response.status_code == 403 and "not supported" in err_msg.lower():
                return (
                    "对话失败：当前网络环境或IP无法访问硅基流动API，建议：\n"
                    "1. 检查你的API Key是否为有效Key，且未被封禁；\n"
                    "2. 若你在中国大陆，请确保网络可访问硅基流动API；\n"
                    "3. 你也可以在API.env中配置代理API地址和Key。\n"
                    f"原始错误信息：{err_msg}",
                    chat_history,
                    ""
                )
            return f"对话失败，请重试，错误码：{response.status_code}，信息：{err_msg}", chat_history, ""
    except Exception as e:
        return f"对话异常: {str(e)}", chat_history, ""

def text_to_speech(text, api_key=None, secret_key=None):
    """调用百度TTS将文本转为语音文件，返回音频文件路径"""
    if not text:
        return None
    API_KEY = api_key if api_key else BAIDU_API_KEY
    SECRET_KEY = secret_key if secret_key else BAIDU_SECRET_KEY
    token = get_access_token(API_KEY, SECRET_KEY)
    tts_url = "http://tsn.baidu.com/text2audio"
    params = {
        "tex": text,
        "lan": "zh",
        "tok": token,
        "ctp": 1,
        "cuid": "travel-assistant",
        "spd": 5,
        "pit": 5,
        "vol": 5,
        "per": 0,
        "aue": 6  # wav
    }
    try:
        response = requests.post(tts_url, data=params)
        if response.headers.get("Content-Type", "").startswith("audio/"):
            temp_dir = Path("../temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            audio_path = temp_dir / f"tts_{int(time.time())}.wav"
            with open(audio_path, "wb") as f:
                f.write(response.content)
            return str(audio_path)
        else:
            return None
    except Exception:
        return None

def process_speech(audio_data, chat_history, baidu_api_key, baidu_secret_key, openai_api_key):
    """处理语音输入并调用对话"""
    if audio_data is None:
        return "请先录制或上传语音", chat_history, "", None
    
    # 处理不同类型的音频输入
    if isinstance(audio_data, str):  # 文件路径
        audio_path = audio_data
    elif isinstance(audio_data, tuple):  # 麦克风输入 (sample_rate, audio_array)
        _, audio_array = audio_data
        # 创建临时文件
        with temp_file.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio_path = temp_file.name
            # 将numpy数组转换为音频文件
            audio = AudioSegment(
                (audio_array * 32767).astype(np.int16).tobytes(),
                frame_rate=16000,
                sample_width=2,
                channels=1
            )
            audio.export(audio_path, format="wav")
    else:
        return "不支持的音频输入类型", chat_history, "", None
    
    # 语音转文字
    recognition_text = speech_to_text(audio_path, baidu_api_key, baidu_secret_key)
    
    if recognition_text.startswith("语音识别失败") or recognition_text.startswith("语音处理错误"):
        return recognition_text, chat_history, recognition_text, None
    
    # 调用对话API
    error_msg, new_chat_history, assistant_reply = chat_with_agent(
        recognition_text,
        chat_history,
        openai_api_key  # 确保传递API密钥
    )
    
    # 语音合成
    audio_path = None
    if assistant_reply:
        audio_path = text_to_speech(assistant_reply, baidu_api_key, baidu_secret_key)
    
    return error_msg, new_chat_history, recognition_text, audio_path

# ================== 语音助手全局状态和历史管理函数提前 ==================
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

assistant_state = VoiceAssistantState()

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

        # 只保留一个“旅行规划”表格（去除多余的gr.Row）
        ticket_url_output = gr.HTML(label="查票网址")
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
        
        # --------- 伪流式输出实现 start ---------
        import threading

        # 用于存储本次流式结果的全局变量
        from collections import defaultdict
        stream_results = defaultdict(list)
        stream_locks = defaultdict(threading.Lock)

        def update_travel_plan(place1, date1, *args):
            """
            手动实现DataFrame表格的流式输出，确保每次点击提交后读取的是本次生成的新内容。
            通过延迟等待route_planner.py启动并写入新文件后再开始流式读取。
            """
            dests = []
            for d in args[:-1]:
                if d and d.strip():
                    dests.append(d.strip())
            date2_val = args[-1]
            if not dests or not date2_val:
                yield "请至少填写一个目的地和返程日期", pd.DataFrame(columns=["日期", "时间", "地点", "活动", "交通"])
                return

            # 1. 写入GUI输入文件
            base_dir = Path(__file__).parent.parent.resolve()
            save_dir = base_dir / "temp" / "travel_plans"
            save_dir.mkdir(parents=True, exist_ok=True)
            gui_path = save_dir / "route_planning_GUIoutput.json"
            llm_path = save_dir / "route_planning_LLMoutput.json"

            gui_plan = {
                "departure": place1,
                "departure_date": date1,
                "return_date": date2_val,
                "destinations": [{"place": d} for d in dests]
            }
            with open(gui_path, "w", encoding="utf-8") as f:
                json.dump(gui_plan, f, ensure_ascii=False, indent=2)

            # 2. 启动route_planner.py为子进程（异步写入llm_path）
            route_planner_path = base_dir / "src" / "utils" / "route_planner.py"
            proc = subprocess.Popen([sys.executable, str(route_planner_path)], cwd=str(save_dir))

            # 3. 等待route_planner.py真正开始写入新文件，避免读取到旧内容
            headers = ["日期", "时间", "地点", "活动", "交通"]
            ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2_val}"
            ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'
            yielded_rows = []
            last_size = 0
            max_wait = 120  # 最多等待2分钟
            waited = 0

            # 先yield空表格
            yield ticket_link, pd.DataFrame([], columns=headers)

            # 先等待llm_path被清空或被重写（即文件内容变为空或被truncate），避免读取到旧内容
            # 只要文件存在且内容不为空，先truncate
            if llm_path.exists():
                try:
                    with open(llm_path, "w", encoding="utf-8") as f:
                        f.truncate(0)
                except Exception:
                    pass

            # 等待route_planner.py真正开始写入（即文件大小大于0）
            start_wait = 0
            while (not llm_path.exists() or os.path.getsize(llm_path) == 0) and start_wait < 10:
                time.sleep(0.2)
                start_wait += 0.2

            # 4. 流式读取llm_path，每次yield一个DataFrame
            while proc.poll() is None or (llm_path.exists() and os.path.getsize(llm_path) > last_size):
                if llm_path.exists():
                    with open(str(llm_path), "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    new_lines = lines[len(yielded_rows):]
                    for line in new_lines:
                        try:
                            row = json.loads(line)
                            norm = [
                                row.get("date") or row.get("日期") or "",
                                row.get("time") or row.get("时间") or "",
                                row.get("location") or row.get("地点") or "",
                                row.get("activity") or row.get("活动") or "",
                                row.get("transport") or row.get("交通") or "",
                            ]
                            yielded_rows.append(norm)
                            df = pd.DataFrame(yielded_rows, columns=headers)
                            yield ticket_link, df
                        except Exception:
                            continue
                time.sleep(0.5)
                waited += 0.5
                if waited > max_wait:
                    break
            # 若无内容，返回空表格
            if not yielded_rows:
                df = pd.DataFrame([], columns=headers)
                yield ticket_link, df

        # --------- 伪流式输出实现 end ---------

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
            fn=lambda p1, d1, *args: save_travel_plan( # type: ignore
                p1, d1, args[0] if args[0] else "", args[-2] if len(args) > 1 else "", args[-3], args[-4], args[-1]
            ),
            inputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, filename_input],
            outputs=[save_status]
        )

    with gr.Tab("🗣️ 语音助手"):    
        gr.Markdown("### 🎤 语音对话助手")
        
        # 使用Column布局组织组件
        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    label="上传语音文件",
                    type="filepath",
                    interactive=True
                )
                
                record_status = gr.Textbox(
                    label="状态",
                    value="等待语音输入...",
                    interactive=False,
                    elem_id="record_status"  # 添加 ID
                )
                
                with gr.Row():
                    stt_btn = gr.Button("🔍 识别语音", variant="primary")
                    clear_btn = gr.Button("🧹 清空历史")
                    tts_btn = gr.Button("🔊 播放回复")
                
                speech_text = gr.Textbox(
                    label="语音识别结果",
                    placeholder="识别结果将显示在这里...",
                    lines=3,
                    interactive=False
                )
                
                audio_output = gr.Audio(
                    label="语音回复",
                    type="filepath",
                    interactive=False,
                    visible=False
                )
            
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    label="对话记录",
                    height=500,
                    show_label=True,
                    value=[],
                    type="messages"
                )
        
        # 添加 JavaScript 状态更新
        status_js = """
        <script>
        function updateStatus() {
            const statusBox = document.getElementById('record_status');
            if (statusBox) {
                if (statusBox.innerText.includes('处理中')) {
                    const dots = '.'.repeat((Math.floor(Date.now() / 500) % 4));
                    statusBox.innerText = '处理中' + dots;
                }
            }
            setTimeout(updateStatus, 500);
        }
        setTimeout(updateStatus, 500);
        </script>
        """
        gr.HTML(status_js)
        
        # 处理上传的音频文件
        def handle_upload(file):
            if file and os.path.isfile(file):
                assistant_state.audio_file_path = file
            else:
                assistant_state.audio_file_path = ""
            # 不返回任何值

        audio_input.upload(
            fn=handle_upload,
            inputs=[audio_input],
            outputs=[]
        )

        # 语音识别和对话处理
        def recognize_and_chat(audio_data=None):
            # 优先使用上传的音频文件路径
            audio_path = assistant_state.audio_file_path
            print(f"[DEBUG] audio_path: {audio_path}")
            print(f"[DEBUG] audio_input.value type: {type(audio_input.value)}")
            print(f"[DEBUG] recognize_and_chat received audio_data param: {type(audio_data)}")
            import platform
            import gradio
            print(f"[DEBUG] gradio version: {gradio.__version__}")
            print(f"[DEBUG] platform: {platform.platform()}")

            # 优先使用传入的 audio_data（gradio 5.x 推荐方式）
            if audio_data is not None:
                # 修正：如果是 tuple，取第二项（numpy数组），并归一化到[-1,1]
                if isinstance(audio_data, tuple) and len(audio_data) == 2:
                    sample_rate, arr = audio_data
                    print(f"[DEBUG] audio_data tuple: sample_rate={sample_rate}, arr.shape={getattr(arr, 'shape', None)}")
                    arr = np.array(arr)
                    if arr.dtype != np.float32:
                        arr = arr.astype(np.float32)
                    # Gradio 5.x 录音通常是[-1,1] float32，但有时是int16
                    if arr.max() > 1.1 or arr.min() < -1.1:
                        arr = arr / 32768.0
                    audio_data = (sample_rate, arr)
            elif audio_path and os.path.isfile(audio_path):
                print("[DEBUG] 使用上传的音频文件路径")
                audio_data = audio_path
            else:
                pass
            # 修正：如果麦克风录音有内容则允许识别
            if audio_data is None or (isinstance(audio_data, (np.ndarray, tuple)) and (getattr(audio_data, 'size', 0) == 0)):
                print("[DEBUG] 未检测到有效音频数据，audio_data:", audio_data)
                print("[DEBUG] 可能原因：")
                print("  1. 浏览器未允许麦克风权限或未正确录音。")
                print("  2. Gradio 版本兼容性问题。")
                print("  3. 录音后未点击“识别语音”按钮。")
                print("  4. 录音组件未正确传递音频数据。")
                print("  5. 若用远程/手机访问，部分浏览器不支持音频录制。")
                return "请先录制或上传语音", assistant_state.chat_history, "", None
            print("[DEBUG] audio_data 检测通过，开始调用 process_speech")
            return process_speech(
                audio_data,
                assistant_state.chat_history,
                BAIDU_API_KEY,
                BAIDU_SECRET_KEY,
                SILICON_API_KEY
            )

        # 设置按钮事件
        stt_btn.click(
            fn=lambda: {"record_status": "正在处理语音..."},
            outputs=[record_status]
        ).then(
            fn=recognize_and_chat,
            inputs=[audio_input],  # 关键：把 audio_input 作为输入
            outputs=[record_status, chatbot, speech_text, audio_output]
        ).then(
            fn=lambda: gr.Audio(visible=True),
            outputs=[audio_output]
        )

        # 播放回复按钮事件
        tts_btn.click(
            fn=lambda: assistant_state.last_audio_path,
            inputs=[],
            outputs=[audio_output]
        ).then(
            fn=lambda: gr.Audio(visible=True),
            outputs=[audio_output]
        )

        # 清空历史按钮
        def reset_conversation():
            assistant_state.reset()
            return {
                record_status: "对话已清空",
                chatbot: [],
                speech_text: "",
                audio_output: gr.update(visible=False)
            }

        clear_btn.click(
            fn=reset_conversation,
            outputs=[record_status, chatbot, speech_text, audio_output]
        )
    
    # 新增：路线规划标签页
    
    with gr.Tab("🗺️ 路线规划"):
        gr.Markdown("# 🗺️ 高德地图路线规划")
        gr.Markdown("输入起点和终点的位置名称（如：北京天安门、上海东方明珠），自动计算最佳驾车路线")
        
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 📍 起点位置")
                    start_location = gr.Textbox(
                        label="起点名称", 
                        placeholder="例如：北京天安门",
                        value="北京天安门"
                    )
                
                with gr.Group():
                    gr.Markdown("### 📍 终点位置")
                    end_location = gr.Textbox(
                        label="终点名称", 
                        placeholder="例如：北京颐和园",
                        value="北京颐和园"
                    )
                
                submit_btn = gr.Button("🚗 规划路线", variant="primary")
                
                gr.Examples(
                    examples=[
                        ["北京天安门", "北京颐和园"],
                        ["上海外滩", "上海东方明珠"],
                        ["广州塔", "广州白云机场"]
                    ],
                    inputs=[start_location, end_location],
                    label="示例路线"
                )
            
            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### 📊 路线摘要")
                    summary = gr.Textbox(label="路线信息", lines=4, interactive=False)
                
                with gr.Group():
                    gr.Markdown("### 🗺️ 路线地图")
                    map_display = gr.HTML(
                        label="路线可视化",
                        value="<div style='min-height:400px; display:flex; align-items:center; justify-content:center; background:#f0f0f0; border-radius:10px;'>等待路线规划...</div>"
                    )
                
                with gr.Group():
                    gr.Markdown("### 🚥 详细路线指引")
                    step_instructions = gr.Textbox(label="导航步骤", lines=8, interactive=False)
        
        # 设置事件处理（注意：需确保process_route函数在当前作用域可用）
        submit_btn.click(
            fn=process_route,
            inputs=[start_location, end_location],
            outputs=[summary, map_display, step_instructions]
        )
    # 票务查询Tab
    with gr.Tab("🎫 票务查询"):
        gr.Markdown("### 查询火车票和机票信息")
        
        with gr.Row():
            with gr.Column():
                departure_place = gr.Textbox(label="出发地", placeholder="例如：北京")
                arrival_place = gr.Textbox(label="目的地", placeholder="例如：上海")
                departure_date = gr.Textbox(label="出发日期", placeholder="YYYY-MM-DD")
                return_date = gr.Textbox(label="返回日期（可选）", placeholder="YYYY-MM-DD")
                
                ticket_type = gr.Radio(
                    choices=["单程", "往返"],
                    label="票务类型",
                    value="单程"
                )
                
                transport_type = gr.Radio(
                    choices=["火车", "飞机"],
                    label="交通工具",
                    value="火车"
                )
                
                search_btn = gr.Button("🔍 查询票务", variant="primary")
                clear_btn = gr.Button("清除")
            
            with gr.Column():
                gr.Markdown("### 票务查询结果")
                
                # 火车票表格
                with gr.Tab("火车票"):
                    train_tickets_output = gr.Dataframe(
                        headers=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"],
                        label="火车票信息",
                        interactive=False
                    )
                    
                    train_price_plot = gr.Plot(label="票价趋势图")
                
                # 机票表格
                with gr.Tab("机票"):
                    flight_tickets_output = gr.Dataframe(
                        headers=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"],
                        label="机票信息",
                        interactive=False
                    )
                    
                    flight_price_plot = gr.Plot(label="票价趋势图")
        
        # 票务查询函数
        def search_tickets(departure_place, arrival_place, departure_date, return_date, ticket_type, transport_type):
            """模拟查询火车票和机票信息"""
            if not departure_place or not arrival_place or not departure_date:
                if transport_type == "火车":
                    return pd.DataFrame(columns=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"]), None
                else:
                    return pd.DataFrame(columns=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"]), None
            
            # 验证日期格式
            if not is_valid_date(departure_date):
                if transport_type == "火车":
                    return pd.DataFrame(columns=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"]), None
                else:
                    return pd.DataFrame(columns=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"]), None
            
            # 验证返程日期
            if ticket_type == "往返" and return_date and not is_valid_date(return_date):
                if transport_type == "火车":
                    return pd.DataFrame(columns=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"]), None
                else:
                    return pd.DataFrame(columns=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"]), None
            
            # 模拟生成票务数据
            if transport_type == "火车":
                # 模拟火车票数据
                train_data = []
                for i in range(1, 11):
                    # 随机生成车次
                    train_number = f"G{i:03d}" if random.random() > 0.5 else f"D{i:03d}"
                    
                    # 随机生成时间
                    dep_hour = random.randint(6, 22)
                    dep_minute = random.choice([0, 15, 30, 45])
                    departure_time = f"{dep_hour:02d}:{dep_minute:02d}"
                    
                    # 随机生成历时
                    duration_hours = random.randint(1, 10)
                    duration_minutes = random.choice([0, 15, 30, 45])
                    duration = f"{duration_hours}小时{duration_minutes}分钟"
                    
                    # 计算到达时间
                    dep_datetime = datetime.strptime(f"{departure_date} {departure_time}", "%Y-%m-%d %H:%M")
                    arr_datetime = dep_datetime + timedelta(hours=duration_hours, minutes=duration_minutes)
                    arrival_time = arr_datetime.strftime("%H:%M")
                    
                    # 随机生成票价
                    business_price = round(random.uniform(800, 2000), 2) if random.random() > 0.3 else ""
                    first_price = round(random.uniform(500, 1200), 2) if random.random() > 0.3 else ""
                    second_price = round(random.uniform(300, 800), 2) if random.random() > 0.1 else ""
                    hard_seat = round(random.uniform(100, 300), 2) if train_number.startswith("D") and random.random() > 0.5 else ""
                    hard_sleep = round(random.uniform(200, 500), 2) if train_number.startswith("D") and random.random() > 0.5 else ""
                    soft_sleep = round(random.uniform(400, 800), 2) if train_number.startswith("D") and random.random() > 0.7 else ""
                    
                    train_data.append([
                        train_number, 
                        departure_place, 
                        arrival_place, 
                        departure_time, 
                        arrival_time, 
                        duration, 
                        business_price, 
                        first_price, 
                        second_price, 
                        hard_seat, 
                        hard_sleep, 
                        soft_sleep
                    ])
                
                # 创建DataFrame
                train_df = pd.DataFrame(
                    train_data, 
                    columns=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"]
                )
                
                # 创建票价趋势图
                days = [datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=i) for i in range(-3, 4)]
                dates = [day.strftime("%Y-%m-%d") for day in days]
                prices = [round(random.uniform(300, 800), 2) for _ in range(7)]
                
                fig = go.Figure(data=go.Scatter(x=dates, y=prices, mode='lines+markers'))
                fig.update_layout(
                    title=f"{departure_place}到{arrival_place}二等座票价趋势",
                    xaxis_title="日期",
                    yaxis_title="价格(元)"
                )
                
                return train_df, fig
            
            else:
                # 模拟机票数据
                airlines = ["中国国航", "东方航空", "南方航空", "海南航空", "厦门航空", "深圳航空", "四川航空", "吉祥航空", "春秋航空"]
                flight_data = []
                
                for i in range(1, 11):
                    # 随机生成航空公司和航班号
                    airline = random.choice(airlines)
                    flight_number = f"{airline[:2]}{random.randint(1000, 9999)}"
                    
                    # 随机生成机场
                    departure_airport = f"{departure_place}机场"
                    arrival_airport = f"{arrival_place}机场"
                    
                    # 随机生成时间
                    dep_hour = random.randint(6, 22)
                    dep_minute = random.choice([0, 15, 30, 45])
                    departure_time = f"{dep_hour:02d}:{dep_minute:02d}"
                    
                    # 随机生成历时
                    duration_hours = random.randint(1, 5)
                    duration_minutes = random.choice([0, 15, 30, 45])
                    duration = f"{duration_hours}小时{duration_minutes}分钟"
                    
                    # 计算到达时间
                    dep_datetime = datetime.strptime(f"{departure_date} {departure_time}", "%Y-%m-%d %H:%M")
                    arr_datetime = dep_datetime + timedelta(hours=duration_hours, minutes=duration_minutes)
                    arrival_time = arr_datetime.strftime("%H:%M")
                    
                    # 随机生成票价和舱位
                    price = round(random.uniform(500, 3000), 2)
                    cabin = random.choice(["经济舱", "超级经济舱", "商务舱", "头等舱"])
                    
                    flight_data.append([
                        airline, 
                        flight_number, 
                        departure_airport, 
                        arrival_airport, 
                        departure_time, 
                        arrival_time, 
                        duration, 
                        price, 
                        cabin
                    ])
                
                # 创建DataFrame
                flight_df = pd.DataFrame(
                    flight_data, 
                    columns=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"]
                )
                
                # 创建票价趋势图
                days = [datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=i) for i in range(-3, 4)]
                dates = [day.strftime("%Y-%m-%d") for day in days]
                prices = [round(random.uniform(500, 3000), 2) for _ in range(7)]
                
                fig = go.Figure(data=go.Scatter(x=dates, y=prices, mode='lines+markers'))
                fig.update_layout(
                    title=f"{departure_place}到{arrival_place}经济舱票价趋势",
                    xaxis_title="日期",
                    yaxis_title="价格(元)"
                )
                
                return flight_df, fig
        # 设置按钮事件
        search_btn.click(
            fn=lambda dp, ap, dd, rd, tt, tp: search_tickets(dp, ap, dd, rd, tt, tp),
            inputs=[departure_place, arrival_place, departure_date, return_date, ticket_type, transport_type],
            outputs=[train_tickets_output if transport_type == "火车" else flight_tickets_output, 
                    train_price_plot if transport_type == "火车" else flight_price_plot]
        )
        
        clear_btn.click(
            fn=lambda: [None, None, None, None, "单程", "火车", 
                    pd.DataFrame(columns=["车次", "出发站", "到达站", "出发时间", "到达时间", "历时", "商务座", "一等座", "二等座", "硬座", "硬卧", "软卧"]), None,
                    pd.DataFrame(columns=["航空公司", "航班号", "出发机场", "到达机场", "出发时间", "到达时间", "历时", "价格", "舱位"]), None],
            inputs=[],
            outputs=[departure_place, arrival_place, departure_date, return_date, ticket_type, transport_type,
                    train_tickets_output, train_price_plot, flight_tickets_output, flight_price_plot]
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
                # 修正此处的语法错误：将 '&&' 改为 'and'
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
                file_selector = gr.Dropdown(choices=[], value=None, label="选择行程", allow_custom_value=True)
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
            fn=update_history_table,
            outputs=[file_selector]
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

    #✅ 2. 加载 PDF 并构建检索系统（初始化一次即可）
    try:
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
        pass  # 注释或跳过文档加载逻辑
    except Exception as e:
        print(f"文档检索功能已跳过：{e}")
    

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

    # 语音助手使用说明
    with gr.Tab("使用说明"):
        gr.Markdown("## 语音助手功能使用说明")
        gr.Markdown(
            """
        **语音录制功能使用说明：**

        1. 打开 Gradio 网页界面，切换到“🗣️ 语音助手”标签页。
        2. 你可以选择两种方式输入语音：
           - **方式一：点击“上传语音文件”按钮，选择本地的音频文件（如 .wav/.mp3），然后点击“🔍 识别语音”按钮。**
           - **方式二：直接点击“上传语音文件”下方的麦克风图标，录制语音，录制完成后点击“🔍 识别语音”按钮。**
        3. 程序会自动识别你的语音内容，并调用大模型进行对话，结果会显示在“语音识别结果”和“对话记录”中。
        4. 若要听AI回复，可以点击“🔊 播放回复”按钮。
        5. 若要清空历史，点击“🧹 清空历史”按钮。

        **注意事项：**
        - 录音完成后一定要点击“🔍 识别语音”按钮，才能进行识别和对话。
        - 如果你没有上传音频文件，也没有录音，点击识别会提示“请先录制或上传语音”。
        - 录音时请确保浏览器已允许麦克风权限。
        - 支持直接录音和上传音频文件两种方式，任选其一即可。

        **常见问题：**
        - 如果识别失败，请检查麦克风权限、音频格式，或确保 ffmpeg 已正确安装。
        - 如果对话失败（如 403），请检查你的大模型 API Key 或网络环境。

        ---
        """
        )

if __name__ == "__main__":
    demo.launch()
