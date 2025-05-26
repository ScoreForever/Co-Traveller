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

# 百度语音API配置（从API.env读取）
BAIDU_API_KEY = env_vars.get("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = env_vars.get("BAIDU_SECRET_KEY", "")
BAIDU_APP_ID = env_vars.get("BAIDU_APP_ID", "")

SILICON_API_KEY = env_vars.get("SILICON_API_KEY", "")

def is_valid_date(date_str):
    """验证日期是否为YYYY-MM-DD格式且在当日或之后"""
    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return input_date >= today
    except ValueError:
        return False

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
        
        # 将列表转换为DataFrame
        headers = ["日期", "时间", "地点", "活动", "交通"]
        travel_plan_data = pd.DataFrame(travel_plan_data, columns=headers)
        
        return ticket_link, travel_plan_data
    
    except ValueError:
        return "日期格式错误，请使用YYYY-MM-DD格式", "请检查输入"
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划"

# 高德地图相关功能
def search_poi(keyword):
    """使用高德POI搜索API将关键词转换为地址，增强景点识别能力"""
    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": AMAP_API_KEY,
        "keywords": keyword,
        "output": "json",
        "offset": 5,  # 获取多个结果
        "extensions": "all"  # 获取详细信息
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data["status"] == "1" and data["pois"]:
            # 优先选择景点、风景名胜等类型
            poi_priorities = ['风景名胜', '旅游景点', '公园广场', '博物馆', '文化场馆', '商务住宅', '地名地址']
            
            for priority_type in poi_priorities:
                for poi in data["pois"]:
                    if priority_type in poi.get("type", ""):
                        address = poi.get("address", "")
                        name = poi.get("name", "")
                        # 返回更详细的地址信息
                        if address and address != "[]":
                            return f"{address}{name}" if name not in address else address
                        else:
                            return name
            
            # 如果没有匹配到优先类型，返回第一个结果
            poi = data["pois"][0]
            address = poi.get("address", "")
            name = poi.get("name", "")
            if address and address != "[]":
                return f"{address}{name}" if name not in address else address
            else:
                return name
        return None
    except Exception as e:
        print(f"POI搜索失败: {e}")
        return None

def extract_addresses_from_text(text):
    """从文本中提取地址信息，支持景点名称和各种地址格式"""
    if not text.strip():
        return []
    
    # 清理文本，去除多余的标点符号
    cleaned_text = re.sub(r'[，。！？；：、\s]+', ' ', text)
    
    # 定义可能的分隔符
    separators = ['从', '到', '去', '经过', '途径', '然后', '接着', '再到', '最后到', 
                 '出发', '前往', '抵达', '到达', '游览', '参观', '访问']
    
    # 使用分隔符分割文本
    pattern = '|'.join([f'({sep})' for sep in separators])
    segments = re.split(pattern, cleaned_text)
    
    # 提取可能的地点
    potential_locations = []
    
    # 从分割的片段中提取地点
    for segment in segments:
        if not segment or segment in separators:
            continue
        
        # 去除常见的非地点词汇
        non_location_words = ['我', '要', '想', '打算', '计划', '准备', '开始', '结束']
        words = segment.split()
        filtered_words = [word for word in words if word not in non_location_words and len(word) > 1]
        
        if filtered_words:
            potential_locations.extend(filtered_words)
    
    # 如果分割方法没有效果，尝试其他方法
    if not potential_locations:
        # 使用正则匹配中文地名和景点名
        location_patterns = [
            r'[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|村|街道|路|街|巷|号|大厦|广场|公园|景区|寺|庙|山|湖|河|桥|站|机场|港|码头)',
            r'[\u4e00-\u9fa5]{2,}(?:博物館|博物馆|纪念馆|展览馆|美术馆|图书馆|体育馆|剧院|影院)',
            r'[\u4e00-\u9fa5]{2,}(?:大学|学院|医院|银行|酒店|宾馆|商场|超市|餐厅)',
            r'[\u4e00-\u9fa5]{3,8}(?:风景区|旅游区|度假村|古镇|古城|老街)',
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, text)
            potential_locations.extend(matches)
        
        # 如果还是没有，尝试提取所有可能的中文词组
        if not potential_locations:
            # 提取2-8个字符的中文词组
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,8}', text)
            potential_locations.extend(chinese_words)
    
    # 去重并过滤
    unique_locations = []
    seen = set()
    
    for loc in potential_locations:
        loc = loc.strip()
        if len(loc) >= 2 and loc not in seen:
            seen.add(loc)
            unique_locations.append(loc)
    
    # 使用POI搜索验证和获取准确地址
    verified_addresses = []
    for location in unique_locations:
        # 尝试POI搜索
        poi_address = search_poi(location)
        if poi_address:
            verified_addresses.append(poi_address)
            print(f"成功解析: {location} -> {poi_address}")
        else:
            # 如果POI搜索失败，但看起来像地址，也保留
            if any(keyword in location for keyword in ['市', '区', '县', '路', '街', '景区', '公园']):
                verified_addresses.append(location)
                print(f"保留可能地址: {location}")
            else:
                print(f"无法解析: {location}")
    
    return list(set(verified_addresses))  # 去重返回

