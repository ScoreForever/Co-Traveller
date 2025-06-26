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
import base64
import io
import os

# 高德地图API配置
AMAP_API_KEY = ""  # 将在travel.py中设置

# 在文件顶部添加全局变量
AMAP_API_KEY = None

# 添加设置 API 密钥的函数
def set_amap_api_key(api_key):
    global AMAP_API_KEY
    AMAP_API_KEY = api_key

# 0528最新修改：增加POI评分计算函数
def calculate_poi_score(poi, priority_type, poi_priorities):
    """计算POI评分"""
    score = 0
    
    # 基于类型优先级评分
    if priority_type in poi_priorities:
        score += (len(poi_priorities) - poi_priorities.index(priority_type)) * 100
    
    # 基于评分评分
    rating = poi.get("biz_ext", {}).get("rating", "")
    if rating and rating.replace(".", "").isdigit():
        score += float(rating) * 10
    
    return score

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
        
        # 处理路线坐标（polyline）- 关键修复
        if "polyline" in best_route:
            result["polyline"] = best_route["polyline"]
        elif "steps" in best_route:
            # 合并所有步骤的polyline
            polylines = []
            for step in best_route["steps"]:
                if step.get("polyline"):
                    polylines.append(step["polyline"])
            result["polyline"] = ";".join(polylines) if polylines else ""
        
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
        
        # 添加缺失的字段
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
            "route_type": "transit",
            # 添加默认距离值（公交路线通常没有总距离）
            "distance": 0,
            # 添加polyline字段（即使为空）
            "polyline": ""
        }
        
        # 合并所有路段的polyline - 关键修复
        polylines = []
        for segment in best_transit.get("segments", []):
            # 处理公交路段
            if "bus" in segment and segment["bus"].get("buslines"):
                for busline in segment["bus"]["buslines"]:
                    if busline.get("polyline"):
                        polylines.append(busline["polyline"])
            
            # 处理步行路段
            if "walking" in segment and segment["walking"].get("polyline"):
                polylines.append(segment["walking"]["polyline"])
        
        result["polyline"] = ";".join(polylines) if polylines else ""
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"公交路线请求异常: {str(e)}"}

def calculate_walking_route(
    start_lng: float, start_lat: float, 
    end_lng: float, end_lat: float
) -> Dict[str, any]:
    """计算步行路线规划"""
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
            return {"success": False, "error": f"步行路线API请求失败: {data.get('info', '未知错误')}"}
        
        route = data.get("route")
        if not route:
            return {"success": False, "error": "步行路线API返回数据中缺少route字段"}
        
        paths = route.get("paths")
        if not paths or len(paths) == 0:
            return {"success": False, "error": "未找到步行路线"}
        
        best_path = paths[0]
        
        result = {
            "success": True,
            "distance": int(best_path.get("distance", 0)),
            "duration": int(best_path.get("duration", 0)),
            "steps": best_path.get("steps", []),
            "origin": f"{start_lng},{start_lat}",
            "destination": f"{end_lng},{end_lat}",
            "origin_name": "",
            "destination_name": "",
            "polyline": best_path.get("polyline", "")
        }
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"步行路线请求异常: {str(e)}"}

def decode_polyline(polyline_str: str) -> List[List[float]]:
    """解码高德地图的polyline字符串为坐标点列表 - 关键修复"""
    if not polyline_str:
        print("空polyline字符串")
        return []
    
    points = []
    
    # 处理多段polyline（用分号分隔）
    segments = polyline_str.split(';')
    print(f"解码polyline: 分段数量={len(segments)}")
    
    for segment in segments:
        if not segment.strip():
            continue
            
        # 处理每个分段中的坐标对（用空格或逗号分隔）
        coordinate_pairs = segment.replace(',', ' ').split()
        
        # 每两个数字组成一个坐标对
        for i in range(0, len(coordinate_pairs) - 1, 2):
            try:
                lng = float(coordinate_pairs[i])
                lat = float(coordinate_pairs[i + 1])
                # Folium使用[纬度,经度]顺序
                points.append([lat, lng])
            except (ValueError, IndexError) as e:
                print(f"解析坐标对失败: {coordinate_pairs[i:i+2]}, 错误: {e}")
                continue
    
    # 如果上面的方法没有成功，尝试另一种解析方式
    if not points:
        print("尝试备用解析方法...")
        # 尝试直接按逗号分割的方式
        coords = polyline_str.replace(';', ',').split(',')
        for i in range(0, len(coords) - 1, 2):
            try:
                lng = float(coords[i].strip())
                lat = float(coords[i + 1].strip())
                points.append([lat, lng])
            except (ValueError, IndexError):
                continue
    
    print(f"解码后坐标点数量: {len(points)}")
    if points:
        print(f"第一个点: 纬度={points[0][0]:.6f}, 经度={points[0][1]:.6f}")
        print(f"最后一个点: 纬度={points[-1][0]:.6f}, 经度={points[-1][1]:.6f}")
    
    return points

