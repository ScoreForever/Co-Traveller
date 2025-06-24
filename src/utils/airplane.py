import requests
import sys
import json
import os
from dotenv import load_dotenv
import csv

# 加载API.env
env_path = os.path.join(os.path.dirname(__file__), '../../API.env')
load_dotenv(env_path)
AIRPLANE_AUTHCODE = os.getenv("AIRPLANE_AUTHCODE")

# 取消内置映射
# CITY_TO_AIRPORT_CODE = {
#     "北京": "PEK",
#     "上海": "SHA",  # 上海虹桥
#     "浦东": "PVG",
#     "重庆": "CKG",
#     # ...可补充更多...
# }

# 全局机场三字码映射表
AIRPORT_CODE_MAP = {}

def load_airport_codes(filepath):
    """
    从CSV加载机场三字码映射，支持城市名、机场名、简称等多种方式模糊查找
    """
    code_map = {}
    if not os.path.exists(filepath):
        print(f"机场三字码文件不存在: {filepath}")
        return code_map
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("机场三字码", "").strip().upper()
            city = row.get("城市名称", "").strip()
            airport = row.get("机场名称", "").strip()
            short = row.get("机场简称", "").strip()
            # 建立多重映射
            if code:
                if city:
                    code_map[city] = code
                if airport:
                    code_map[airport] = code
                if short:
                    code_map[short] = code
    return code_map

# 初始化机场三字码映射
airport_csv_path = os.path.join(os.path.dirname(__file__), "../../data/reference/airportcode.csv")
AIRPORT_CODE_MAP = load_airport_codes(airport_csv_path)

