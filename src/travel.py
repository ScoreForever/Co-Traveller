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

# 活动类型定义
morning_activities = ["参观", "品尝当地早餐", "参加文化体验活动", "游览自然风光"]
afternoon_activities = ["游览", "购物", "参观博物馆", "参加户外活动"]
evening_activities = ["体验夜景", "品尝特色晚餐", "参加当地表演", "散步"]

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

# 新增：火车票和飞机票API配置
TRAIN_API_KEY = env_vars.get("TRAIN_API_KEY", "")
FLIGHT_API_KEY = env_vars.get("FLIGHT_API_KEY", "")

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

# 新增：查询火车票班次
def query_train_tickets(origin, destination, date):
    """查询指定日期从出发地到目的地的火车班次"""
    if not TRAIN_API_KEY:
        return [{"车次": "G101", "出发时间": "08:00", "到达时间": "12:00", "历时": "4小时", "二等座": "¥553", "一等座": "¥933"},
                {"车次": "G103", "出发时间": "09:00", "到达时间": "13:00", "历时": "4小时", "二等座": "¥553", "一等座": "¥933"},
                {"车次": "G105", "出发时间": "10:00", "到达时间": "14:00", "历时": "4小时", "二等座": "¥553", "一等座": "¥933"}]
    
    # 实际API调用（示例，需替换为真实API）
    try:
        url = "https://api.example.com/train/tickets"
        params = {
            "key": TRAIN_API_KEY,
            "origin": origin,
            "destination": destination,
            "date": date
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json().get("trains", [])
        else:
            return []
    except Exception as e:
        print(f"查询火车票失败: {e}")
        return []

# 新增：查询飞机票班次
def query_flight_tickets(origin, destination, date):
    """查询指定日期从出发地到目的地的飞机班次"""
    if not FLIGHT_API_KEY:
        return [{"航班号": "CA1234", "航空公司": "国航", "出发时间": "07:30", "到达时间": "10:30", "历时": "3小时", "经济舱": "¥1200", "商务舱": "¥3500"},
                {"航班号": "MU2345", "航空公司": "东航", "出发时间": "09:30", "到达时间": "12:30", "历时": "3小时", "经济舱": "¥1100", "商务舱": "¥3200"},
                {"航班号": "CZ3456", "航空公司": "南航", "出发时间": "13:30", "到达时间": "16:30", "历时": "3小时", "经济舱": "¥1000", "商务舱": "¥2900"}]
    
    # 实际API调用（示例，需替换为真实API）
    try:
        url = "https://api.example.com/flight/tickets"
        params = {
            "key": FLIGHT_API_KEY,
            "origin": origin,
            "destination": destination,
            "date": date
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json().get("flights", [])
        else:
            return []
    except Exception as e:
        print(f"查询飞机票失败: {e}")
        return []

def generate_travel_plan(place1, date1, place2, date2):
    """生成查票网址和旅行规划"""
    try:
        # 验证日期格式和有效性
        if not is_valid_date(date1):
            return "日期格式错误或日期必须在当日或之后", "请检查出发日期", None, None
        if not is_valid_date(date2):
            return "日期格式错误或日期必须在当日或之后", "请检查返回日期", None, None
            
        # 验证返回日期是否晚于出发日期
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            return "返回日期不能早于出发日期", "请检查日期顺序", None, None
        
        # 计算旅行天数
        days = (ret_date - dep_date).days + 1
        
        # 验证旅行天数不超过30天
        if days > 30:
            return "旅游时间过长，建议不超过30天", "请缩短旅行日期", None, None
        
        # 生成查票网址（示例使用携程API格式，需替换为真实API）
        ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{place2}-{date1}-{date2}"
        
        # 创建可点击的HTML链接
        ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看更多票务信息</a>'
        
        # 新增：查询火车票和飞机票
        train_tickets = query_train_tickets(place1, place2, date1)
        flight_tickets = query_flight_tickets(place1, place2, date1)
        
        # 创建票务信息HTML表格
        tickets_html = generate_tickets_html(train_tickets, flight_tickets)
        
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
        
        return ticket_link, travel_plan_data, train_tickets, flight_tickets
    
    except ValueError:
        return "日期格式错误，请使用YYYY-MM-DD格式", "请检查输入", None, None
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划", None, None

# 新增：生成票务信息HTML表格
def generate_tickets_html(train_tickets, flight_tickets):
    """生成火车票和飞机票的HTML表格"""
    html = "<div style='margin-top:20px;'>"
    
    # 火车票表格
    if train_tickets:
        html += "<h3>火车票班次</h3>"
        html += "<table class='ticket-table' style='width:100%; border-collapse:collapse; margin-bottom:20px;'>"
        html += "<tr style='background-color:#f2f2f2;'>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>车次</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>出发时间</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>到达时间</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>历时</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>二等座</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>一等座</th>"
        html += "</tr>"
        
        for train in train_tickets[:5]:  # 只显示前5条
            html += "<tr>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['车次']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['出发时间']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['到达时间']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['历时']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['二等座']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{train['一等座']}</td>"
            html += "</tr>"
        
        html += "</table>"
    
    # 飞机票表格
    if flight_tickets:
        html += "<h3>飞机票班次</h3>"
        html += "<table class='ticket-table' style='width:100%; border-collapse:collapse;'>"
        html += "<tr style='background-color:#f2f2f2;'>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>航班号</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>航空公司</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>出发时间</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>到达时间</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>历时</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>经济舱</th>"
        html += "<th style='border:1px solid #ddd; padding:8px; text-align:left;'>商务舱</th>"
        html += "</tr>"
        
        for flight in flight_tickets[:5]:  # 只显示前5条
            html += "<tr>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['航班号']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['航空公司']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['出发时间']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['到达时间']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['历时']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['经济舱']}</td>"
            html += f"<td style='border:1px solid #ddd; padding:8px;'>{flight['商务舱']}</td>"
            html += "</tr>"
        
        html += "</table>"
    
    html += "</div>"
    return html

def generate_travel_plan_multi(place1, date1, dests, date2):
    """
    流式输出旅行规划，每次yield部分DataFrame
    """
    try:
        if not is_valid_date(date1):
            yield "日期格式错误或日期必须在当日或之后", None, None, None
            return
        if not is_valid_date(date2):
            yield "日期格式错误或日期必须在当日或之后", None, None, None
            return
        if not dests:
            yield "请至少填写一个目的地", None, None, None
            return
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            yield "返回日期不能早于出发日期", None, None, None
            return
        total_days = (ret_date - dep_date).days + 1
        if total_days > 30:
            yield "旅游时间过长，建议不超过30天", None, None, None
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
        
        # 新增：初始化票务信息
        train_tickets = []
        flight_tickets = []
        
        # 先yield初始状态
        yield ticket_link, pd.DataFrame([], columns=headers), train_tickets, flight_tickets

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
                        
                        # 新增：当收集到一定数量的行程时，查询票务信息
                        if len(yielded_rows) >= 3 and not train_tickets and not flight_tickets:
                            train_tickets = query_train_tickets(place1, dests[0], date1)
                            flight_tickets = query_flight_tickets(place1, dests[0], date1)
                        
                        yield ticket_link, df, train_tickets, flight_tickets
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
            yield ticket_link, df, train_tickets, flight_tickets
    except Exception as e:
        yield f"发生错误: {str(e)}", None, None, None

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
            return "日期格式错误或日期必须在当日或之后", "请检查出发日期", None, None
        if not is_valid_date(date2):
            return "日期格式错误或日期必须在当日或之后", "请检查返回日期", None, None
        if not dests:
            return "请至少填写一个目的地", "请检查输入", None, None
        dep_date = datetime.strptime(date1, "%Y-%m-%d").date()
        ret_date = datetime.strptime(date2, "%Y-%m-%d").date()
        if ret_date < dep_date:
            return "返回日期不能早于出发日期", "请检查日期顺序", None, None
        total_days = (ret_date - dep_date).days + 1
        if total_days > 30:
            return "旅游时间过长，建议不超过30天", "请缩短旅行日期", None, None

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
                    
                    # 新增：查询票务信息
                    train_tickets = query_train_tickets(place1, dests[0], date1)
                    flight_tickets = query_flight_tickets(place1, dests[0], date1)
                    
                    return ticket_link, df, train_tickets, flight_tickets
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
        all_attractions = []
        travel_plan_data = []
        day_idx = 1
        cur_date = dep_date

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
        travel_plan_data = pd.DataFrame(travel_plan_data, columns=headers)
        
        # 新增：查询票务信息
        train_tickets = query_train_tickets(place1, dests[0], date1)
        flight_tickets = query_flight_tickets(place1, dests[0], date1)
        
        return ticket_link, travel_plan_data, train_tickets, flight_tickets
    except Exception as e:
        return f"发生错误: {str(e)}", "无法生成旅行规划", None, None

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
                
            route = amap.calculate_driving_route(start_lng, start_lat, end_lng, end_lat)  # 正确函数
            
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

        # 查票结果展示
        ticket_url_output = gr.HTML(label="查票网址")
        tickets_output = gr.HTML(label="票务信息")
        
        # 旅行规划表格
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
                yield "请至少填写一个目的地和返程日期", pd.DataFrame(columns=["日期", "时间", "地点", "活动", "交通"]), [], []
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
            with open(str(gui_path), "w", encoding="utf-8") as f:
                json.dump(gui_plan, f, ensure_ascii=False, indent=2)

            # 2. 启动route_planner.py作为子进程
            import subprocess
            import sys
            route_planner_path = base_dir / "src" / "utils" / "route_planner.py"
            try:
                # 先删除可能存在的旧输出文件
                if llm_path.exists():
                    llm_path.unlink()
                
                # 启动子进程
                proc = subprocess.Popen(
                    [sys.executable, str(route_planner_path)],
                    cwd=str(save_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # 3. 流式读取输出文件
                headers = ["日期", "时间", "地点", "活动", "交通"]
                ticket_url = f"https://flights.ctrip.com/international/search/round-{place1}-{dests[0]}-{date1}-{date2_val}"
                ticket_link = f'<a href="{ticket_url}" target="_blank">点击查看票务信息</a>'
                
                # 初始化票务信息
                train_tickets = []
                flight_tickets = []
                
                # 先yield初始状态
                yield ticket_link, pd.DataFrame([], columns=headers), train_tickets, flight_tickets
                
                # 等待文件创建并开始读取
                max_wait = 30  # 最多等待30秒
                waited = 0
                while not llm_path.exists() and waited < max_wait:
                    time.sleep(0.5)
                    waited += 0.5
                
                # 读取文件内容
                prev_size = 0
                max_attempts = 60  # 最多尝试60次，约30秒
                attempts = 0
                
                while proc.poll() is None or (llm_path.exists() and os.path.getsize(llm_path) > prev_size):
                    if llm_path.exists():
                        try:
                            with open(str(llm_path), "r", encoding="utf-8") as f:
                                content = f.read()
                            
                            # 解析JSONL内容
                            lines = content.strip().split('\n')
                            if lines and lines[-1].strip():
                                try:
                                    data = []
                                    for line in lines:
                                        if line.strip():
                                            data.append(json.loads(line))
                                    
                                    if data:
                                        # 转换为DataFrame
                                        df = pd.DataFrame(data)
                                        
                                        # 标准化列名
                                        if not df.empty:
                                            if "date" in df.columns:
                                                df = df.rename(columns={"date": "日期"})
                                            if "time" in df.columns:
                                                df = df.rename(columns={"time": "时间"})
                                            if "location" in df.columns:
                                                df = df.rename(columns={"location": "地点"})
                                            if "activity" in df.columns:
                                                df = df.rename(columns={"activity": "活动"})
                                            if "transport" in df.columns:
                                                df = df.rename(columns={"transport": "交通"})
                                            
                                            # 确保所有必要的列都存在
                                            for col in headers:
                                                if col not in df.columns:
                                                    df[col] = ""
                                            
                                            # 按日期和时间排序
                                            if "日期" in df.columns and "时间" in df.columns:
                                                # 处理日期格式
                                                def parse_date(date_str):
                                                    try:
                                                        return datetime.strptime(date_str, "%Y-%m-%d")
                                                    except:
                                                        return datetime.min
                                                
                                                df['_date'] = df['日期'].apply(parse_date)
                                                df = df.sort_values(by=['_date', '时间'])
                                                df = df.drop('_date', axis=1)
                                            
                                            # 新增：当收集到一定数量的行程时，查询票务信息
                                            if len(df) >= 3 and not train_tickets and not flight_tickets:
                                                train_tickets = query_train_tickets(place1, dests[0], date1)
                                                flight_tickets = query_flight_tickets(place1, dests[0], date1)
                                            
                                            yield ticket_link, df[headers], train_tickets, flight_tickets
                                except json.JSONDecodeError as e:
                                    print(f"JSON解析错误: {e}")
                            
                            prev_size = os.path.getsize(llm_path)
                        except Exception as e:
                            print(f"读取文件错误: {e}")
                    
                    time.sleep(0.5)
                    attempts += 1
                    if attempts > max_attempts:
                        break
                
                # 最后检查一次
                if llm_path.exists() and os.path.getsize(llm_path) > 0:
                    try:
                        with open(str(llm_path), "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        lines = content.strip().split('\n')
                        data = []
                        for line in lines:
                            if line.strip():
                                data.append(json.loads(line))
                        
                        if data:
                            df = pd.DataFrame(data)
                            
                            # 标准化列名
                            if not df.empty:
                                if "date" in df.columns:
                                    df = df.rename(columns={"date": "日期"})
                                if "time" in df.columns:
                                    df = df.rename(columns={"time": "时间"})
                                if "location" in df.columns:
                                    df = df.rename(columns={"location": "地点"})
                                if "activity" in df.columns:
                                    df = df.rename(columns={"activity": "活动"})
                                if "transport" in df.columns:
                                    df = df.rename(columns={"transport": "交通"})
                                
                                # 确保所有必要的列都存在
                                for col in headers:
                                    if col not in df.columns:
                                        df[col] = ""
                                
                                # 按日期和时间排序
                                if "日期" in df.columns and "时间" in df.columns:
                                    df['_date'] = df['日期'].apply(parse_date)
                                    df = df.sort_values(by=['_date', '时间'])
                                    df = df.drop('_date', axis=1)
                                
                                yield ticket_link, df[headers], train_tickets, flight_tickets
                    except Exception as e:
                        print(f"最后读取文件错误: {e}")
                
                # 如果子进程还在运行，等待它结束
                if proc.poll() is None:
                    proc.wait()
                
                # 检查是否有错误输出
                if proc.returncode != 0:
                    try:
                        stderr = proc.stderr.read().decode('utf-8')
                        print(f"子进程错误: {stderr}")
                    except:
                        pass
            except Exception as e:
                print(f"生成行程计划错误: {e}")
                yield f"生成行程计划错误: {str(e)}", pd.DataFrame(columns=headers), [], []
        
        # --------- 伪流式输出实现 end ---------

        # 提交按钮事件
        submit_btn.click(
            update_travel_plan,
            inputs=[place1, date1] + dest_inputs + [date2],
            outputs=[ticket_url_output, travel_plan_output, tickets_output, save_status]
        )

        # 清除按钮事件
        def clear_all():
            return (
                "", "", *([gr.Textbox.update(value="", visible=i == 0)] for i in range(MAX_INPUTS)), 
                "", "", pd.DataFrame(columns=["日期", "时间", "地点", "活动", "交通"]), 
                0, "", ""
            )
        
        clear_btn.click(
            clear_all,
            outputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, current_index, tickets_output, save_status]
        )

        # 保存按钮事件
        save_btn.click(
            lambda p1, d1, *args: save_travel_plan(
                p1, d1, 
                args[0] if args and args[0] else "目的地", 
                args[-2] if args and len(args) > 1 else "",
                args[-3] if args and len(args) > 2 else "",
                args[-4] if args and len(args) > 3 else pd.DataFrame(),
                args[-1] if args and len(args) > 4 else None
            ),
            inputs=[place1, date1] + dest_inputs + [date2, ticket_url_output, travel_plan_output, filename_input],
            outputs=[save_status]
        )

    # 地图导航Tab
    with gr.Tab("地图导航"):
        gr.Markdown("### 输入多个景点或地址，获取最佳路线规划和地图导航")
        with gr.Row():
            with gr.Column():
                places_input = gr.Textbox(
                    label="景点或地址（用逗号分隔）",
                    placeholder="例如：故宫,天安门广场,颐和园,八达岭长城"
                )
                transport_mode = gr.Radio(
                    ["驾车", "公交", "步行", "骑行"],
                    label="出行方式",
                    value="驾车"
                )
                optimize_route = gr.Checkbox(label="优化路线顺序", value=True)
                show_details = gr.Checkbox(label="显示路线详情", value=True)
            with gr.Column():
                map_output = gr.HTML(label="路线地图")
                route_info = gr.Textbox(label="路线信息", lines=10, interactive=False)
        
        with gr.Row():
            clear_map_btn = gr.Button("清除")
            generate_map_btn = gr.Button("生成路线", variant="primary")
        
        generate_map_btn.click(
            generate_route_map,
            inputs=[places_input, transport_mode, optimize_route, show_details],
            outputs=[map_output, route_info]
        )
        
        clear_map_btn.click(
            lambda: ("", "", ""),
            outputs=[places_input, map_output, route_info]
        )

    # 保存的计划Tab
    with gr.Tab("我的旅行计划"):
        gr.Markdown("### 查看、加载和管理已保存的旅行计划")
        with gr.Row():
            with gr.Column():
                plans_list = gr.Dropdown(
                    choices=[],
                    label="已保存的计划",
                    interactive=True,
                    multiselect=False
                )
                load_btn = gr.Button("📖 加载计划")
                delete_btn = gr.Button("🗑️ 删除计划")
            with gr.Column():
                loaded_plan_info = gr.Textbox(label="计划信息", lines=5, interactive=False)
                loaded_ticket_url = gr.HTML(label="查票链接")
                loaded_travel_plan = gr.Dataframe(
                    headers=["日期", "时间", "地点", "活动", "交通"],
                    label="旅行规划",
                    interactive=False
                )
        
        # 加载已保存的计划列表
        def update_plans_list():
            plans = list_saved_plans()
            choices = [f"{p['filename']} | {p['place1']} → {p['place2']} | {p['date1']} - {p['date2']}" for p in plans]
            return gr.Dropdown.update(choices=choices)
        
        # 页面加载时更新计划列表
        demo.load(update_plans_list, outputs=plans_list)
        
        # 加载按钮事件
        load_btn.click(
            lambda filename: load_travel_plan(filename.split(" | ")[0] if filename else ""),
            inputs=[plans_list],
            outputs=[place1, date1, dest_inputs[0], date2, loaded_ticket_url, loaded_travel_plan, loaded_plan_info]
        )
        
        # 删除按钮事件
        delete_btn.click(
            lambda filename: delete_travel_plan(filename.split(" | ")[0] if filename else ""),
            inputs=[plans_list],
            outputs=[loaded_plan_info, plans_list]
        ).then(
            update_plans_list,
            outputs=plans_list
        )

    # 语音助手Tab
    with gr.Tab("语音助手"):
        gr.Markdown("### 语音输入查询旅行信息")
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(source="microphone", type="filepath", label="语音输入")
                voice_query_btn = gr.Button("🔊 语音查询", variant="primary")
                text_output = gr.Textbox(label="识别结果", interactive=False)
            with gr.Column():
                chatbot = gr.Chatbot(label="对话")
                chat_history = gr.State([])
                user_message = gr.Textbox(label="文字输入", placeholder="请输入您的问题...")
                send_btn = gr.Button("发送")
        
        # 语音查询按钮事件
        voice_query_btn.click(
            speech_to_text,
            inputs=[audio_input],
            outputs=[text_output]
        ).then(
            chat_with_agent,
            inputs=[text_output, chat_history],
            outputs=[user_message, chatbot]
        )
        
        # 文字发送按钮事件
        send_btn.click(
            chat_with_agent,
            inputs=[user_message, chat_history],
            outputs=[user_message, chatbot]
        )

    # 城市景点地图Tab
    with gr.Tab("城市景点地图"):
        gr.Markdown("### 查询城市或景点地图")
        with gr.Row():
            with gr.Column():
                city_place_input = gr.Textbox(label="城市或景点名称", placeholder="例如：北京故宫")
                map_date_input = gr.Textbox(label="日期（可选）", placeholder="YYYY-MM-DD")
                generate_city_map_btn = gr.Button("生成地图", variant="primary")
            with gr.Column():
                city_map_output = gr.Image(label="地图")
                city_map_info = gr.Textbox(label="地点信息", interactive=False)
        
        generate_city_map_btn.click(
            generate_city_map,
            inputs=[city_place_input, map_date_input],
            outputs=[city_map_output, city_map_info]
        )

# 设置中文字体
# 由于无法直接修改系统字体，建议在Gradio界面中使用支持中文的字体
# 启动应用
if __name__ == "__main__":
    demo.launch()