def create_map_html(result: Dict, route_type: str) -> str:
    """创建路线可视化地图并返回HTML字符串 - 关键修复"""
    print(f"开始创建地图: 路线类型={route_type}, 结果成功={result.get('success')}")
    
    # 处理路线类型（兼容大小写）
    route_type = route_type.lower()
    
    # 检查结果是否有效
    if not result.get("success"):
        error_msg = result.get("error", "未知错误")
        print(f"无法生成路线地图: {error_msg}")
        return f"""
        <div style='color:red; padding:20px; text-align:center; 
                    background:#fff3f3; border:2px solid #ffcdd2; border-radius:10px;'>
            <h3>⚠️ 路线规划失败</h3>
            <p>{error_msg}</p>
        </div>
        """
    
    # 解析起点和终点坐标
    try:
        start_lng, start_lat = map(float, result["origin"].split(','))
        end_lng, end_lat = map(float, result["destination"].split(','))
        print(f"起点: 经度={start_lng}, 纬度={start_lat}")
        print(f"终点: 经度={end_lng}, 纬度={end_lat}")
    except Exception as e:
        print(f"解析起点终点坐标失败: {e}")
        return f"<div style='color:red; padding:20px; text-align:center;'>坐标解析失败: {str(e)}</div>"
    
    # 解码路线坐标
    points = []
    if "polyline" in result and result["polyline"]:
        print(f"开始解码polyline: {result['polyline'][:100]}...")
        points = decode_polyline(result["polyline"])
    
    # 如果没有路线坐标，使用起点终点连线
    if not points:
        print("使用起点终点连线作为路径")
        points = [[start_lat, start_lng], [end_lat, end_lng]]
    
    # 计算地图中心点和缩放级别
    if len(points) >= 2:
        center_lat = sum(point[0] for point in points) / len(points)
        center_lng = sum(point[1] for point in points) / len(points)
        
        # 计算坐标范围以确定合适的缩放级别
        lat_range = max(point[0] for point in points) - min(point[0] for point in points)
        lng_range = max(point[1] for point in points) - min(point[1] for point in points)
        max_range = max(lat_range, lng_range)
        
        if max_range > 1:
            zoom = 8
        elif max_range > 0.1:
            zoom = 10
        elif max_range > 0.01:
            zoom = 13
        else:
            zoom = 15
    else:
        center_lat, center_lng = start_lat, start_lng
        zoom = 13
    
    print(f"地图中心: 纬度={center_lat:.6f}, 经度={center_lng:.6f}, 缩放={zoom}")
    
    # 创建地图
    try:
        # 使用高德地图瓦片
        m = folium.Map(
            location=[center_lat, center_lng], 
            zoom_start=zoom,
            tiles=None  # 不使用默认瓦片
        )
        
        # 添加高德地图瓦片层
        folium.TileLayer(
            tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
            attr='高德地图',
            name='高德地图',
            overlay=False,
            control=True
        ).add_to(m)
        
        print("地图对象创建成功")
    except Exception as e:
        print(f"创建地图失败: {e}")
        return f"<div style='color:red; padding:20px; text-align:center;'>创建地图失败: {str(e)}</div>"
    
    # 添加路线
    try:
        # 根据路线类型设置不同颜色和样式
        if route_type == "driving" or route_type == "驾车":
            color = '#1890FF'
            tooltip = "🚗 驾车路线"
            start_icon = "car"
            start_color = "green"
        elif route_type == "transit" or route_type == "公交":
            color = '#FF6B6B'
            tooltip = "🚌 公交路线"
            start_icon = "bus"
            start_color = "blue"
        else:  # 步行
            color = '#52C41A'
            tooltip = "🚶 步行路线"
            start_icon = "male"
            start_color = "orange"
        
        # 添加路线折线
        if len(points) > 1:
            folium.PolyLine(
                locations=points,
                color=color,
                weight=5,
                opacity=0.8,
                tooltip=tooltip
            ).add_to(m)
            print(f"路线添加成功，坐标点数量: {len(points)}")
        
        # 添加起点标记
        folium.Marker(
            location=[start_lat, start_lng],
            popup=f"🏁 起点: {result.get('origin_name', '起点')}",
            icon=folium.Icon(color=start_color, icon=start_icon, prefix='fa'),
            tooltip="起点"
        ).add_to(m)
        
        # 添加终点标记
        folium.Marker(
            location=[end_lat, end_lng],
            popup=f"🎯 终点: {result.get('destination_name', '终点')}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix='fa'),
            tooltip="终点"
        ).add_to(m)
        
        print("起点终点标记添加成功")
        
        # 添加小地图和全屏功能
        MiniMap(position='bottomleft').add_to(m)
        Fullscreen(position='topright').add_to(m)
        
        # 添加样式和脚本
        m.get_root().html.add_child(folium.Element("""
        <style>
            .folium-map {
                border-radius: 15px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                border: 2px solid #e0e0e0;
                height: 500px !important;
            }
            .leaflet-control-container .leaflet-top.leaflet-right {
                margin-top: 10px;
                margin-right: 10px;
            }
        </style>
        <script>
            function resizeMap() {
                console.log("调整地图大小...");
                setTimeout(function() {
                    if (window.L && window.L.Map) {
                        Object.values(L.Map._instances).forEach(map => {
                            try {
                                map.invalidateSize();
                                console.log("地图大小调整成功");
                            } catch (e) {
                                console.error("调整地图大小失败:", e);
                            }
                        });
                    }
                }, 500);
            }
            
            document.addEventListener('DOMContentLoaded', resizeMap);
            window.addEventListener('resize', resizeMap);
            
            // 延迟执行
            setTimeout(resizeMap, 1000);
        </script>
        """))
        
        print("地图HTML生成成功")
        return m._repr_html_()
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"地图渲染错误: {e}")
        print(f"错误详情: {error_trace}")
        
        error_html = f"""
        <div style="color:red; padding:20px; text-align:center; 
                    background:#fff3f3; border:2px solid #ffcdd2; border-radius:10px;">
            <h3>⚠️ 地图渲染错误</h3>
            <p>错误信息: {str(e)}</p>
            <p>坐标点数量: {len(points)}</p>
            <details style="margin-top: 10px;">
                <summary>详细错误信息</summary>
                <pre style="text-align: left; font-size: 12px; overflow: auto; max-height: 200px;">
{error_trace}
                </pre>
            </details>
        </div>
        """
        return error_html

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
        return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="

