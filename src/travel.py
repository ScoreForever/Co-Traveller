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
import math 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.rag_helper import load_pdfs_from_folder, build_retriever_from_docs, stream_search_docs
load_dotenv()
import amap
from src.amap import geocode_address, set_amap_api_key, process_route, create_map_html  
import html2image
import requests


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

from pathlib import Path
module_path = Path(__file__).parent / "utils"  
sys.path.append(str(module_path))
from railway import query_trains
from airplane import query_flights


def query_airplane(start, end, date):
    """查询机票信息"""
    if not start or not end or not date:
        return "请输入出发地、目的地和日期"
    
    try:
        flights = query_flights(leave_city=start, arrive_city=end, date=date)
        if not flights:
            return "未查询到符合条件的航班。"
        
        result = []
        for flight in flights:
            info = (f"{flight.get('flightNo','')} {flight.get('airlineCompany','')} "
                    f"{flight.get('planLeaveTime','')}→{flight.get('planArriveTime','')} "
                    f"{flight.get('leavePort','')}({flight.get('leavePortCode','')})→"
                    f"{flight.get('arrivePort','')}({flight.get('arrivePortCode','')}) "
                    f"状态:{flight.get('state','')}")
            result.append(info)
        
        return "\n\n".join(result)
    
    except Exception as e:
        return f"查询航班失败: {str(e)}"


def query_train(start, end, date):
    """查询火车票信息"""
    if not start or not end or not date:
        return "请输入出发地、目的地和日期"
    
    try:
        trains = query_trains(start, end, date=date)
        if not trains:
            return "未查询到符合条件的火车班次。"
        
        result = []
        for train in trains:
            price_info = []
            price_fields = [
                ("pricesw", "商务座"),
                ("pricetd", "特等座"),
                ("pricegr1", "高级软卧上铺"),
                ("pricegr2", "高级软卧下铺"),
                ("pricerw1", "软卧上铺"),
                ("pricerw2", "软卧下铺"),
                ("priceyw1", "硬卧上铺"),
                ("priceyw2", "硬卧中铺"),
                ("priceyw3", "硬卧下铺"),
                ("priceyd", "一等座"),
                ("priceed", "二等座"),
            ]
            
            for key, label in price_fields:
                value = train.get(key, "")
                value_str = str(value).strip()
                if value_str and value_str != "0.0" and value_str != "-":
                    price_info.append(f"{label}:{value_str}元")
            
            price_str = " ".join(price_info)
            info = (f"{train.get('trainno','')} {train.get('type','')} "
                    f"{train.get('departuretime','')}→{train.get('arrivaltime','')} "
                    f"历时{train.get('costtime','')} {price_str}")
            result.append(info)
        
        return "\n\n".join(result)
    
    except Exception as e:
        return f"查询火车班次失败: {str(e)}"
    
def save_travel_plan(filename):
    """
    保存当前旅行计划为PDF，支持自定义文件名。
    """
    import subprocess
    import sys
    from pathlib import Path
    import os
    import shutil

    base_dir = Path(__file__).parent.parent.resolve()
    temp_dir = base_dir / "temp" / "travel_plans"
    guides_dir = base_dir / "travel_guides"
    temp_dir.mkdir(parents=True, exist_ok=True)
    guides_dir.mkdir(parents=True, exist_ok=True)

    # 1. 调用plan_maker.py生成tourGuide.md
    plan_maker_path = base_dir / "src" / "utils" / "plan_maker.py"
    try:
        subprocess.run([sys.executable, str(plan_maker_path)], cwd=str(temp_dir), check=True)
    except Exception as e:
        return f"调用plan_maker.py失败: {e}"

    # 2. 调用md2pdf_wkhtmltopdf.py生成tourGuide.pdf
    md2pdf_path = base_dir / "src" / "utils" / "md2pdf_wkhtmltopdf.py"
    try:
        subprocess.run([sys.executable, str(md2pdf_path)], cwd=str(base_dir), check=True)
    except Exception as e:
        return f"调用md2pdf_wkhtmltopdf.py失败: {e}"

    # 3. 检查文件名并重命名
    pdf_path = guides_dir / "tourGuide.pdf"
    if not pdf_path.exists():
        return "PDF文件未生成，保存失败"
    if filename and filename.strip():
        # 只保留文件名部分，自动加.pdf后缀
        safe_name = "".join(c for c in filename.strip() if c not in r'\/:*?"<>|')
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"
        target_path = guides_dir / safe_name
        try:
            shutil.move(str(pdf_path), str(target_path))
            return f"已保存为 {target_path.name}"
        except Exception as e:
            return f"重命名PDF失败: {e}"
    else:
        return f"已保存为 {pdf_path.name}"

