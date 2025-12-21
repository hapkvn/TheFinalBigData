import requests
import json
from cassandra.cluster import Cluster
from datetime import datetime
import time

# 1. Cấu hình
TOMTOM_KEY = "ongdJdbk2vMblJsUqljZ9PUmflEntbzI"
POINTS_TO_MONITOR = [
    {"name": "Nga_Tu_So", "lat": 21.0025, "lon": 105.8200},
    {"name": "Cau_Giay", "lat": 21.0345, "lon": 105.7950}
    # Thêm các điểm nóng giao thông bạn muốn theo dõi vào đây
]

# 2. Kết nối Cassandra
cluster = Cluster(['127.0.0.1']) # IP của Cassandra
session = cluster.connect()
session.execute("""
    CREATE KEYSPACE IF NOT EXISTS traffic_keyspace 
    WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 1 }
""")
session.set_keyspace('traffic_keyspace')
session.execute("""
    CREATE TABLE IF NOT EXISTS traffic_status (
        sensor_id text,
        timestamp timestamp,
        lat double,
        lon double,
        current_speed int,
        free_flow_speed int,
        congestion_ratio double,
        PRIMARY KEY (sensor_id, timestamp)
    )
""")

# 3. Hàm lấy dữ liệu từ TomTom
def get_traffic_data(lat, lon):
    # Endpoint: Flow Segment Data
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={TOMTOM_KEY}&point={lat},{lon}"
    try:
        response = requests.get(url)
        data = response.json()
        
        # Phân tích JSON trả về
        flow_data = data['flowSegmentData']
        current_speed = flow_data['currentSpeed']
        free_flow_speed = flow_data['freeFlowSpeed']
        
        # Tính tỷ lệ tắc nghẽn (0.0 -> 1.0)
        ratio = current_speed / free_flow_speed if free_flow_speed > 0 else 0
        
        return current_speed, free_flow_speed, ratio
    except Exception as e:
        print(f"Lỗi gọi API: {e}")
        return 0, 0, 0

# 4. Vòng lặp thu thập (Real-time)
while True:
    for point in POINTS_TO_MONITOR:
        c_speed, f_speed, ratio = get_traffic_data(point['lat'], point['lon'])
        
        # Ghi vào Cassandra
        query = """
            INSERT INTO traffic_status (sensor_id, timestamp, lat, lon, current_speed, free_flow_speed, congestion_ratio)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        session.execute(query, (point['name'], datetime.now(), point['lat'], point['lon'], c_speed, f_speed, ratio))
        print(f"Đã ghi: {point['name']} - Ratio: {ratio:.2f}")
        
    time.sleep(60) # Chờ 60 giây trước khi cập nhật lại (TomTom update mỗi 1 phút)