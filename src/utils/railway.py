import requests
import sys
import json
import os
from dotenv import load_dotenv

# 加载API.env
env_path = os.path.join(os.path.dirname(__file__), '../../API.env')
load_dotenv(env_path)
RAILWAY_APPCODE = os.getenv("RAILWAY_APPCODE")

def query_trains(start, end, date=None, ishigh=None, appcode=None):
    """
    查询两地间可选火车班次
    :param start: 出发地（如"北京"）
    :param end: 目的地（如"上海"）
    :param date: 日期（如"2025-06-25"，可选）
    :param ishigh: 是否高铁（0/1，可选）
    :param appcode: 阿里云市场AppCode（可选，默认读取环境变量）
    :return: 返回火车班次信息的列表
    """
    import urllib.parse
    url_host = 'http://jisutrainf.market.alicloudapi.com'
    url_path = '/train/station2s'
    url = url_host + url_path

    params = {
        "start": start,
        "end": end
    }
    if date:
        params["date"] = date
    if ishigh is not None:
        params["ishigh"] = str(ishigh)

    # urlencode参数
    querys = urllib.parse.urlencode(params)
    full_url = url + '?' + querys

    # 优先使用传入的appcode，否则用环境变量
    if appcode is None:
        appcode = RAILWAY_APPCODE
    if not appcode:
        raise ValueError("AppCode未设置，请在API.env中配置RAILWAY_APPCODE或传入appcode参数。")

    headers = {
        "Authorization": "APPCODE " + appcode,
        "Content-Type": "application/json; charset=UTF-8"
    }

    try:
        import urllib.request
        req = urllib.request.Request(full_url, headers=headers)
        response = urllib.request.urlopen(req)
        content = response.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        data = json.loads(content)
        if data.get("status") == 0 and "result" in data:
            # result直接就是list
            if isinstance(data["result"], list):
                return data["result"]
            # 兼容部分API返回dict的情况
            elif isinstance(data["result"], dict) and "list" in data["result"]:
                return data["result"]["list"]
            else:
                return []
        else:
            print("API返回异常:", data.get("msg", data))
            return []
    except Exception as e:
        print("查询火车班次失败:", e)
        return []

def extract_train_trips_from_plan(plan_path):
    """
    从旅行规划文件中提取需要乘坐火车/高铁/动车的日程
    :param plan_path: 旅行规划json文件路径
    :return: [(date, start, end, transport, activity, time, next_time, next_date), ...]
    """
    trips = []
    keywords = ["火车", "高铁", "动车"]
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
            # 目的地一般在“前往XXX”或“到达XXX”
            import re
            m = re.search(r"(前往|到达)([\u4e00-\u9fa5]+)", activity)
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

def time_in_range(start_time, end_time, check_time):
    """
    判断check_time是否在[start_time, end_time]区间内
    时间格式: "HH:MM"
    """
    try:
        from datetime import datetime
        t_format = "%H:%M"
        t0 = datetime.strptime(start_time, t_format)
        t1 = datetime.strptime(end_time, t_format)
        t = datetime.strptime(check_time, t_format)
        return t0 <= t <= t1
    except Exception:
        return False

def datetime_less_than(date1, time1, date2, time2):
    """
    判断date1 time1 是否早于 date2 time2
    日期格式: YYYY-MM-DD，时间格式: HH:MM
    """
    try:
        from datetime import datetime
        dt_format = "%Y-%m-%d %H:%M"
        dt1 = datetime.strptime(f"{date1} {time1}", dt_format)
        dt2 = datetime.strptime(f"{date2} {time2}", dt_format)
        return dt1 < dt2
    except Exception:
        return False

def datetime_in_range(dep_date, dep_time, arr_date, arr_time, plan_dep_date, plan_dep_time, plan_arr_date, plan_arr_time):
    """
    检查火车的出发/到达日期时间是否在规划的区间内
    """
    try:
        from datetime import datetime
        dt_format = "%Y-%m-%d %H:%M"
        train_dep = datetime.strptime(f"{dep_date} {dep_time}", dt_format)
        train_arr = datetime.strptime(f"{arr_date} {arr_time}", dt_format)
        plan_dep = datetime.strptime(f"{plan_dep_date} {plan_dep_time}", dt_format)
        plan_arr = datetime.strptime(f"{plan_arr_date} {plan_arr_time}", dt_format)
        # 要求：出发时间>=规划出发，且到达时间<=规划到达，且出发时间<到达时间
        return (train_dep >= plan_dep) and (train_arr <= plan_arr) and (train_dep < train_arr)
    except Exception:
        return False

def add_day_if_needed(dep_time, arr_time):
    """
    判断到达时间是否跨天（如出发时间11:20，到达时间04:45，说明到达是次日），
    如果是，返回1，否则返回0
    """
    try:
        from datetime import datetime
        t_format = "%H:%M"
        t_dep = datetime.strptime(dep_time, t_format)
        t_arr = datetime.strptime(arr_time, t_format)
        # 到达时间小于出发时间，说明跨天
        return 1 if t_arr < t_dep else 0
    except Exception:
        return 0

if __name__ == "__main__":
    # 新增：自动读取旅行规划并检索火车票
    print("\n=== 根据旅行规划自动检索火车票 ===")
    # 路径可根据实际情况调整
    plan_path = os.path.join(os.path.dirname(__file__), "../../temp/travel_plans/route_planning_LLMoutput.json")
    trips = extract_train_trips_from_plan(plan_path)
    if not trips:
        print("未找到需要乘坐火车的日程。")
    else:
        for idx, (date, start, end, transport, activity, time, next_time, next_date) in enumerate(trips, 1):
            if not start or not end or not date or not time or not next_time or not next_date:
                print(f"\n[{idx}] 行程信息不完整，跳过: {activity}")
                continue
            print(f"\n[{idx}] {date} {start} → {end} 交通方式: {transport} 活动: {activity} 时间段: {date} {time}~{next_date} {next_time}")
            try:
                trains = query_trains(start, end, date=date)
                filtered_trains = []
                for train in trains:
                    dep_time = train.get("departuretime", "")
                    arr_time = train.get("arrivaltime", "")
                    if dep_time and arr_time:
                        # 计算到达日期
                        from datetime import datetime, timedelta
                        add_days = add_day_if_needed(dep_time, arr_time)
                        arr_date = date
                        if add_days:
                            arr_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                        # 判断火车的出发/到达是否在规划区间内（允许跨天）
                        if datetime_in_range(date, dep_time, arr_date, arr_time, date, time, next_date, next_time):
                            filtered_trains.append(train)
                if not filtered_trains:
                    print("  未查询到符合时间段的火车班次。")
                else:
                    for train in filtered_trains:
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
                        print(f"  {train.get('trainno','')} {train.get('type','')} {train.get('departuretime','')}→{train.get('arrivaltime','')} 历时{train.get('costtime','')} {price_str}")
            except Exception as e:
                print(f"  查询失败: {e}")
