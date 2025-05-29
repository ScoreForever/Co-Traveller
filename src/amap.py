import requests
import re
from PIL import Image
import io
import json
import time

# 高德地图API配置
AMAP_API_KEY = ""  # 将在travel.py中设置

def set_amap_api_key(api_key):
    """设置高德地图API密钥"""
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

# 0528最新修改：新增POI评分计算函数
def calculate_poi_score(poi, priority_type, poi_priorities):
    """计算POI的综合评分"""
    base_score = len(poi_priorities) - poi_priorities.index(priority_type)
    
    # 加入评分权重
    rating = poi.get("biz_ext", {}).get("rating", "0")
    if rating and rating != "0":
        try:
            rating_score = float(rating) * 10
            base_score += rating_score
        except:
            pass
    
    # 加入名称匹配度权重
    name = poi.get("name", "")
    keywords = ["景区", "公园", "博物馆", "寺", "庙", "山", "湖", "古", "文化", "历史"]
    for keyword in keywords:
        if keyword in name:
            base_score += 5
    
    return base_score

def extract_addresses_from_text(text):
    """从文本中提取地址信息"""
    if not text.strip():
        return []

    # 0528最新修改：优化文本清理逻辑
    cleaned_text = re.sub(r'[，。！？；：、\s]+', ' ', text)
    
    # 0528最新修改：扩展分隔符识别
    separators = [
        '从', '到', '去', '经过', '途径', '然后', '接着', '再到', '最后到',
        '出发', '前往', '抵达', '到达', '游览', '参观', '访问', '路过',
        '->', '-->', '→', '——', '先去', '后去', '再去'
    ]
    pattern = '|'.join([f'({re.escape(sep)})' for sep in separators])
    segments = re.split(pattern, cleaned_text)

    potential_locations = []
    # 0528最新修改：扩展非地点词汇过滤
    non_location_words = [
        '我', '要', '想', '打算', '计划', '准备', '开始', '结束', '时间', '小时',
        '分钟', '天', '晚上', '早上', '下午', '中午', '今天', '明天', '昨天'
    ]

    for segment in segments:
        if not segment or segment in separators:
            continue
        words = segment.split()
        filtered_words = [word for word in words if word not in non_location_words and len(word) > 1]
        if filtered_words:
            potential_locations.extend(filtered_words)

    # 0528最新修改：增强地址模式识别
    if not potential_locations:
        location_patterns = [
            r'[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|村|街道|路|街|巷|号|大厦|广场|公园|景区|寺|庙|山|湖|河|桥|站|机场|港|码头)',
            r'[\u4e00-\u9fa5]{2,}(?:博物館|博物馆|纪念馆|展览馆|美术馆|图书馆|体育馆|剧院|影院|音乐厅)',
            r'[\u4e00-\u9fa5]{2,}(?:大学|学院|医院|银行|酒店|宾馆|商场|超市|餐厅|咖啡厅)',
            r'[\u4e00-\u9fa5]{3,8}(?:风景区|旅游区|度假村|古镇|古城|老街|步行街)',
            r'[\u4e00-\u9fa5]{2,}(?:塔|楼|阁|亭|台|殿|宫|府|院|园)',  # 0528最新修改：新增建筑类型
        ]
        for pattern in location_patterns:
            matches = re.findall(pattern, text)
            potential_locations.extend(matches)
        
        if not potential_locations:
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,8}', text)
            potential_locations.extend(chinese_words)

    # 0528最新修改：去重并优化地址验证
    unique_locations = []
    seen = set()
    for loc in potential_locations:
        loc = loc.strip()
        if len(loc) >= 2 and loc not in seen and not is_common_word(loc):
            seen.add(loc)
            unique_locations.append(loc)

    verified_addresses = []
    for location in unique_locations:
        poi_result = search_poi(location)
        if poi_result:
            verified_addresses.append(poi_result)
            print(f"成功解析: {location} -> {poi_result['address']}")
        else:
            # 0528最新修改：改进地址保留逻辑
            if any(keyword in location for keyword in ['市', '区', '县', '路', '街', '景区', '公园', '山', '湖', '寺', '庙']):
                fallback_result = {
                    'address': location,
                    'name': location,
                    'type': '地名地址',
                    'location': '',
                    'tel': '',
                    'rating': '',
                    'cost': ''
                }
                verified_addresses.append(fallback_result)
                print(f"保留可能地址: {location}")
            else:
                print(f"无法解析: {location}")

    return verified_addresses

