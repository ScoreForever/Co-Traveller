import requests
import sys
import json
import os
from dotenv import load_dotenv

# 加载API.env
env_path = os.path.join(os.path.dirname(__file__), '../../API.env')
load_dotenv(env_path)
AIRPLANE_AUTHCODE = os.getenv("AIRPLANE_AUTHCODE")

# 简单城市名到三字码映射（可扩展）
CITY_TO_AIRPORT_CODE = {
    "北京": "PEK",
    "上海": "SHA",  # 上海虹桥
    "浦东": "PVG",
    "重庆": "CKG",
    # ...可补充更多...
}

def city_to_airport_code(city):
    # 支持“上海浦东”等写法
    for k, v in CITY_TO_AIRPORT_CODE.items():
        if k in city:
            return v
    return ""

def query_flights(leave_city, arrive_city, date, authcode=None):
    """
    查询两地间可选航班
    :param leave_city: 出发城市名
    :param arrive_city: 到达城市名
    :param date: 日期 yyyy-MM-dd
    :param authcode: 鉴权码
    :return: 航班信息列表
    """
    leave_code = city_to_airport_code(leave_city)
    arrive_code = city_to_airport_code(arrive_city)
    if not leave_code or not arrive_code:
        print(f"未找到城市三字码: {leave_city} 或 {arrive_city}")
        return []
    if authcode is None:
        authcode = AIRPLANE_AUTHCODE
    if not authcode:
        raise ValueError("未设置AIRPLANE_AUTHCODE，请在API.env中配置。")
    url = (
        f"https://api.hangxx.com/restapi/airQuery/flightTime"
        f"?authCode={authcode}&leaveCode={leave_code}&arriveCode={arrive_code}&queryDate={date}"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("code") == 200 and "flightInfos" in data:
            return data["flightInfos"]
        else:
            print("API返回异常:", data.get("message", data))
            return []
    except Exception as e:
        print("查询航班失败:", e)
        return []

def extract_flight_trips_from_plan(plan_path):
    """
    从旅行规划文件中提取需要乘坐飞机的日程
    :return: [(date, start, end, transport, activity, time, next_time, next_date), ...]
    """
    trips = []
    keywords = ["飞机", "航班", "飞"]
    if not os.path.exists(plan_path):
        print(f"未找到旅行规划文件: {plan_path}")
        return trips
    with open(plan_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        try:
            item = json.loads(line)
        except Exception:
            try:
                item = json.loads(line.strip().rstrip(","))
            except Exception:
                continue
        transport = item.get("transport", "")
        if any(k in transport for k in keywords):
            date = item.get("date", "")
            start = item.get("location", "")
            activity = item.get("activity", "")
            time = item.get("time", "")
            # 目的地一般在“前往XXX”或“到达XXX”或“抵达XXX”
            import re
            m = re.search(r"(前往|到达|抵达)([\u4e00-\u9fa5]+)", activity)
            if m:
                end = m.group(2)
            else:
                end = ""
            # 查找下一条的时间和日期作为到达时间和到达日期
            next_time = ""
            next_date = date
            if idx + 1 < len(lines):
                try:
                    next_item = json.loads(lines[idx + 1])
                except Exception:
                    try:
                        next_item = json.loads(lines[idx + 1].strip().rstrip(","))
                    except Exception:
                        next_item = {}
                if next_item.get("date", ""):
                    next_date = next_item.get("date", date)
                    next_time = next_item.get("time", "")
            trips.append((date, start, end, transport, activity, time, next_time, next_date))
    return trips

def datetime_in_range(dep_date, dep_time, arr_date, arr_time, plan_dep_date, plan_dep_time, plan_arr_date, plan_arr_time):
    """
    检查航班的出发/到达日期时间是否在规划的区间内
    """
    try:
        from datetime import datetime
        dt_format = "%Y-%m-%d %H:%M"
        flight_dep = datetime.strptime(f"{dep_date} {dep_time}", dt_format)
        flight_arr = datetime.strptime(f"{arr_date} {arr_time}", dt_format)
        plan_dep = datetime.strptime(f"{plan_dep_date} {plan_dep_time}", dt_format)
        plan_arr = datetime.strptime(f"{plan_arr_date} {plan_arr_time}", dt_format)
        return (flight_dep >= plan_dep) and (flight_arr <= plan_arr) and (flight_dep < flight_arr)
    except Exception:
        return False

def add_day_if_needed(dep_time, arr_time):
    """
    判断到达时间是否跨天
    """
    try:
        from datetime import datetime
        t_format = "%H:%M"
        t_dep = datetime.strptime(dep_time, t_format)
        t_arr = datetime.strptime(arr_time, t_format)
        return 1 if t_arr < t_dep else 0
    except Exception:
        return 0

if __name__ == "__main__":
    print("\n=== 根据旅行规划自动检索飞机票 ===")
    plan_path = os.path.join(os.path.dirname(__file__), "../../temp/travel_plans/route_planning_LLMoutput.json")
    trips = extract_flight_trips_from_plan(plan_path)
    if not trips:
        print("未找到需要乘坐飞机的日程。")
    else:
        for idx, (date, start, end, transport, activity, time, next_time, next_date) in enumerate(trips, 1):
            if not start or not end or not date or not time or not next_time or not next_date:
                print(f"\n[{idx}] 行程信息不完整，跳过: {activity}")
                continue
            print(f"\n[{idx}] {date} {start} → {end} 交通方式: {transport} 活动: {activity} 时间段: {date} {time}~{next_date} {next_time}")
            try:
                flights = query_flights(start, end, date=date)
                filtered_flights = []
                for flight in flights:
                    dep_time = flight.get("planLeaveTime", "")[-8:-3]  # "2010-10-28 10:00:00" -> "10:00"
                    arr_time = flight.get("planArriveTime", "")[-8:-3]
                    if dep_time and arr_time:
                        # 计算到达日期
                        from datetime import datetime, timedelta
                        add_days = add_day_if_needed(dep_time, arr_time)
                        arr_date = date
                        if add_days:
                            arr_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                        # 判断航班的出发/到达是否在规划区间内
                        if datetime_in_range(date, dep_time, arr_date, arr_time, date, time, next_date, next_time):
                            filtered_flights.append(flight)
                if not filtered_flights:
                    print("  未查询到符合时间段的航班。")
                else:
                    for flight in filtered_flights:
                        print(
                            f"  {flight.get('flightNo','')} {flight.get('airlineCompany','')} "
                            f"{flight.get('planLeaveTime','')}→{flight.get('planArriveTime','')} "
                            f"{flight.get('leavePort','')}({flight.get('leavePortCode','')})→"
                            f"{flight.get('arrivePort','')}({flight.get('arrivePortCode','')}) "
                            f"状态:{flight.get('state','')}"
                        )
            except Exception as e:
                print(f"  查询失败: {e}")
