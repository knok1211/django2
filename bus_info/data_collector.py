import threading
import time
from datetime import datetime, time as dt_time
from django.utils import timezone
from .config import (
    GBIS_SERVICE_KEY, 
    GBIS_API_ENDPOINT, 
    API_TIMEOUT, 
    RESPONSE_FORMAT
)
import requests
import urllib.parse


class BusDataCollector:
    """
    버스 데이터를 자동으로 수집하고 데이터베이스에 저장하는 클래스
    """
    
    def __init__(self, route_id="234001730", interval_seconds=90):
        self.route_id = route_id
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.thread = None
    
    def is_skip_time(self, query_time_str=None):
        """
        현재 시간이 00:00 ~ 05:30 범위인지 확인 (UTC+9 기준)
        """
        try:
            from datetime import timedelta
            # UTC+9 시간 계산
            utc_now = datetime.utcnow()
            kst_now = utc_now + timedelta(hours=9)
            current_time = kst_now.time()
            
            # 00:00 ~ 05:30 범위 확인
            skip_start = dt_time(0, 0)  # 00:00
            skip_end = dt_time(5, 30)   # 05:30
            
            return skip_start <= current_time <= skip_end
            
        except Exception as e:
            print(f"시간 확인 오류: {e}")
            return False
    


    def collect_bus_data(self):
        """
        현재 시점의 버스 데이터를 수집
        """
        try:
            # 00:00 ~ 05:30 시간대 체크 (UTC+9 기준) - API 요청 전에 먼저 확인
            if self.is_skip_time():
                # 서버 시간으로 대체
                from datetime import timedelta
                utc_now = datetime.utcnow()
                kst_now = utc_now + timedelta(hours=9)
                server_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')
                
                return {
                    'query_time': server_time,
                    'skipped': True,
                    'skip_reason': '00:00 ~ 05:30 시간대는 수집하지 않습니다. (KST 기준)'
                }
            
            # 서비스키 디코딩
            decoded_service_key = urllib.parse.unquote(GBIS_SERVICE_KEY)
            
            # API 요청 파라미터
            params = {
                'serviceKey': decoded_service_key,
                'routeId': self.route_id,
                'format': RESPONSE_FORMAT
            }
            
            # API 요청
            response = requests.get(GBIS_API_ENDPOINT, params=params, timeout=API_TIMEOUT)
            response.raise_for_status()
            
            # JSON 응답 파싱
            data = response.json()
            
            # 응답 데이터 처리
            response_data = data.get('response', {})
            msg_header = response_data.get('msgHeader', {})
            msg_body = response_data.get('msgBody', {})
            
            result_code = msg_header.get('resultCode')
            result_message = msg_header.get('resultMessage', '')
            query_time = msg_header.get('queryTime', 'N/A')
            
            if result_code == 0:
                bus_list = msg_body.get('busLocationList', [])
                
                # 서버 시간으로 대체
                from datetime import timedelta
                utc_now = datetime.utcnow()
                kst_now = utc_now + timedelta(hours=9)
                server_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')
                
                # 수집된 데이터 구조화
                collected_data = {
                    'query_time': server_time,
                    'buses': []
                }
                
                # 각 버스 데이터 처리 - 요청된 3개 필드만
                for bus in bus_list:
                    bus_data = {
                        'plateNo': bus.get('plateNo', 'N/A'),
                        'remainSeatCnt': bus.get('remainSeatCnt', -1),
                        'stationSeq': bus.get('stationSeq', 'N/A')
                    }
                    collected_data['buses'].append(bus_data)
                
                # 버스 데이터를 정류소 순번 순으로 정렬
                def sort_key(bus):
                    station_seq = str(bus['stationSeq'])
                    try:
                        return int(station_seq)
                    except (ValueError, TypeError):
                        # 숫자가 아닌 경우 맨 뒤로 정렬
                        return float('inf')
                
                collected_data['buses'].sort(key=sort_key)
                
                return collected_data
            else:
                # 서버 시간으로 대체
                from datetime import timedelta
                utc_now = datetime.utcnow()
                kst_now = utc_now + timedelta(hours=9)
                server_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')
                
                return {
                    'query_time': server_time,
                    'route_id': self.route_id,
                    'result_code': result_code,
                    'result_message': result_message,
                    'error': True
                }
                
        except Exception as e:
            # 서버 시간으로 대체
            from datetime import timedelta
            utc_now = datetime.utcnow()
            kst_now = utc_now + timedelta(hours=9)
            server_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                'query_time': server_time,
                'route_id': self.route_id,
                'error': True,
                'error_message': str(e)
            }
    
    def save_to_database(self, data):
        """
        수집된 데이터를 데이터베이스에 저장
        """
        try:
            from .models import BusCollection, BusData
            
            query_time_str = data.get('query_time', 'N/A')
            
            # 쿼리 시간 파싱
            if query_time_str != 'N/A':
                if '.' in query_time_str:
                    query_time_str = query_time_str.split('.')[0]
                query_time = datetime.strptime(query_time_str, '%Y-%m-%d %H:%M:%S')
                query_time = timezone.make_aware(query_time)
                collection_date = query_time.date()
            else:
                query_time = timezone.now()
                collection_date = query_time.date()
            
            # BusCollection 생성
            collection = BusCollection.objects.create(
                route_id=self.route_id,
                query_time=query_time,
                collection_date=collection_date,
                result_code=data.get('result_code', 0),
                result_message=data.get('result_message', ''),
                is_error=data.get('error', False),
                error_message=data.get('error_message', ''),
                is_skipped=data.get('skipped', False),
                skip_reason=data.get('skip_reason', '')
            )
            
            # 버스 데이터가 있는 경우에만 BusData 생성
            if 'buses' in data and not data.get('error', False) and not data.get('skipped', False):
                bus_data_objects = []
                for bus in data['buses']:
                    bus_data_objects.append(BusData(
                        collection=collection,
                        plate_no=bus.get('plateNo', 'N/A'),
                        remain_seat_cnt=bus.get('remainSeatCnt', -1),
                        station_seq=str(bus.get('stationSeq', 'N/A'))
                    ))
                
                # 벌크 생성으로 성능 최적화
                if bus_data_objects:
                    BusData.objects.bulk_create(bus_data_objects)
            
            return collection.id
            
        except Exception as e:
            print(f"데이터베이스 저장 오류: {e}")
            return None
    
    def get_log_time_kst(self):
        """
        현재 시간을 KST(UTC+9) 기준으로 로그용 형식으로 반환
        """
        try:
            from datetime import timedelta
            # UTC+9 시간 계산
            utc_now = datetime.utcnow()
            kst_now = utc_now + timedelta(hours=9)
            return f"[{kst_now.strftime('%Y-%m-%d %H:%M:%S')} KST]"
            
        except Exception as e:
            return f"[시간 오류: {e}]"

    def collect_and_save(self):
        """
        데이터 수집 및 저장 실행
        """
        data = self.collect_bus_data()
        query_time = data.get('query_time', 'N/A')
        log_time = self.get_log_time_kst()
        
        print(f"{log_time} 버스 데이터 수집 시작 - 노선: {self.route_id}")
        
        # 수집 건너뛰기 체크
        if data.get('skipped'):
            print(f"{log_time} 수집 건너뜀: {data.get('skip_reason')}")
            print(f"  - API 쿼리 시간: {query_time}")
            # 건너뛴 경우에도 데이터베이스에 기록
            collection_id = self.save_to_database(data)
            return collection_id
        
        collection_id = self.save_to_database(data)
        
        if collection_id:
            print(f"{log_time} 데이터 저장 완료: Collection ID {collection_id}")
            if 'buses' in data:
                print(f"  - API 쿼리 시간: {query_time}")
                print(f"  - 수집된 버스 수: {len(data['buses'])}대")
                for bus in data['buses']:
                    print(f"    🚌 {bus['plateNo']} - 잔여좌석: {bus['remainSeatCnt']}개, 정류소순번: {bus['stationSeq']}")
        else:
            print(f"{log_time} 데이터 저장 실패")
        
        return collection_id
    
    def get_current_interval(self):
        """
        수집 간격 반환
        """
        return self.interval_seconds
    
    def start_collection(self):
        """
        자동 수집 시작
        """
        if self.is_running:
            print("이미 수집이 실행 중입니다.")
            return
        
        self.is_running = True
        
        def collection_loop():
            next_collection_time = time.time()
            
            while self.is_running:
                current_time = time.time()
                
                if current_time >= next_collection_time:
                    start_time = time.time()
                    self.collect_and_save()
                    end_time = time.time()
                    
                    # 현재 시간에 따른 간격 결정
                    current_interval = self.get_current_interval()
                    next_collection_time += current_interval
                    
                    # 만약 처리 시간이 너무 길어서 다음 수집 시간을 놓쳤다면, 즉시 다음 수집 시간으로 설정
                    if next_collection_time <= current_time:
                        next_collection_time = current_time + current_interval
                    
                    processing_time = end_time - start_time
                    wait_time = next_collection_time - current_time
                    
                    print(f"  - 처리 시간: {processing_time:.2f}초, 다음 수집까지: {wait_time:.1f}초")
                
                # 0.1초마다 체크 (CPU 사용량 최소화)
                time.sleep(0.1)
        
        self.thread = threading.Thread(target=collection_loop, daemon=True)
        self.thread.start()
        print(f"자동 데이터 수집 시작 - 노선: {self.route_id}, 간격: {self.interval_seconds}초")
    
    def stop_collection(self):
        """
        자동 수집 중지
        """
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("자동 데이터 수집 중지")
    
    def get_status(self):
        """
        수집 상태 반환
        """
        return {
            'is_running': self.is_running,
            'route_id': self.route_id,
            'interval_seconds': self.interval_seconds
        }


# 전역 수집기 인스턴스
bus_collector = BusDataCollector(route_id="234001730", interval_seconds=90)