# 0528最新修改：新增常用词过滤函数
def is_common_word(word):
    """检查是否为常用非地名词汇"""
    common_words = [
        '一下', '一起', '什么', '怎么', '这里', '那里', '地方', '时候',
        '可以', '应该', '需要', '必须', '比较', '非常', '特别', '还是'
    ]
    return word in common_words

def geocode_address(address_info):
    """使用高德地图API将地址转换为经纬度"""
    # 0528最新修改：支持新的地址信息格式
    if isinstance(address_info, dict):
        address = address_info['address']
        # 如果已有经纬度信息，直接使用
        if address_info.get('location'):
            try:
                lng, lat = address_info['location'].split(',')
                return float(lng), float(lat), address, address_info
            except:
                pass
    else:
        address = address_info
        address_info = {
            'address': address,
            'name': address,
            'type': '',
            'location': '',
            'tel': '',
            'rating': '',
            'cost': ''
        }
    
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
            formatted_address = data["geocodes"][0]["formatted_address"]
            return float(lng), float(lat), formatted_address, address_info
        else:
            print(f"地理编码失败，地址: {address}, 错误信息: {data.get('info', '未知错误')}")
            return None, None, f"无法解析地址: {address}", address_info
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None, None, f"网络请求错误: {str(e)}", address_info
    except Exception as e:
        print(f"地址解析错误: {e}")
        return None, None, f"地址解析错误: {str(e)}", address_info

def calculate_route(start_lng, start_lat, end_lng, end_lat, transport_mode="driving"):
    """使用高德地图API计算路线，支持不同交通方式"""
    # 0528最新修改：优化路线计算API调用
    if transport_mode == "driving":
        url = "https://restapi.amap.com/v3/direction/driving"
    elif transport_mode == "transit":
        url = "https://restapi.amap.com/v3/direction/transit/integrated"
    elif transport_mode == "walking":
        url = "https://restapi.amap.com/v3/direction/walking"
    elif transport_mode == "bicycling":
        url = "https://restapi.amap.com/v4/direction/bicycling"
    else:
        return {"success": False, "error": f"不支持的交通方式: {transport_mode}"}
    
    params = {
        "key": AMAP_API_KEY,
        "origin": f"{start_lng},{start_lat}",
        "destination": f"{end_lng},{end_lat}",
        "output": "json",
        "extensions": "all"
    }
    
    # 0528最新修改：改进公交路线城市推断
    if transport_mode == "transit":
        city = infer_city_from_coordinates(start_lng, start_lat)
        params["city"] = city or "北京"
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data["status"] == "1" and "route" in data:
            if transport_mode == "driving":
                path = data["route"]["paths"][0]
                polyline = path["steps"][0]["polyline"] if path["steps"] else ""
                distance = path["distance"]
                duration = path["duration"]
                # 0528最新修改：添加详细路线信息
                tolls = path.get("tolls", "0")
                traffic_lights = path.get("traffic_lights", "0")
            elif transport_mode == "transit":
                path = data["route"]["transits"][0]
                polyline = extract_transit_polyline(path)  # 0528最新修改：提取公交路线
                distance = path["distance"]
                duration = path["duration"]
                tolls = "0"
                traffic_lights = "0"
            elif transport_mode == "walking":
                path = data["route"]["paths"][0]
                polyline = path["steps"][0]["polyline"] if path["steps"] else ""
                distance = path["distance"]
                duration = path["duration"]
                tolls = "0"
                traffic_lights = "0"
            elif transport_mode == "bicycling":
                path = data["data"]["paths"][0]
                polyline = path["polyline"]
                distance = path["distance"]
                duration = path["duration"]
                tolls = "0"
                traffic_lights = "0"
            
            return {
                "polyline": polyline,
                "distance": distance,
                "duration": duration,
                "tolls": tolls,  # 0528最新修改：添加收费信息
                "traffic_lights": traffic_lights,  # 0528最新修改：添加红绿灯信息
                "success": True,
                "transport_mode": transport_mode
            }
        else:
            print(f"路线规划失败，起点: {start_lng},{start_lat}, 终点: {end_lng},{end_lat}, 错误信息: {data.get('info', '未知错误')}")
            return {"success": False, "error": "路线规划失败"}
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return {"success": False, "error": f"网络请求错误: {str(e)}"}
    except Exception as e:
        print(f"路线规划错误: {e}")
        return {"success": False, "error": f"路线规划错误: {str(e)}"}