#创建界面
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
            # 两个按钮上下排列（同一列）
            with gr.Column():
                generate_btn = gr.Button("📝 生成旅行攻略")
                view_pdf_btn = gr.Button("📄 查看旅行攻略")
            filename_input = gr.Textbox(label="保存文件名", placeholder="可选，留空则自动生成")
            generate_status = gr.Textbox(label="保存状态", interactive=False)
        with gr.Row():
            pdf_viewer = gr.HTML(label="旅行攻略PDF预览")

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
            outputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, generate_status]
        )
        
        generate_btn.click(
            fn=save_travel_plan,
            inputs=[filename_input],
            outputs=[generate_status]
        )

        def show_pdf(_):
            from pathlib import Path
            import base64
            guides_dir = Path(__file__).parent.parent / "travel_guides"
            pdf_path = guides_dir / "tourGuide.pdf"
            # 若有自定义文件名，优先显示最新修改的pdf
            pdf_files = sorted(guides_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
            if pdf_files:
                pdf_path = pdf_files[0]
            if not pdf_path.exists():
                return "<div style='color:red;'>未找到旅行攻略PDF文件，请先生成。</div>"
            with open(pdf_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"""
            <iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px" style="border:none;"></iframe>
            <div style="margin-top:8px;color:#888;">文件名：{pdf_path.name}</div>
            """

        view_pdf_btn.click(
            fn=show_pdf,
            inputs=[filename_input],  # 这里输入参数无实际用处，仅为触发
            outputs=[pdf_viewer]
        )

    with gr.Tab("🗺️ 路线规划"):
        gr.Markdown("# 🗺️ 高德地图路线规划")
        gr.Markdown("输入起点和终点的位置名称（如：北京天安门、上海东方明珠），自动计算最佳路线")
        
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
                
                # 路线类型选择
                route_type = gr.Dropdown(
                    label="路线类型",
                    choices=["驾车", "公交"],
                    value="驾车"
                )

                # 示例
                gr.Examples(
                    examples=[
                        ["北京天安门", "北京颐和园", "驾车"],
                        ["上海外滩", "上海东方明珠", "公交"]
                    ],
                    inputs=[start_location, end_location, route_type],
                    label="示例路线"
                )
            
            with gr.Column(scale=2):
                # 路线摘要
                with gr.Group():
                    gr.Markdown("### 📊 路线摘要")
                    summary = gr.Textbox(label="路线信息", lines=4, interactive=False)
                
                # 路线地图 - 关键修复
                with gr.Group():
                    gr.Markdown("### 🗺️ 路线地图")
                    map_display = gr.HTML(
                        label="路线可视化",
                        elem_id="map-container",
                        value="""
                        <div style="
                            height: 500px;
                            background: #f8f9fa;
                            border-radius: 15px;
                            padding: 20px;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        ">
                            <div style="height: 100%; width: 100%; display: flex; align-items: center; justify-content: center;">
                                <p>等待路线规划...</p>
                            </div>
                        </div>
                        """
                    )
                
                # 详细路线指引
                with gr.Group():
                    gr.Markdown("### 🚥 详细路线指引")
                    step_instructions = gr.Textbox(label="导航步骤", lines=8, interactive=False)
        
        # 事件处理
        submit_btn.click(
            fn=process_route,
            inputs=[start_location, end_location, route_type],
            outputs=[summary, map_display, step_instructions]
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
                
            lng, lat, detail = geocode_address(poi_info['address'])
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

    #交通票务查询Tab
    with gr.Tab("🎫 交通票务查询") :
        gr.Markdown("## 火车票和机票查询系统")
        
        with gr.Row():
            with gr.Column(scale=1):
                start_input = gr.Textbox(label="出发地", placeholder="请输入城市名称")
                end_input = gr.Textbox(label="目的地", placeholder="请输入城市名称")
                date_input = gr.Textbox(label="日期", placeholder="YYYY-MM-DD")
                
                with gr.Row():
                    airplane_btn = gr.Button("查询机票", variant="primary")
                    train_btn = gr.Button("查询火车票", variant="secondary")
            
            with gr.Column(scale=2):
                result_output = gr.Textbox(label="查询结果", lines=15)
        
        airplane_btn.click(
            fn=query_airplane,
            inputs=[start_input, end_input, date_input],
            outputs=result_output
        )
        
        train_btn.click(
            fn=query_train,
            inputs=[start_input, end_input, date_input],
            outputs=result_output
        )    

if __name__ == "__main__":
    demo.launch()