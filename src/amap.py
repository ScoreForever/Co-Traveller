import requests
import folium
from folium.plugins import MiniMap, Fullscreen
from typing import Dict, List, Tuple, Optional
from PIL import Image
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import tempfile
# 高德地图API配置
AMAP_API_KEY = ""  # 将在travel.py中设置

# 在文件顶部添加全局变量
AMAP_API_KEY = None

# 添加设置 API 密钥的函数
def set_amap_api_key(api_key):
    global AMAP_API_KEY
    AMAP_API_KEY = api_key

def search_poi(keyword):
    """使用高德POI搜索API将关键词转换为地址"""
    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": AMAP_API_KEY,
        "keywords": keyword,
        "output": "json",
        "offset": 10,  # 0528最新修改：增加搜索结果数量
        "extensions": "all"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data["status"] == "1" and data["pois"]:
            # 0528最新修改：优化景点类型优先级排序
            poi_priorities = [
                '风景名胜', '旅游景点', '公园广场', '博物馆', '纪念馆', '文化场馆',
                '宗教场所', '古迹遗址', '娱乐休闲', '购物服务', '餐饮服务',
                '商务住宅', '地名地址', '交通设施'
            ]
            
            # 0528最新修改：增加景点评分和热度筛选
            best_poi = None
            best_score = 0
            
            for priority_type in poi_priorities:
                for poi in data["pois"]:
                    poi_type = poi.get("type", "")
                    if priority_type in poi_type:
                        # 计算POI评分（基于类型优先级、评分、距离等）
                        score = calculate_poi_score(poi, priority_type, poi_priorities)
                        if score > best_score:
                            best_score = score
                            best_poi = poi
            
            if best_poi:
                address = best_poi.get("address", "")
                name = best_poi.get("name", "")
                # 0528最新修改：返回更详细的POI信息
                return {
                    'address': f"{address}{name}" if name not in address else address,
                    'name': name,
                    'type': best_poi.get("type", ""),
                    'location': best_poi.get("location", ""),
                    'tel': best_poi.get("tel", ""),
                    'rating': best_poi.get("biz_ext", {}).get("rating", ""),
                    'cost': best_poi.get("biz_ext", {}).get("cost", "")
                }
            else:
                # 0528最新修改：如果没有找到优先级POI，返回第一个结果
                first_poi = data["pois"][0]
                return {
                    'address': first_poi["name"],
                    'name': first_poi["name"],
                    'type': first_poi.get("type", ""),
                    'location': first_poi.get("location", ""),
                    'tel': first_poi.get("tel", ""),
                    'rating': '',
                    'cost': ''
                }
        return None
    except Exception as e:
        print(f"POI搜索失败: {e}")
        return None

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
            print(f"地理编码失败，地址: {address}, 错误信息: {data.get('info', '未知错误')}")
            return None, None, f"无法解析地址: {address}"
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None, None, f"网络请求错误: {str(e)}"
    except Exception as e:
        print(f"地址解析错误: {e}")
        return None, None, f"地址解析错误: {str(e)}"