# 0528最新修改：新增城市推断函数
def infer_city_from_coordinates(lng, lat):
    """根据经纬度推断城市"""
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": AMAP_API_KEY,
        "location": f"{lng},{lat}",
        "output": "json"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data["status"] == "1":
            city = data["regeocode"]["addressComponent"]["city"]
            return city.replace("市", "") if city else "北京"
    except:
        pass
    return "北京"

# 0528最新修改：新增公交路线提取函数
def extract_transit_polyline(transit_path):
    """从公交路线中提取折线数据"""
    polylines = []
    for segment in transit_path.get("segments", []):
        if "walking" in segment:
            polylines.append(segment["walking"]["polyline"])
        if "bus" in segment:
            for busline in segment["bus"]["segments"]:
                if "polyline" in busline:
                    polylines.append(busline["polyline"])
    return ";".join(polylines)

def generate_map_html(locations, routes=None):
    """生成包含标注点、路线和交互式弹窗的高德地图HTML"""
    if not locations:
        return "未找到有效地址"

    # 0528最新修改：改进中心点计算
    valid_locations = [loc for loc in locations if loc[0] and loc[1]]
    if not valid_locations:
        return "没有有效的地理坐标"
    
    center_lng = sum([loc[0] for loc in valid_locations]) / len(valid_locations)
    center_lat = sum([loc[1] for loc in valid_locations]) / len(valid_locations)

    html_content = f"""
    <div id="mapContainer" style="width: 100%; height: 400px;"></div>
    <script src="https://webapi.amap.com/maps?v=1.4.15&key={AMAP_API_KEY}"></script>
    <script>
        var map = new AMap.Map('mapContainer', {{
            center: [{center_lng}, {center_lat}],
            zoom: 10
        }});
    """

    # 0528最新修改：优化标记点显示
    for i, (lng, lat, addr, info) in enumerate(locations):
        if lng and lat:
            html_content += f"""
            var marker{i} = new AMap.Marker({{
                position: [{lng}, {lat}],
                map: map,
                title: '{addr}'
            }});
            var infoWindow{i} = new AMap.InfoWindow({{
                content: '<div style="padding: 15px; max-width: 300px;">' +
                         '<h3 style="margin: 0 0 10px 0; color: #333;">{info.get("name", addr)}</h3>' +
                         '<p style="margin: 5px 0;"><strong>地址:</strong> {addr}</p>' +
                         '<p style="margin: 5px 0;"><strong>类型:</strong> {info.get("type", "未知")}</p>' +
                         {f"'<p style=\"margin:5px 0;\"><strong>电话:</strong> {info.get('tel', '暂无')}</p>' +" if info.get('tel') else ""}
                         {f"'<p style=\"margin:5px 0;\"><strong>评分:</strong> ⭐{info.get('rating', '无')}</p>' +" if info.get('rating') else ""}
                         {f"'<p style=\"margin:5px 0;\"><strong>人均消费:</strong> ¥{info.get('cost', '无')}</p>' +" if info.get('cost') else ""}
                         '</div>',
                offset: new AMap.Pixel(0, -30)
            }});
            marker{i}.on('click', function() {{
                infoWindow{i}.open(map, marker{i}.getPosition());
            }});
            """

    # 0528最新修改：优化路线显示和交互
    if routes:
        for i, route in enumerate(routes):
            if route.get("success") and route.get("polyline"):
                points = route["polyline"].split(';')
                if len(points) > 1:
                    try:
                        path = [[float(p.split(',')[0]), float(p.split(',')[1])] for p in points if ',' in p]
                        if path:
                            # 根据交通方式设置颜色
                            colors = {
                                "driving": "#3366FF",
                                "transit": "#FF6600", 
                                "walking": "#66CC66",
                                "bicycling": "#CC66CC"
                            }
                            color = colors.get(route["transport_mode"], "#3366FF")
                            
                            html_content += f"""
                            var polyline{i} = new AMap.Polyline({{
                                path: {path},
                                strokeColor: "{color}",
                                strokeWeight: 6,
                                strokeOpacity: 0.8,
                                lineJoin: 'round',
                                lineCap: 'round',
                                zIndex: 50,
                                map: map
                            }});
                            var routeInfoWindow{i} = new AMap.InfoWindow({{
                                content: '<div style="padding: 15px; max-width: 250px;">' +
                                         '<h4 style="margin: 0 0 10px 0; color: #333;">路线 {i + 1}</h4>' +
                                         '<p style="margin: 5px 0;"><strong>交通方式:</strong> {route["transport_mode"]}</p>' +
                                         '<p style="margin: 5px 0;"><strong>距离:</strong> {float(route["distance"])/1000:.2f} 公里</p>' +
                                         '<p style="margin: 5px 0;"><strong>预计时间:</strong> {int(route["duration"])/60:.0f} 分钟</p>' +
                                         {f"'<p style=\"margin: 5px 0;\"><strong>过路费:</strong> {route.get('tolls', '0')} 元</p>' +" if route.get('tolls') and route.get('tolls') != '0' else ""} 
                                         {f"'<p style=\"margin: 5px 0;\"><strong>红绿灯:</strong> {route.get('traffic_lights', '0')} 个</p>' +" if route.get('traffic_lights') and route.get('traffic_lights') != '0' else ""}
                                         '</div>',
                                offset: new AMap.Pixel(0, -30)
                            }});
                            polyline{i}.on('click', function(e) {{
                                routeInfoWindow{i}.open(map, e.lnglat);
                            }});
                            """
                    except Exception as e:
                        print(f"路线 {i} 绘制失败: {e}")

    html_content += """
        // 0528最新修改：添加地图控件
        map.addControl(new AMap.ToolBar());
        map.addControl(new AMap.Scale());
        
        // 自动调整视野
        setTimeout(function() {
            map.setFitView();
        }, 500);
    </script>
    """
    return html_content