def city_to_airport_code(city, prefer_airport_name=None):
    """
    仅从外部机场三字码库查询，优先用prefer_airport_name（如“首都国际机场”），否则用city。
    支持机场名称、简称、城市名多重模糊查找。
    """
    target_list = []
    if prefer_airport_name:
        target_list.append(prefer_airport_name)
    if city:
        target_list.append(city)
    for target in target_list:
        if not target:
            continue
        # 优先查机场名称/简称
        for k, v in AIRPORT_CODE_MAP.items():
            if k and k in target:
                return v
        # 针对“xxx国际”等，自动补全“机场”后查找
        if not target.endswith("机场"):
            target_with_airport = target + "机场"
            for k, v in AIRPORT_CODE_MAP.items():
                if k and k in target_with_airport:
                    return v
        # 如果是“xxx机场”，尝试去掉“机场”后查城市名
        if target.endswith("机场"):
            target_simple = target.replace("机场", "")
            for k, v in AIRPORT_CODE_MAP.items():
                if k and k in target_simple:
                    return v
            for k, v in AIRPORT_CODE_MAP.items():
                if k and k == target_simple:
                    return v
        # 再查城市名
        for k, v in AIRPORT_CODE_MAP.items():
            if k and k == target:
                return v
        # 针对“xxx国际”再查
        if "国际" in target:
            target_no_guoji = target.replace("国际", "")
            for k, v in AIRPORT_CODE_MAP.items():
                if k and k in target_no_guoji:
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
    first_departure_location = ""
    if lines:
        try:
            first_item = json.loads(lines[0])
        except Exception:
            try:
                first_item = json.loads(lines[0].strip().rstrip(","))
            except Exception:
                first_item = {}
        first_departure_location = first_item.get("location", "")
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
            import re
            m = re.search(r"(前往|到达|抵达)([\u4e00-\u9fa5]+)", activity)
            m_airport = re.search(r"(首都国际机场|浦东机场|虹桥国际机场|江北国际机场|双流国际机场|白云国际机场|宝安国际机场|萧山国际机场|咸阳国际机场|禄口国际机场|太平国际机场|凤凰国际机场|美兰国际机场|龙洞堡国际机场|高崎国际机场|其他机场)", activity)
            m_from = re.search(r"从([\u4e00-\u9fa5]+)(机场)?出发", activity)
            m_return = re.search(r"返程", activity)
            real_start = start
            real_end = ""
            prefer_start_airport = None
            prefer_end_airport = None
            if m:
                real_end = m.group(2)
                # 如果activity中有具体机场名，优先用
                m_airport_end = re.search(r"抵达([\u4e00-\u9fa5]+机场)", activity)
                if m_airport_end:
                    prefer_end_airport = m_airport_end.group(1)
            elif m_from:
                real_start = m_from.group(1)
                m_airport_start = re.search(r"从([\u4e00-\u9fa5]+机场)出发", activity)
                if m_airport_start:
                    prefer_start_airport = m_airport_start.group(1)
                if idx + 1 < len(lines):
                    try:
                        next_item = json.loads(lines[idx + 1])
                    except Exception:
                        try:
                            next_item = json.loads(lines[idx + 1].strip().rstrip(","))
                        except Exception:
                            next_item = {}
                    real_end = next_item.get("location", "")
            elif m_return:
                real_end = first_departure_location
            else:
                real_end = ""
            # 新增：如果real_start或real_end以“机场”结尾，自动提取城市名（如“北京首都国际机场”→“北京”）
            def airport_to_city(name):
                if name and name.endswith("机场"):
                    return name.replace("机场", "")
                return name
            real_start = airport_to_city(real_start)
            real_end = airport_to_city(real_end)
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
            # 只有起止地都不为空才加入
            if real_start and real_end:
                # 返回时带prefer_start_airport/prefer_end_airport
                trips.append((date, real_start, real_end, transport, activity, time, next_time, next_date, prefer_start_airport, prefer_end_airport))
            else:
                trips.append((date, "", "", transport, activity, time, next_time, next_date, None, None))
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
        for idx, (date, start, end, transport, activity, time, next_time, next_date, prefer_start_airport, prefer_end_airport) in enumerate(trips, 1):
            is_return = "返程" in activity
            if not start or not end or not date or not time or (not is_return and (not next_time or not next_date)):
                print(f"\n[{idx}] 行程信息不完整，跳过: {activity}")
                continue
            print(f"\n[{idx}] {date} {start} → {end} 交通方式: {transport} 活动: {activity} 时间段: {date} {time}~{next_date} {next_time}")
            try:
                # 优先用prefer_start_airport/prefer_end_airport
                # 新增：打印API调用时的起降三字码
                if not (prefer_start_airport or prefer_end_airport):
                    leave_code = city_to_airport_code(start)
                    arrive_code = city_to_airport_code(end)
                else:
                    leave_code = city_to_airport_code(prefer_start_airport if prefer_start_airport else start)
                    arrive_code = city_to_airport_code(prefer_end_airport if prefer_end_airport else end)
                print(f"  [DEBUG] API调用三字码: 起飞={leave_code}, 降落={arrive_code}")
                flights = query_flights(
                    leave_city=start,
                    arrive_city=end,
                    date=date,
                    authcode=None if AIRPLANE_AUTHCODE is None else AIRPLANE_AUTHCODE
                ) if not (prefer_start_airport or prefer_end_airport) else query_flights(
                    leave_city=prefer_start_airport if prefer_start_airport else start,
                    arrive_city=prefer_end_airport if prefer_end_airport else end,
                    date=date,
                    authcode=None if AIRPLANE_AUTHCODE is None else AIRPLANE_AUTHCODE
                )
                filtered_flights = []
                for flight in flights:
                    dep_time = flight.get("planLeaveTime", "")[-8:-3]
                    arr_time = flight.get("planArriveTime", "")[-8:-3]
                    if dep_time and arr_time:
                        from datetime import datetime, timedelta
                        add_days = add_day_if_needed(dep_time, arr_time)
                        arr_date = date
                        if add_days:
                            arr_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                        plan_arr_date = next_date if next_date else date
                        plan_arr_time = next_time if next_time else time
                        if datetime_in_range(date, dep_time, arr_date, arr_time, date, time, plan_arr_date, plan_arr_time):
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