def geocode_location(location_name: str) -> Optional[Tuple[float, float]]:
    """地理编码：将地名转换为经纬度"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": AMAP_API_KEY,
        "address": location_name,
        "output": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get("status") == "1" and int(data.get("count", 0)) > 0:
            location_str = data["geocodes"][0]["location"]
            lng, lat = location_str.split(",")
            return float(lng), float(lat)
        return None
    except:
        return None

def calculate_walking_route(start_lng: float, start_lat: float, end_lng: float, end_lat: float):
    url = "https://restapi.amap.com/v3/direction/walking"
    params = {
        "key": AMAP_API_KEY,
        "origin": f"{start_lng},{start_lat}",
        "destination": f"{end_lng},{end_lat}",
        "output": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") != "1":
            return {"success": False, "error": f"步行路线请求失败: {data.get('info', '未知错误')}"}
            
        route = data.get("route", {})
        paths = route.get("paths", [{}])
        best_path = paths[0]
        
        return {
            "success": True,
            "distance": best_path.get("distance", 0),
            "duration": best_path.get("duration", 0),
            "steps": [{"instruction": step["instruction"]} for step in best_path.get("steps", [])],
            "polyline": best_path.get("polyline", "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def calculate_driving_route(
    start_lng: float, start_lat: float, 
    end_lng: float, end_lat: float
) -> Dict[str, any]:
    """计算驾车路线规划"""
    url = "https://restapi.amap.com/v3/direction/driving"
    params = {
        "key": AMAP_API_KEY,
        "origin": f"{start_lng},{start_lat}",
        "destination": f"{end_lng},{end_lat}",
        "extensions": "all",
        "output": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # 检查API状态
        if data.get("status") != "1":
            return {"success": False, "error": f"API请求失败: {data.get('info', '未知错误')}"}
        
        # 检查核心字段
        route = data.get("route")
        if not route:
            return {"success": False, "error": "API返回数据中缺少route字段"}
        
        paths = route.get("paths")
        if not paths or len(paths) == 0:
            return {"success": False, "error": "API返回数据中缺少paths字段或paths为空"}
        
        best_route = paths[0]
        
        # 安全提取数值字段并处理空值
        distance_str = best_route.get("distance", "0")
        duration_str = best_route.get("duration", "0")
        
        result = {
            "success": True,
            "distance": int(distance_str) if distance_str.isdigit() else 0,
            "duration": int(duration_str) if duration_str.isdigit() else 0,
            "steps": best_route.get("steps", []),
            "origin": f"{start_lng},{start_lat}",
            "destination": f"{end_lng},{end_lat}",
            "origin_name": "",
            "destination_name": ""
        }
        
        # 处理路线坐标（polyline）
        if "polyline" in best_route:
            result["polyline"] = best_route["polyline"]
        elif "steps" in best_route:
            polyline_points = [step.get("polyline", "") for step in best_route["steps"] if step.get("polyline")]
            result["polyline"] = ";".join(polyline_points) if polyline_points else None
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"请求异常: {str(e)}"}

def calculate_transit_route(
    start_lng: float, start_lat: float, 
    end_lng: float, end_lat: float,
    city: str = "北京"
) -> Dict[str, any]:
    """计算公共交通路线规划"""
    url = "https://restapi.amap.com/v3/direction/transit/integrated"
    params = {
        "key": AMAP_API_KEY,
        "origin": f"{start_lng},{start_lat}",
        "destination": f"{end_lng},{end_lat}",
        "city": city,
        "output": "json",
        "strategy": "0"  # 0-最快捷模式，1-最经济模式，2-最少换乘模式，3-最少步行模式
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") != "1":
            return {"success": False, "error": f"公交API请求失败: {data.get('info', '未知错误')}"}
        
        route = data.get("route")
        if not route:
            return {"success": False, "error": "公交API返回数据中缺少route字段"}
        
        # 公交路线数据结构
        transits = route.get("transits", [])
        if not transits:
            return {"success": False, "error": "未找到公交路线"}
        
        best_transit = transits[0]  # 选择第一个方案
        
        # 计算总时长和费用
        duration = int(best_transit.get("duration", 0))
        cost = float(best_transit.get("cost", 0))
        walking_distance = int(best_transit.get("walking_distance", 0))
        
        result = {
            "success": True,
            "duration": duration,
            "cost": cost,
            "walking_distance": walking_distance,
            "segments": best_transit.get("segments", []),
            "origin": f"{start_lng},{start_lat}",
            "destination": f"{end_lng},{end_lat}",
            "origin_name": "",
            "destination_name": "",
            "route_type": "transit"
        }
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"公交路线请求异常: {str(e)}"}

def decode_polyline(polyline_str: str) -> List[List[float]]:
    """解码高德地图的polyline字符串为坐标点列表"""
    if not polyline_str:
        return []
    
    points = []
    coordinate_chunks = polyline_str.split(';')
    
    for chunk in coordinate_chunks:
        if ',' in chunk:
            lng, lat = chunk.split(',')
            points.append([float(lat), float(lng)])  # Folium使用[纬度,经度]顺序
    
    return points

def create_map_html(result: Dict, route_type: str) -> str:  # 添加route_type参数
    """创建路线可视化地图并返回HTML字符串"""
    # 原函数内容保持不变，根据route_type调整地图样式
    if not result.get("success") or not result.get("polyline"):
        return "<div style='color:red; padding:20px; text-align:center;'>无法生成路线地图</div>"
    
    # 解码路线坐标
    points = decode_polyline(result["polyline"])
    if not points:
        return "<div style='color:red; padding:20px; text-align:center;'>路线坐标点为空</div>"
    
    # 计算地图中心点
    center_lat = sum(point[0] for point in points) / len(points)
    center_lng = sum(point[1] for point in points) / len(points)
    
    # 创建地图 - 设置合适的高度并添加边框
    m = folium.Map(location=[center_lat, center_lng], 
                   zoom_start=12,
                   tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
                   attr='高德地图',
                   height=400,
                   width='100%')
    
    # 添加美化样式
    m.get_root().html.add_child(folium.Element("""
        <style>
            .folium-map {
                border-radius: 15px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                border: 2px solid #e0e0e0;
            }
            .leaflet-control-container .leaflet-top.leaflet-right {
                margin-top: 10px;
                margin-right: 10px;
            }
        </style>
    """))
    
    if route_type == "driving":
        # 驾车路线处理
        if result.get("polyline"):
            points = decode_polyline(result["polyline"])
            if points:
                # 添加路线
                folium.PolyLine(
                    locations=points,
                    color='#1890FF',
                    weight=5,
                    opacity=0.8,
                    tooltip=f"🚗 驾车路线: {result['distance']/1000:.2f}公里, {result['duration']//60}分钟"
                ).add_to(m)
        
        # 添加起点标记 - 汽车图标
        folium.Marker(
            location=[start_lat, start_lng],
            popup=f"🚗 起点: {result.get('origin_name', '')}",
            icon=folium.Icon(color="green", icon="car", prefix='fa'),
            tooltip="起点"
        ).add_to(m)
        
        # 添加终点标记
        folium.Marker(
            location=[end_lat, end_lng],
            popup=f"🏁 终点: {result.get('destination_name', '')}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix='fa'),
            tooltip="终点"
        ).add_to(m)
    
    elif route_type == "transit":
        # 公交路线处理
        segments = result.get("segments", [])
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        
        for i, segment in enumerate(segments):
            color = colors[i % len(colors)]
            
            if segment.get("bus") and segment["bus"].get("buslines"):
                # 公交/地铁线路
                busline = segment["bus"]["buslines"][0]
                polyline = busline.get("polyline", "")
                if polyline:
                    points = decode_polyline(polyline)
                    if points:
                        folium.PolyLine(
                            locations=points,
                            color=color,
                            weight=4,
                            opacity=0.7,
                            tooltip=f"🚌 {busline.get('name', '公交线路')}"
                        ).add_to(m)
            
            elif segment.get("walking"):
                # 步行路段
                steps = segment["walking"].get("steps", [])
                for step in steps:
                    polyline = step.get("polyline", "")
                    if polyline:
                        points = decode_polyline(polyline)
                        if points:
                            folium.PolyLine(
                                locations=points,
                                color='#666666',
                                weight=2,
                                opacity=0.6,
                                dashArray='5, 5',
                                tooltip="🚶 步行路段"
                            ).add_to(m)
        
        # 添加起点标记 - 公交图标
        folium.Marker(
            location=[start_lat, start_lng],
            popup=f"🚌 起点: {result.get('origin_name', '')}",
            icon=folium.Icon(color="blue", icon="bus", prefix='fa'),
            tooltip="起点"
        ).add_to(m)
        
        # 添加终点标记
        folium.Marker(
            location=[end_lat, end_lng],
            popup=f"🏁 终点: {result.get('destination_name', '')}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix='fa'),
            tooltip="终点"
        ).add_to(m)
    
    # 添加小地图和全屏功能
    MiniMap(position='bottomleft').add_to(m)
    Fullscreen(position='topright').add_to(m)
    
    return m._repr_html_()
def save_map_as_image(result: Dict, route_type: str = "driving") -> str:
    """将地图保存为JPG图片并返回base64编码"""
    try:
        # 创建临时HTML文件
        map_html = create_map_html(result, route_type)
        
        # 使用Selenium截图（需要安装Chrome浏览器和ChromeDriver）
        # 注意：在实际部署时确保Chrome和ChromeDriver可用
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1200,800')
        
        # 创建临时HTML文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Route Map</title>
            </head>
            <body style="margin:0; padding:20px; background:#f5f5f5;">
                {map_html}
            </body>
            </html>
            """)
            temp_file = f.name
        
        try:
            # 注意：这部分代码需要系统安装Chrome浏览器和ChromeDriver
            # 在Gradio环境中可能无法直接使用，建议使用其他截图方案
            driver = webdriver.Chrome(options=options)
            driver.get(f"file://{temp_file}")
            time.sleep(3)  # 等待地图加载
            
            # 截图并保存
            screenshot = driver.get_screenshot_as_png()
            driver.quit()
            
            # 转换为JPG格式
            img = Image.open(io.BytesIO(screenshot))
            img_rgb = img.convert('RGB')
            
            # 保存为base64
            buffer = io.BytesIO()
            img_rgb.save(buffer, format='JPEG', quality=95)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_base64}"
            
        finally:
            # 清理临时文件
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"地图截图失败: {e}")
        # 返回一个占位图片的base64编码
        return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="


def process_route(start: str, end: str, route_type: str):
    # 地理编码获取坐标
    start_coords = geocode_location(start)
    end_coords = geocode_location(end)
    
    if not start_coords or not end_coords:
        return "地址解析失败", "", ""

    # 根据路线类型调用不同计算函数
    if route_type == "驾车":
        result = calculate_driving_route(*start_coords, *end_coords)
    elif route_type == "公交":
        result = calculate_transit_route(*start_coords, *end_coords)
    else:
        result = {"success": False, "error": "暂不支持此路线类型"}

    # 处理结果
    if result.get('success'):
        summary = f"路线距离：{result['distance']/1000:.1f}公里\n预计时间：{result['duration']//60}分钟"
        map_html = create_map_html(result, route_type.lower())
        steps = '\n'.join([step['instruction'] for step in result.get('steps',[])])
        return summary, map_html, steps
    else:
        return result.get('error', '路线规划失败'), "", ""