def geocode_address(address):
    """使用高德地图API将地址转换为经纬度"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": AMAP_API_KEY,
        "address": address,
        "output": "json"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] == "1" and data["geocodes"]:
            location = data["geocodes"][0]["location"]
            lng, lat = location.split(",")
            return float(lng), float(lat), data["geocodes"][0]["formatted_address"]
        else:
            return None, None, f"无法解析地址: {address}"
    except Exception as e:
        return None, None, f"地址解析错误: {str(e)}"

def calculate_route(start_lng, start_lat, end_lng, end_lat):
    """使用高德地图API计算路线"""
    url = "https://restapi.amap.com/v3/direction/driving"
    params = {
        "key": AMAP_API_KEY,
        "origin": f"{start_lng},{start_lat}",
        "destination": f"{end_lng},{end_lat}",
        "output": "json",
        "extensions": "all"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] == "1" and data["route"]["paths"]:
            path = data["route"]["paths"][0]
            polyline = path["steps"][0]["polyline"] if path["steps"] else ""
            distance = path["distance"]
            duration = path["duration"]
            
            return {
                "polyline": polyline,
                "distance": distance,
                "duration": duration,
                "success": True
            }
        else:
            return {"success": False, "error": "路线规划失败"}
    except Exception as e:
        return {"success": False, "error": f"路线规划错误: {str(e)}"}

def generate_map_html(locations, routes=None):
    """生成包含标注点、路线和交互式弹窗的高德地图HTML"""
    if not locations:
        return "未找到有效地址"
    
    center_lng = sum([loc[0] for loc in locations if loc[0]]) / len([loc for loc in locations if loc[0]])
    center_lat = sum([loc[1] for loc in locations if loc[1]]) / len([loc for loc in locations if loc[1]])
    
    html_content = f"""
    <div id="mapContainer" style="width: 100%; height: 400px;"></div>
    <script src="https://webapi.amap.com/maps?v=1.4.15&key={AMAP_API_KEY}"></script>
    <script>
        var map = new AMap.Map('mapContainer', {{
            center: [{center_lng}, {center_lat}],
            zoom: 10
        }});
    """
    
    for lng, lat, addr in locations:
        html_content += f"""
        var marker = new AMap.Marker({{
            position: [{lng}, {lat}],
            map: map,
            title: '{addr}'
        }});
        var infoWindow = new AMap.InfoWindow({{
            content: '<div><h4>{addr}</h4><p>点击查看详情</p></div>',
            offset: new AMap.Pixel(0, -30)
        }});
        marker.on('click', function() {{
            infoWindow.open(map, marker.getPosition());
        }});
        """
    
    if routes:
        for route in routes:
            if route.get("success"):
                points = route["polyline"].split(';')
                path = [[float(p.split(',')[0]), float(p.split(',')[1])] for p in points]
                html_content += f"""
                var polyline = new AMap.Polyline({{
                    path: {path},
                    strokeColor: "#3366FF",
                    strokeWeight: 5,
                    map: map
                }});
                """
    
    html_content += "</script>"
    return html_content

def process_text_to_map(text):
    """处理文本，提取地址并生成地图"""
    if not text.strip():
        return "请输入包含地址的文字", "请输入文字"
    
    addresses = extract_addresses_from_text(text)
    if not addresses:
        return "未在文本中识别到地址信息", "未识别到地址"
    
    locations = []
    geocode_results = []
    
    for addr in addresses:
        lng, lat, formatted_addr = geocode_address(addr)
        if lng and lat:
            locations.append((lng, lat, formatted_addr))
            geocode_results.append(f"✅ {addr} → {formatted_addr}")
        else:
            geocode_results.append(f"❌ {addr} → {formatted_addr}")
    
    if not locations:
        result_text = "地址解析失败:\n" + "\n".join(geocode_results)
        return "所有地址解析失败，无法生成地图", result_text
    
    routes = []
    if len(locations) > 1:
        for i in range(len(locations) - 1):
            start_lng, start_lat = locations[i][0], locations[i][1]
            end_lng, end_lat = locations[i + 1][0], locations[i + 1][1]
            route = calculate_route(start_lng, start_lat, end_lng, end_lat)
            routes.append(route)
    
    map_html = generate_map_html(locations, routes)
    
    result_text = "地址解析结果:\n" + "\n".join(geocode_results)
    if routes:
        success_routes = [r for r in routes if r.get('success')]
        result_text += f"\n\n路线规划: {len(success_routes)} 条路线成功规划"
    
    return map_html, result_text

def generate_city_map(place, date):
    """使用高德静态地图API生成城市或景点地图"""
    if not place:
        return None, "请输入地点"
    
    if date and not is_valid_date(date):
        return None, "日期格式错误或日期必须为今天或之后"
    
    try:
        # 尝试从POI搜索获取地址
        addr = search_poi(place)
        if not addr:
            addr = place  # 如果搜索失败，使用原始输入
        
        lng, lat, formatted_address = geocode_address(addr)
        if not lng or not lat:
            return None, f"无法找到地点: {place}"
        
        static_map_url = f"https://restapi.amap.com/v3/staticmap?key={AMAP_API_KEY}&location={lng},{lat}&zoom=10&size=600*400&markers=mid,,A:{lng},{lat}"
        response = requests.get(static_map_url)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content))
            return img, f"{formatted_address} {date} 地图"
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

    audio = AudioSegment.from_file(audio_path)
    wav_path = "temp.wav"
    audio.export(wav_path, format="wav")

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
    
    save_dir = Path("./travel_plans")
    save_dir.mkdir(exist_ok=True)
    
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
        
        return f"旅行计划已保存为: {filename}", list_saved_plans()
    except Exception as e:
        return f"保存失败: {str(e)}", list_saved_plans()

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
    save_dir = Path("./travel_plans")
    save_dir.mkdir(exist_ok=True)
    
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
    save_dir = Path("./travel_plans")
    file_path = save_dir / filename
    
    if not file_path.exists():
        return None, "未找到指定的旅行计划", []
    
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
            travel_plan_data
        )
    except Exception as e:
        return None, f"加载失败: {str(e)}", []

def delete_travel_plan(filename):
    """删除保存的旅行计划"""
    save_dir = Path("./travel_plans")
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
    
    with gr.Tab("查票与行程规划"):
        gr.Markdown("### 输入出发地、目的地和日期，获取查票链接和旅行建议")
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
        
        with gr.Row():
            with gr.Column(scale=1):
                save_btn = gr.Button("💾 保存当前计划")
                filename_input = gr.Textbox(label="保存文件名", placeholder="可选，留空则自动生成")
            with gr.Column(scale=2):
                saved_plans_output = gr.JSON(label="已保存的旅行计划")
        
        with gr.Row():
            with gr.Column(scale=1):
                load_btn = gr.Button("📂 加载选中计划")
                delete_btn = gr.Button("🗑️ 删除选中计划")
            with gr.Column(scale=2):
                file_selector = gr.Dropdown(choices=[], label="选择已保存的计划")
        
        def update_travel_plan(place1, date1, place2, date2):
            ticket_link, plan = generate_travel_plan(place1, date1, place2, date2)
            return ticket_link, plan
        
        submit_btn.click(
            fn=update_travel_plan,
            inputs=[place1, date1, place2, date2],
            outputs=[ticket_url_output, travel_plan_output]
        )
        
        clear_btn.click(
            fn=lambda: [None, None, None, None, None, None],
            inputs=[],
            outputs=[place1, date1, place2, date2, ticket_url_output, travel_plan_output]
        )
        
        def update_file_selector():
            plans = list_saved_plans()
            return [plan["filename"] for plan in plans]
        
        save_btn.click(
            fn=lambda p1, d1, p2, d2, url, plan, fn: save_travel_plan(p1, d1, p2, d2, url, plan, fn),
            inputs=[place1, date1, place2, date2, ticket_url_output, travel_plan_output, filename_input],
            outputs=[gr.Textbox(label="保存状态"), saved_plans_output]
        ).then(
            fn=update_file_selector,
            inputs=[],
            outputs=file_selector
        )
        
        load_btn.click(
            fn=lambda filename: load_travel_plan(filename) if filename else (None, "请先选择一个计划", []),
            inputs=[file_selector],
            outputs=[place1, date1, place2, date2, ticket_url_output, travel_plan_output]
        )
        
        delete_btn.click(
            fn=lambda filename: delete_travel_plan(filename) if filename else ("请先选择一个计划", []),
            inputs=[file_selector],
            outputs=[gr.Textbox(label="删除状态"), saved_plans_output]
        ).then(
            fn=update_file_selector,
            inputs=[],
            outputs=file_selector
        )
        
        demo.load(
            fn=lambda: (list_saved_plans(), update_file_selector()),
            inputs=[],
            outputs=[saved_plans_output, file_selector]
        )
    
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
            inputs=[audio_input, chat_state, gr.Textbox(visible=False, value=BAIDU_API_KEY)],  # 使用env中的API_KEY
            outputs=[gr.Textbox(visible=False), chatbot]
        )
    
        clear_btn.click(
            fn=lambda: ([], []),
            outputs=[chat_state, chatbot]
        )

    with gr.Tab("城市景点地图"):    
        gr.Markdown("### 🌍 城市景点地图")
    
        with gr.Row():
            with gr.Column():
                place = gr.Textbox(label="所在城市", placeholder="例如：北京")
                date = gr.Textbox(label="日期", placeholder="YYYY-MM-DD")
                map_submit_btn = gr.Button("获取地图", variant="primary")
                map_clear_btn = gr.Button("清除")
        
            with gr.Column():
                map_image = gr.Image(label="城市地图", height=400)
                map_caption = gr.Textbox(label="地图说明", interactive=False)
    
        def update_city_map(place, date):
            img, caption = generate_city_map(place, date)
            return img, caption
        
        map_submit_btn.click(
            fn=update_city_map,
            inputs=[place, date],
            outputs=[map_image, map_caption]
        )
        
        map_clear_btn.click(
            fn=lambda: [None, None, None],
            inputs=[],
            outputs=[place, date, map_image]
        )

    with gr.Tab("智能路线规划"):
        gr.Markdown("### 🗺️ 文本地址解析与路线规划")
        gr.Markdown("输入包含地址的文字，系统将自动提取地址、转换为经纬度、规划路线并在地图上展示")
        
        with gr.Row():
            with gr.Column():
                text_input = gr.Textbox(
                    label="输入包含地址的文字", 
                    placeholder="例如：我要从北京市朝阳区三里屯出发，去故宫博物院，然后到天安门广场",
                    lines=4
                )
                with gr.Row():
                    process_btn = gr.Button("🚀 开始规划", variant="primary")
                    clear_text_btn = gr.Button("清除")
                result_text = gr.Textbox(label="处理结果", lines=6, interactive=False)
            
            with gr.Column():
                map_display = gr.HTML(
                    label="路线地图",
                    value="""<div style="width: 100%; height: 400px; text-align: center; line-height: 400px;">请输入地址并点击“开始规划”来显示地图</div>"""
                )
        
        def handle_route_planning(text):
            map_html, result = process_text_to_map(text)
            return map_html, result
        
        def clear_route_planning():
            return "", "请输入地址并点击“开始规划”来显示地图", ""
        
        process_btn.click(
            fn=handle_route_planning,
            inputs=[text_input],
            outputs=[map_display, result_text]
        )
        
        clear_text_btn.click(
            fn=clear_route_planning,
            inputs=[],
            outputs=[text_input, map_display, result_text]
        )

if __name__ == "__main__":
    demo.launch()