def generate_route_map(locations, routes, transport_mode, show_details, optimize_route):
    """生成美化后的路线地图，包含自定义标记和路线"""
    if not locations:
        return "未找到有效地址"
    
    # 0528最新修改：改进中心点和缩放级别计算
    valid_locations = [(lng, lat, addr, info) for lng, lat, addr, info in locations if lng and lat]
    if not valid_locations:
        return "没有有效的地理坐标"
    
    center_lng = sum([loc[0] for loc in valid_locations]) / len(valid_locations)
    center_lat = sum([loc[1] for loc in valid_locations]) / len(valid_locations)
    
    # 计算合适的缩放级别
    if len(valid_locations) == 1:
        zoom_level = 15
    else:
        # 根据地点间距离计算缩放级别
        max_distance = calculate_max_distance(valid_locations)
        zoom_level = calculate_zoom_level(max_distance)
    
    # 0528最新修改：扩展交通方式图标
    transport_icons = {
        "driving": "🚗",
        "transit": "🚌", 
        "walking": "🚶",
        "bicycling": "🚲"
    }
    
    # 0528最新修改：扩展景点类型图标映射
    attraction_icons = {
        "公园": "🌳", "博物馆": "🏛️", "寺庙": "🛕", "广场": "🟩", "山峰": "⛰️",
        "湖泊": "💧", "古迹": "🏯", "建筑": "🏢", "酒店": "🏨", "餐厅": "🍴",
        "商场": "🏬", "车站": "🚉", "机场": "✈️", "医院": "🏥", "学校": "🏫",
        "银行": "🏦", "教堂": "⛪", "塔": "🗼", "桥": "🌉", "海滩": "🏖️"
    }
    
    # 0528最新修改：使用更现代的地图样式和增强的UI组件
    html_content = f"""
    <div style="position: relative;">
        <div id="mapContainer" style="width: 100%; height: 600px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"></div>
        <div id="routeInfo" style="position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.9); padding: 10px; border-radius: 5px; font-size: 14px; max-width: 200px;"></div>
    </div>
    <script src="https://webapi.amap.com/maps?v=1.4.15&key={AMAP_API_KEY}"></script>
    <script src="https://webapi.amap.com/ui/1.1/main.js"></script>
    <script>
        var map = new AMap.Map('mapContainer', {{
            center: [{center_lng}, {center_lat}],
            zoom: {zoom_level}
        }});
        
        // 0528最新修改：使用更美观的地图样式
        map.setMapStyle('amap://styles/fresh');
        
        // 0528最新修改：改进标记样式配置
        var markerOptions = {{
            anchor: 'bottom-center',
            autoRotation: true,
            animation: 'AMAP_ANIMATION_DROP'
        }};
        
        var markers = [];
        var infoWindows = [];
    """
    
    # 0528最新修改：优化景点标记显示，使用更丰富的图标和信息
    for i, (lng, lat, addr, info) in enumerate(valid_locations):
        # 根据景点类型选择图标
        icon = "📍"
        poi_type = info.get('type', '')
        for category, emoji in attraction_icons.items():
            if category in poi_type or category in addr:
                icon = emoji
                break
        
        # 0528最新修改：创建更精美的标记点
        html_content += f"""
        var marker{i} = new AMap.Marker({{
            position: [{lng}, {lat}],
            map: map,
            content: '<div style="font-size: 24px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); cursor: pointer;" title="{addr}">{icon}</div>',
            offset: new AMap.Pixel(-12, -24)
        }});
        
        // 0528最新修改：创建更详细的信息窗口
        var infoWindow{i} = new AMap.InfoWindow({{
            content: '<div style="padding: 15px; max-width: 320px; font-family: Arial, sans-serif;">' +
                     '<div style="border-bottom: 2px solid #3366FF; padding-bottom: 8px; margin-bottom: 10px;">' +
                     '<h3 style="margin: 0; color: #333; font-size: 18px;">{icon} {info.get("name", addr)}</h3>' +
                     '</div>' +
                     '<div style="margin-bottom: 8px;"><strong style="color: #666;">📍 地址:</strong> <span style="color: #333;">{addr}</span></div>' +
                     '<div style="margin-bottom: 8px;"><strong style="color: #666;">🏷️ 类型:</strong> <span style="color: #333;">{info.get("type", "未知")}</span></div>' +
                     {f"'<div style=\"margin-bottom: 8px;\"><strong style=\"color: #666;\">📞 电话:</strong> <span style=\"color: #333;\">{info.get('tel', '暂无')}</span></div>' +" if info.get('tel') else ""} 
                     {f"'<div style=\"margin-bottom: 8px;\"><strong style=\"color: #666;\">⭐ 评分:</strong> <span style=\"color: #FF6600;\">{info.get('rating', '暂无')}</span></div>' +" if info.get('rating') else ""}
                     {f"'<div style=\"margin-bottom: 8px;\"><strong style=\"color: #666;\">💰 人均:</strong> <span style=\"color: #333;\">{info.get('cost', '暂无')}</span></div>' +" if info.get('cost') else ""}
                     '<div style="text-align: center; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">' +
                     '<span style="background: #3366FF; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">景点 #{i+1}</span>' +
                     '</div>' +
                     '</div>',
            offset: new AMap.Pixel(0, -30)
        }});
        
        marker{i}.on('click', function() {{
            // 关闭其他信息窗口
            infoWindows.forEach(function(window) {{
                window.close();
            }});
            infoWindow{i}.open(map, marker{i}.getPosition());
        }});
        
        markers.push(marker{i});
        infoWindows.push(infoWindow{i});
        """

    # 0528最新修改：优化路线显示，增加动画效果和更详细的交互
    if routes and show_details:
        html_content += """
        var polylines = [];
        var routeInfoWindows = [];
        """
        
        for i, route in enumerate(routes):
            if route.get("success") and route.get("polyline"):
                points = route["polyline"].split(';')
                if len(points) > 1:
                    try:
                        path = [[float(p.split(',')[0]), float(p.split(',')[1])] for p in points if ',' in p]
                        if path:
                            # 0528最新修改：根据交通方式设置不同的路线样式
                            transport_styles = {
                                "driving": {"color": "#3366FF", "weight": 6, "opacity": 0.8, "icon": "🚗"},
                                "transit": {"color": "#FF6600", "weight": 5, "opacity": 0.8, "icon": "🚌"},
                                "walking": {"color": "#66CC66", "weight": 4, "opacity": 0.8, "icon": "🚶"},
                                "bicycling": {"color": "#CC66CC", "weight": 5, "opacity": 0.8, "icon": "🚲"}
                            }
                            
                            style = transport_styles.get(route["transport_mode"], transport_styles["driving"])
                            
                            html_content += f"""
                            var polyline{i} = new AMap.Polyline({{
                                path: {path},
                                strokeColor: "{style['color']}",
                                strokeWeight: {style['weight']},
                                strokeOpacity: {style['opacity']},
                                lineJoin: 'round',
                                lineCap: 'round',
                                zIndex: 50,
                                map: map,
                                cursor: 'pointer'
                            }});
                            
                            // 0528最新修改：创建更详细的路线信息窗口
                            var routeInfoWindow{i} = new AMap.InfoWindow({{
                                content: '<div style="padding: 15px; max-width: 280px; font-family: Arial, sans-serif;">' +
                                         '<div style="border-bottom: 2px solid {style['color']}; padding-bottom: 8px; margin-bottom: 10px;">' +
                                         '<h3 style="margin: 0; color: #333; font-size: 16px;">{style['icon']} 路线 {i+1}</h3>' +
                                         '</div>' +
                                         '<div style="margin-bottom: 8px;"><strong style="color: #666;">🚀 交通方式:</strong> <span style="color: #333;">{get_transport_name(route["transport_mode"])}</span></div>' +
                                         '<div style="margin-bottom: 8px;"><strong style="color: #666;">📏 距离:</strong> <span style="color: #333; font-weight: bold;">{float(route["distance"])/1000:.2f} 公里</span></div>' +
                                         '<div style="margin-bottom: 8px;"><strong style="color: #666;">⏱️ 预计时间:</strong> <span style="color: #333; font-weight: bold;">{format_duration(int(route["duration"]))}</span></div>' +
                                         {f"'<div style=\"margin-bottom: 8px;\"><strong style=\"color: #666;\">💰 过路费:</strong> <span style=\"color: #FF6600; font-weight: bold;\">{route.get('tolls', '0')} 元</span></div>' +" if route.get('tolls') and route.get('tolls') != '0' else ""} 
                                         {f"'<div style=\"margin-bottom: 8px;\"><strong style=\"color: #666;\">🚦 红绿灯:</strong> <span style=\"color: #333;\">{route.get('traffic_lights', '0')} 个</span></div>' +" if route.get('traffic_lights') and route.get('traffic_lights') != '0' else ""}
                                         '<div style="text-align: center; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">' +
                                         '<span style="font-size: 12px; color: #999;">点击路线查看详情</span>' +
                                         '</div>' +
                                         '</div>',
                                offset: new AMap.Pixel(0, -30)
                            }});
                            
                            polyline{i}.on('click', function(e) {{
                                // 关闭其他路线信息窗口
                                routeInfoWindows.forEach(function(window) {{
                                    window.close();
                                }});
                                routeInfoWindow{i}.open(map, e.lnglat);
                            }});
                            
                            // 0528最新修改：添加路线悬停效果
                            polyline{i}.on('mouseover', function() {{
                                polyline{i}.setOptions({{
                                    strokeWeight: {style['weight'] + 2},
                                    strokeOpacity: 1.0
                                }});
                            }});
                            
                            polyline{i}.on('mouseout', function() {{
                                polyline{i}.setOptions({{
                                    strokeWeight: {style['weight']},
                                    strokeOpacity: {style['opacity']}
                                }});
                            }});
                            
                            polylines.push(polyline{i});
                            routeInfoWindows.push(routeInfoWindow{i});
                            """
                    except Exception as e:
                        print(f"路线 {i} 绘制失败: {e}")

    # 0528最新修改：添加更多地图控件和功能
    html_content += f"""
        // 添加地图控件
        map.addControl(new AMap.ToolBar({{
            position: 'LT'
        }}));
        map.addControl(new AMap.Scale({{
            position: 'LB'
        }}));
        
        // 0528最新修改：添加路线总览信息
        function updateRouteInfo() {{
            var totalDistance = 0;
            var totalDuration = 0;
            var routeCount = 0;
            
            {generate_route_summary_js(routes) if routes else ""}
            
            if (routeCount > 0) {{
                document.getElementById('routeInfo').innerHTML = 
                    '<div style="font-weight: bold; margin-bottom: 5px; color: #333;">🗺️ 路线总览</div>' +
                    '<div style="font-size: 12px; color: #666;">📍 {len(valid_locations)} 个景点</div>' +
                    '<div style="font-size: 12px; color: #666;">🛣️ ' + routeCount + ' 段路线</div>' +
                    '<div style="font-size: 12px; color: #666;">📏 总距离: ' + (totalDistance/1000).toFixed(2) + ' 公里</div>' +
                    '<div style="font-size: 12px; color: #666;">⏱️ 总时间: ' + Math.round(totalDuration/60) + ' 分钟</div>';
            }}
        }}
        
        // 0528最新修改：自动调整地图视野，包含所有标记点和路线
        function fitMapView() {{
            var bounds = new AMap.Bounds();
            markers.forEach(function(marker) {{
                bounds.extend(marker.getPosition());
            }});
            
            if (markers.length > 1) {{
                map.setBounds(bounds, false, [20, 20, 20, 20]);
            }} else if (markers.length === 1) {{
                map.setCenter(markers[0].getPosition());
                map.setZoom(15);
            }}
        }}
        
        // 0528最新修改：添加地图点击事件，关闭所有信息窗口
        map.on('click', function() {{
            infoWindows.forEach(function(window) {{
                window.close();
            }});
            routeInfoWindows.forEach(function(window) {{
                window.close();
            }});
        }});
        
        // 初始化
        setTimeout(function() {{
            fitMapView();
            updateRouteInfo();
        }}, 500);
        
        // 0528最新修改：添加辅助函数
        function getTransportName(mode) {{
            var names = {{
                'driving': '自驾',
                'transit': '公交',
                'walking': '步行',
                'bicycling': '骑行'
            }};
            return names[mode] || mode;
        }}
        
        function formatDuration(seconds) {{
            var hours = Math.floor(seconds / 3600);
            var minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {{
                return hours + '小时' + minutes + '分钟';
            }} else {{
                return minutes + '分钟';
            }}
        }}
    </script>
    """
    
    return html_content

