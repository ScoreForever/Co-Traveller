import gradio as gr
import requests
import folium
from folium.plugins import MiniMap, Fullscreen
from typing import Dict, List, Tuple, Optional

# 配置高德API密钥（需替换为你的真实Key）
AMAP_API_KEY = "27c0337b84e44bb373bb2724a6ea157d"

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
        
        # 处理路线坐标（polyline）
        if "polyline" in best_route:
            result["polyline"] = best_route["polyline"]
        elif "steps" in best_route:
            polyline_points = [step.get("polyline", "") for step in best_route["steps"] if step.get("polyline")]
            result["polyline"] = ";".join(polyline_points) if polyline_points else None
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"请求异常: {str(e)}"}

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

def create_map_html(result: Dict) -> str:
    """创建路线可视化地图并返回HTML字符串"""
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
    
    # 添加圆角边框样式
    m.get_root().html.add_child(folium.Element("""
        <style>
            .folium-map {
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
        </style>
    """))
    
    # 解析起点和终点
    origin = result.get("origin", "").split(",")
    destination = result.get("destination", "").split(",")
    
    if len(origin) == 2 and len(destination) == 2:
        # 添加起点标记
        folium.Marker(
            location=[float(origin[1]), float(origin[0])],
            popup=f"起点: {result.get('origin_name', '')}",
            icon=folium.Icon(color="green", icon="flag", prefix='fa')
        ).add_to(m)
        
        # 添加终点标记
        folium.Marker(
            location=[float(destination[1]), float(destination[0])],
            popup=f"终点: {result.get('destination_name', '')}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix='fa')
        ).add_to(m)
    
    # 添加路线
    folium.PolyLine(
        locations=points,
        color='#3388ff',
        weight=6,
        opacity=0.8,
        tooltip=f"路线: {result['distance']/1000:.2f}公里, {result['duration']//60}分钟"
    ).add_to(m)
    
    # 添加比例尺
    MiniMap().add_to(m)
    
    # 添加全屏按钮
    Fullscreen().add_to(m)
    
    # 返回地图HTML字符串
    return m._repr_html_()

def process_route(start_location, end_location):
    """处理路线规划请求并返回结果"""
    try:
        # 地理编码起点
        start_coords = geocode_location(start_location)
        if not start_coords:
            return f"无法找到起点位置: {start_location}", "", ""
        
        # 地理编码终点
        end_coords = geocode_location(end_location)
        if not end_coords:
            return f"无法找到终点位置: {end_location}", "", ""
        
        start_lng, start_lat = start_coords
        end_lng, end_lat = end_coords
        
        # 计算路线
        result = calculate_driving_route(start_lng, start_lat, end_lng, end_lat)
        result["origin_name"] = start_location
        result["destination_name"] = end_location
        
        if not result["success"]:
            return f"路线规划失败: {result['error']}", "", ""
        
        # 生成路线摘要
        summary = (
            f"🚗 从 {start_location} 到 {end_location}\n\n"
            f"📏 总距离: {result['distance']/1000:.2f}公里\n"
            f"🕒 预计时间: {result['duration']//60}分钟"
        )
        
        # 生成详细路线
        step_instructions = ""
        for i, step in enumerate(result.get("steps", []), 1):
            road = step.get("road", "未知道路")
            instruction = step.get("instruction", "请按导航行驶")
            distance = step.get("distance", "0")
            
            step_instructions += f"{i}. 沿{road}行驶 {int(distance)}米\n"
            step_instructions += f"   导航提示: {instruction}\n\n"
        
        # 创建地图HTML
        map_html = create_map_html(result)
        
        return summary, map_html, step_instructions
    
    except Exception as e:
        return f"处理过程中发生错误: {str(e)}", "", ""

# 创建Gradio界面
def create_interface():
    with gr.Blocks(title="高德地图路线规划", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🗺️ 高德地图路线规划")
        gr.Markdown("输入起点和终点的位置名称（如：北京天安门、上海东方明珠），自动计算最佳驾车路线")
        
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
                
                gr.Examples(
                    examples=[
                        ["北京天安门", "北京颐和园"],
                        ["上海外滩", "上海东方明珠"],
                        ["广州塔", "广州白云机场"]
                    ],
                    inputs=[start_location, end_location],
                    label="示例路线"
                )
            
            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### 📊 路线摘要")
                    summary = gr.Textbox(label="路线信息", lines=4, interactive=False)
                
                with gr.Group():
                    gr.Markdown("### 🗺️ 路线地图")
                    map_display = gr.HTML(
                        label="路线可视化",
                        # 设置最小高度防止空白
                        value="<div style='min-height:400px; display:flex; align-items:center; justify-content:center; background:#f0f0f0; border-radius:10px;'>等待路线规划...</div>"
                    )
                
                with gr.Group():
                    gr.Markdown("### 🚥 详细路线指引")
                    step_instructions = gr.Textbox(label="导航步骤", lines=8, interactive=False)
        
        # 设置事件处理
        submit_btn.click(
            fn=process_route,
            inputs=[start_location, end_location],
            outputs=[summary, map_display, step_instructions]
        )
    
    return app

# 启动应用
if __name__ == "__main__":
    app = create_interface()
    app.launch()