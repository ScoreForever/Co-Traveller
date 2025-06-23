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

if __name__ == "__main__":
    # 示例用法
    start_city = "包头"
    end_city = "北京"
    date = "2025-06-25"
    trains = query_trains(start_city, end_city, date=date)
    print(f"{start_city} → {end_city} {date} 可选火车班次：")
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
    for train in trains:
        # 典型字段：trainno, type, station, endstation, departuretime, arrivaltime, costtime, 各种票价
        price_info = []
        for key, label in price_fields:
            value = train.get(key, "")
            value_str = str(value).strip()
            # 只输出有票价且不为0、空或"-"的
            if value_str and value_str != "0.0" and value_str != "-":
                price_info.append(f"{label}:{value_str}元")
        price_str = " ".join(price_info)
        print(f"{train.get('trainno','')} {train.get('type','')} {train.get('departuretime','')}→{train.get('arrivaltime','')} 历时{train.get('costtime','')} {price_str}")
