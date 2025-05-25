import requests
import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# 高德地图API Key（⚠️ 请确保使用您自己的有效API Key）
API_KEY = '27c0337b84e44bb373bb2724a6ea157d'
GEO_URL = 'https://restapi.amap.com/v3/geocode/geo'  # 地理编码API地址
ROUTE_URL = 'https://restapi.amap.com/v3/direction/driving'  # 路径规划API地址

def extract_addresses_from_text(text):
    """
    从输入文本中提取地址信息
    使用正则表达式匹配常见的中文地址格式
    """
    # 定义地址匹配的正则表达式模式
    patterns = [
        # 完整地址格式：省市区街道详细地址
        r'[^，。！？\s]{2,6}[省市][^，。！？\s]{2,6}[市区县][^，。！？\s]{2,15}[路街道巷弄][^，。！？\s]{0,20}号?',
        # 简化地址格式：城市+地标
        r'[^，。！？\s]{2,6}[市区县][^，。！？\s]{2,15}[路街道巷弄站场]',
        # 景点、地标名称
        r'[^，。！？\s]{2,10}[景区公园博物馆寺庙塔楼广场中心站]',
        # 学校、医院等机构
        r'[^，。！？\s]{2,10}[大学学院医院银行酒店宾馆]'
    ]
    
    addresses = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        addresses.extend(matches)
    
    # 去重并过滤过短的匹配结果
    unique_addresses = list(set([addr for addr in addresses if len(addr) >= 3]))
    
    return unique_addresses

def get_coordinates(address):
    """
    通过高德地图地理编码API将地址转换为经纬度坐标
    返回格式：[经度, 纬度] 或 None（如果失败）
    """
    params = {
        'address': address,  # 输入的地址名称
        'key': API_KEY       # API密钥
    }
    
    try:
        response = requests.get(GEO_URL, params=params, timeout=10)  # 发送GET请求，设置超时
        data = response.json()
        
        # 检查API返回状态：status为'1'表示成功，count不为'0'表示有结果
        if data['status'] == '1' and data['count'] != '0':
            location = data['geocodes'][0]['location']  # 提取经纬度字符串
            coords = location.split(',')  # 分割经度和纬度
            return [float(coords[0]), float(coords[1])]  # 返回浮点数格式的坐标
        else:
            print(f"地址 '{address}' 坐标获取失败: {data.get('info', '未知错误')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except Exception as e:
        print(f"坐标转换错误: {e}")
        return None

def get_route(origin, destination):
    """
    通过高德地图路径规划API获取从起始地到目的地的路线信息
    参数：origin和destination为[经度, 纬度]格式的坐标
    """
    params = {
        'origin': f"{origin[0]},{origin[1]}",         # 起始地经纬度
        'destination': f"{destination[0]},{destination[1]}",  # 目的地经纬度
        'key': API_KEY,                               # API密钥
        'extensions': 'all'                           # 返回详细路线信息
    }
    
    try:
        response = requests.get(ROUTE_URL, params=params, timeout=15)  # 发送GET请求
        data = response.json()
        
        # 检查API返回状态：status为'1'表示成功
        if data['status'] == '1':
            return data['route']  # 返回路线数据
        else:
            print(f"路线规划失败: {data.get('info', '未知错误')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except Exception as e:
        print(f"路线规划错误: {e}")
        return None

def calculate_multi_point_route(coordinates_list):
    """
    计算多点间的路线规划
    参数：coordinates_list - 坐标列表，格式为[[lng1,lat1], [lng2,lat2], ...]
    返回：包含所有路段信息的列表
    """
    if len(coordinates_list) < 2:
        return []
    
    routes = []
    # 计算相邻两点间的路线
    for i in range(len(coordinates_list) - 1):
        route = get_route(coordinates_list[i], coordinates_list[i + 1])
        if route:
            routes.append({
                'from': coordinates_list[i],
                'to': coordinates_list[i + 1],
                'route_data': route
            })
    
    return routes

@app.route('/')
def index():
    """渲染Web界面的主页"""
    return render_template('index.html')

@app.route('/extract_and_plan', methods=['POST'])
def extract_and_plan_route():
    """
    处理文本地址提取和路线规划的主要API端点
    接收用户输入的文本，提取地址，转换坐标，规划路线
    """
    try:
        # 获取用户输入的文本
        input_text = request.json.get('text', '')
        
        if not input_text.strip():
            return jsonify({'error': '输入文本不能为空'})
        
        # 1. 从文本中提取地址
        addresses = extract_addresses_from_text(input_text)
        
        if not addresses:
            return jsonify({'error': '未能从文本中提取到有效地址'})
        
        print(f"提取到的地址: {addresses}")  # 调试输出
        
        # 2. 将地址转换为坐标
        locations = []
        for address in addresses:
            coords = get_coordinates(address)
            if coords:
                locations.append({
                    'name': address,
                    'coordinates': coords,
                    'description': f'地点: {address}'  # 这里可以后续扩展为景点说明
                })
        
        if not locations:
            return jsonify({'error': '所有地址都无法转换为有效坐标'})
        
        # 3. 计算多点路线规划
        coordinates_list = [loc['coordinates'] for loc in locations]
        routes = calculate_multi_point_route(coordinates_list)
        
        # 4. 返回结果
        result = {
            'success': True,
            'addresses': addresses,
            'locations': locations,
            'routes': routes,
            'total_locations': len(locations)
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"处理请求时发生错误: {e}")
        return jsonify({'error': f'服务器内部错误: {str(e)}'})

@app.route('/get_coordinates', methods=['POST'])
def get_coordinates_api():
    """
    单独的坐标获取API端点
    用于获取单个地址的坐标信息
    """
    try:
        address = request.json.get('address', '')
        
        if not address.strip():
            return jsonify({'error': '地址不能为空'})
        
        coords = get_coordinates(address)
        
        if coords:
            return jsonify({
                'success': True,
                'address': address,
                'coordinates': coords
            })
        else:
            return jsonify({'error': f'无法获取地址 "{address}" 的坐标'})
            
    except Exception as e:
        return jsonify({'error': f'坐标获取失败: {str(e)}'})

# ⚠️ 调试配置：根据您的设备情况调整以下参数
if __name__ == '__main__':
    # 端口配置：如果5000端口被占用，请修改为其他端口（如5001, 8080等）
    PORT = 5000
    
    # 主机配置：本地调试使用'127.0.0.1'，局域网访问使用'0.0.0.0'
    HOST = '127.0.0.1'
    
    print(f"启动Flask应用...")
    print(f"访问地址: http://{HOST}:{PORT}")
    print(f"请确保:")
    print(f"1. API Key '{API_KEY[:10]}...' 有效且有足够配额")
    print(f"2. 网络可以访问高德地图API服务")
    print(f"3. 端口 {PORT} 未被其他程序占用")
    
    app.run(
        host=HOST,      # ⚠️ 根据需要调整主机地址
        port=PORT,      # ⚠️ 根据需要调整端口
        debug=True      # 开发模式，生产环境请设为False
    )