# 0528最新修改：新增距离计算函数
def calculate_max_distance(locations):
    """计算地点间的最大距离（用于确定缩放级别）"""
    max_dist = 0
    for i in range(len(locations)):
        for j in range(i + 1, len(locations)):
            lng1, lat1 = locations[i][0], locations[i][1]
            lng2, lat2 = locations[j][0], locations[j][1]
            dist = ((lng2 - lng1) ** 2 + (lat2 - lat1) ** 2) ** 0.5
            max_dist = max(max_dist, dist)
    return max_dist

# 0528最新修改：新增缩放级别计算函数
def calculate_zoom_level(max_distance):
    """根据最大距离计算合适的缩放级别"""
    if max_distance > 5:
        return 6
    elif max_distance > 2:
        return 8
    elif max_distance > 1:
        return 10
    elif max_distance > 0.5:
        return 11
    elif max_distance > 0.1:
        return 13
    else:
        return 15

# 0528最新修改：新增路线摘要JS生成函数
def generate_route_summary_js(routes):
    """生成路线摘要的JavaScript代码"""
    if not routes:
        return ""
    
    js_code = ""
    for i, route in enumerate(routes):
        if route.get("success"):
            js_code += f"""
            totalDistance += {route.get('distance', 0)};
            totalDuration += {route.get('duration', 0)};
            routeCount++;
            """
    return js_code