def process_route(start: str, end: str, route_type: str):
    """处理路线规划请求并生成地图和路线信息 - 关键修复"""
    print(f"开始处理路线规划: {start} -> {end}, 类型: {route_type}")
    
    # 检查API密钥
    if not AMAP_API_KEY:
        error_msg = "高德地图API密钥未设置，请先设置API密钥"
        print(error_msg)
        return error_msg, "<div style='color:red; padding:20px;'>API密钥未设置</div>", ""
    
    # 地理编码获取坐标
    print("开始地理编码...")
    start_coords = geocode_location(start)
    end_coords = geocode_location(end)

    if not start_coords or not end_coords:
        error_msg = f"地址解析失败: 起点={start_coords}, 终点={end_coords}"
        print(error_msg)
        return error_msg, "<div style='color:red; padding:20px;'>地址解析失败</div>", ""

    print(f"地理编码成功: 起点={start_coords}, 终点={end_coords}")

    # 根据路线类型调用不同计算函数
    try:
        if route_type in ["驾车", "driving"]:
            print("计算驾车路线...")
            result = calculate_driving_route(*start_coords, *end_coords)
            result["origin_name"] = start
            result["destination_name"] = end
        elif route_type in ["公交", "transit"]:
            print("计算公交路线...")
            # 提取城市信息用于公交查询
            city = start.split()[0] if ' ' in start else "北京"  # 简单提取城市
            result = calculate_transit_route(*start_coords, *end_coords, city)
            result["origin_name"] = start
            result["destination_name"] = end
        elif route_type in ["步行", "walking"]:
            print("计算步行路线...")
            result = calculate_walking_route(*start_coords, *end_coords)
            result["origin_name"] = start
            result["destination_name"] = end
        else:
            error_msg = f"暂不支持路线类型: {route_type}"
            print(error_msg)
            return error_msg, "<div style='color:red; padding:20px;'>暂不支持此路线类型</div>", ""
    except Exception as e:
        error_msg = f"路线计算异常: {str(e)}"
        print(error_msg)
        return error_msg, "<div style='color:red; padding:20px;'>路线计算失败</div>", ""

    print(f"路线计算结果: success={result.get('success')}")

    if result.get('success'):
        # 确保必要字段存在
        result.setdefault('distance', 0)
        result.setdefault('duration', 0)
        if route_type in ["公交", "transit"]:
            result.setdefault('walking_distance', 0)
            result.setdefault('cost', 0)

        # 生成摘要信息
        try:
            if route_type in ["驾车", "driving"]:
                distance_km = result['distance'] / 1000
                duration_min = result['duration'] // 60
                summary = f"🚗 驾车路线：{distance_km:.1f}公里，预计{duration_min}分钟"
            elif route_type in ["公交", "transit"]:
                walking_m = result.get('walking_distance', 0)
                duration_min = result['duration'] // 60
                cost = result.get('cost', 0)
                summary = f"🚌 公交路线：步行{walking_m}米，总耗时{duration_min}分钟"
                if cost > 0:
                    summary += f"，费用约{cost}元"
            elif route_type in ["步行", "walking"]:
                distance_m = result['distance']
                duration_min = result['duration'] // 60
                summary = f"🚶 步行路线：{distance_m}米，预计{duration_min}分钟"
            else:
                summary = "路线信息"
        except Exception as e:
            print(f"生成摘要失败: {e}")
            summary = "路线规划完成，但摘要生成失败"

        print("开始生成地图...")
        # 生成地图HTML
        try:
            map_html = create_map_html(result, route_type)
            print("地图生成成功")
        except Exception as e:
            print(f"地图生成失败: {e}")
            map_html = f"<div style='color:red; padding:20px;'>地图生成失败: {str(e)}</div>"

        # 生成详细步骤
        steps = []
        try:
            if route_type in ["驾车", "driving"] and "steps" in result:
                for i, step in enumerate(result["steps"]):
                    instruction = step.get("instruction", "")
                    if instruction:
                        steps.append(f"{i+1}. {instruction}")
            
            elif route_type in ["公交", "transit"] and "segments" in result:
                step_num = 1
                for segment in result["segments"]:
                    # 步行路段
                    if "walking" in segment:
                        walking = segment["walking"]
                        for walk_step in walking.get("steps", []):
                            instruction = walk_step.get("instruction")
                            if instruction:
                                steps.append(f"{step_num}. 🚶 {instruction}")
                                step_num += 1
                    
                    # 公交路段
                    if "bus" in segment and segment["bus"].get("buslines"):
                        for busline in segment["bus"]["buslines"]:
                            bus_name = busline.get('name', '公交线路')
                            departure = busline.get('departure_stop', {}).get('name', '起点站')
                            arrival = busline.get('arrival_stop', {}).get('name', '终点站')
                            steps.append(f"{step_num}. 🚌 乘坐{bus_name} ({departure} → {arrival})")
                            step_num += 1
            
            elif route_type in ["步行", "walking"] and "steps" in result:
                for i, step in enumerate(result["steps"]):
                    instruction = step.get("instruction", "")
                    if instruction:
                        steps.append(f"{i+1}. {instruction}")
                        
        except Exception as e:
            print(f"生成步骤时出错: {e}")
            steps.append("无法生成详细步骤")

        steps_text = '\n'.join(steps) if steps else "暂无详细路线指引"
        
        print("路线规划处理完成")
        return summary, map_html, steps_text
    else:
        error_msg = result.get('error', '路线规划失败')
        print(f"路线规划失败: {error_msg}")
        return error_msg, f"<div style='color:red; padding:20px;'>{error_msg}</div>", ""