# 0528最新修改：新增交通方式名称获取函数
def get_transport_name(transport_mode):
    """获取交通方式的中文名称"""
    names = {
        "driving": "自驾",
        "transit": "公交",
        "walking": "步行",
        "bicycling": "骑行"
    }
    return names.get(transport_mode, transport_mode)

# 0528最新修改：新增时间格式化函数
def format_duration(seconds):
    """格式化时间显示"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"



# 0528最新修改：新增批量地理编码函数
def batch_geocode_addresses(address_list, max_concurrent=5):
    """批量地理编码，提高处理效率"""
    results = []
    for i in range(0, len(address_list), max_concurrent):
        batch = address_list[i:i + max_concurrent]
        batch_results = []
        
        for addr_info in batch:
            result = geocode_address(addr_info)
            batch_results.append(result)
            time.sleep(0.1)  # 避免API调用频率过高
        
        results.extend(batch_results)
    
    return results

# 0528最新修改：新增路线优化函数
def optimize_route_order(locations, start_index=0):
    """优化路线顺序，减少总距离（简单的贪心算法）"""
    if len(locations) <= 2:
        return locations
    
    optimized = [locations[start_index]]
    remaining = locations[:start_index] + locations[start_index+1:]
    
    while remaining:
        current = optimized[-1]
        nearest_idx = 0
        min_distance = float('inf')
        
        for i, location in enumerate(remaining):
            # 计算欧几里得距离（简化）
            dist = ((current[0] - location[0]) ** 2 + (current[1] - location[1]) ** 2) ** 0.5
            if dist < min_distance:
                min_distance = dist
                nearest_idx = i
        
        optimized.append(remaining.pop(nearest_idx))
    
    return optimized

# 0528最新修改：新增地图导出功能
def export_map_data(locations, routes, format="json"):
    """导出地图数据为不同格式"""
    data = {
        "locations": [
            {
                "lng": lng,
                "lat": lat,
                "address": addr,
                "info": info
            } for lng, lat, addr, info in locations
        ],
        "routes": routes,
        "summary": {
            "total_locations": len(locations),
            "total_routes": len([r for r in routes if r.get("success")]),
            "total_distance": sum([float(r.get("distance", 0)) for r in routes if r.get("success")]),
            "total_duration": sum([int(r.get("duration", 0)) for r in routes if r.get("success")])
        }
    }
    
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    elif format == "csv":
        # 生成CSV格式的景点列表
        csv_data = "序号,名称,地址,类型,经度,纬度,电话,评分\n"
        for i, (lng, lat, addr, info) in enumerate(locations, 1):
            csv_data += f"{i},{info.get('name', addr)},{addr},{info.get('type', '')},{lng},{lat},{info.get('tel', '')},{info.get('rating', '')}\n"
        return csv_data
    else:
        return str(data)