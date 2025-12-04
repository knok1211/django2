"""
데이터 분석 관련 뷰
"""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .busstop import BUS_STOPS_8201
import os


def analysis_page(request):
    """
    데이터 분석 페이지
    """
    return render(request, 'bus_info/analysis.html')


@csrf_exempt
@require_http_methods(["POST"])
def upload_database(request):
    """
    SQLite 데이터베이스 파일 업로드
    """
    try:
        if 'database' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': '데이터베이스 파일이 없습니다.'
            }, status=400)
        
        db_file = request.FILES['database']
        
        # 파일 확장자 확인
        if not db_file.name.endswith('.sqlite3'):
            return JsonResponse({
                'success': False,
                'error': 'SQLite 데이터베이스 파일(.sqlite3)만 업로드 가능합니다.'
            }, status=400)
        
        # 임시 파일로 저장
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        temp_db_path = os.path.join(temp_dir, 'uploaded_db.sqlite3')
        
        with open(temp_db_path, 'wb+') as destination:
            for chunk in db_file.chunks():
                destination.write(chunk)
        
        # 데이터베이스 연결 테스트 및 날짜 범위 조회
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bus_info_buscollection'")
        if not cursor.fetchone():
            conn.close()
            shutil.rmtree(temp_dir)
            return JsonResponse({
                'success': False,
                'error': '올바른 버스 데이터베이스 파일이 아닙니다.'
            }, status=400)
        
        # 날짜 범위 조회
        cursor.execute("""
            SELECT 
                MIN(collection_date) as min_date,
                MAX(collection_date) as max_date,
                COUNT(DISTINCT collection_date) as total_dates,
                COUNT(*) as total_collections
            FROM bus_info_buscollection
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        # 세션에 임시 파일 경로 저장
        request.session['temp_db_path'] = temp_db_path
        request.session['temp_dir'] = temp_dir
        
        return JsonResponse({
            'success': True,
            'message': '데이터베이스 파일이 업로드되었습니다.',
            'data': {
                'min_date': result[0],
                'max_date': result[1],
                'total_dates': result[2],
                'total_collections': result[3]
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'업로드 중 오류 발생: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def start_analysis(request):
    """
    데이터 분석 시작 - 일자별 목록 반환
    """
    try:
        import json
        data = json.loads(request.body)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return JsonResponse({
                'success': False,
                'error': '시작 날짜와 종료 날짜를 모두 입력해주세요.'
            }, status=400)
        
        # 세션에서 임시 DB 경로 가져오기
        temp_db_path = request.session.get('temp_db_path')
        
        if not temp_db_path or not os.path.exists(temp_db_path):
            return JsonResponse({
                'success': False,
                'error': '업로드된 데이터베이스 파일을 찾을 수 없습니다. 다시 업로드해주세요.'
            }, status=400)
        
        # 기간 내 일자별 데이터 조회
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                collection_date,
                COUNT(*) as total_collections,
                COUNT(CASE WHEN is_error = 0 AND is_skipped = 0 THEN 1 END) as successful_collections
            FROM bus_info_buscollection
            WHERE collection_date BETWEEN ? AND ?
            GROUP BY collection_date
            ORDER BY collection_date DESC
        """, (start_date, end_date))
        
        daily_list = []
        for row in cursor.fetchall():
            daily_list.append({
                'date': row[0],
                'total_collections': row[1],
                'successful_collections': row[2]
            })
        
        conn.close()
        
        # 세션에 분석 기간 저장
        request.session['analysis_start_date'] = start_date
        request.session['analysis_end_date'] = end_date
        
        return JsonResponse({
            'success': True,
            'message': '분석이 시작되었습니다.',
            'data': {
                'start_date': start_date,
                'end_date': end_date,
                'daily_list': daily_list
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'분석 시작 중 오류 발생: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_analysis_data(request):
    """
    특정 날짜의 승객 수 변화량 분석 데이터 조회
    """
    try:
        date = request.GET.get('date')
        
        if not date:
            return JsonResponse({
                'success': False,
                'error': '날짜를 입력해주세요.'
            }, status=400)
        
        # 세션에서 임시 DB 경로 가져오기
        temp_db_path = request.session.get('temp_db_path')
        
        if not temp_db_path or not os.path.exists(temp_db_path):
            return JsonResponse({
                'success': False,
                'error': '업로드된 데이터베이스 파일을 찾을 수 없습니다.'
            }, status=400)
        
        import sqlite3
        from datetime import datetime as dt
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # 해당 날짜의 성공한 수집 데이터 조회
        cursor.execute("""
            SELECT 
                c.id,
                c.query_time,
                b.plate_no,
                b.station_seq,
                b.remain_seat_cnt
            FROM bus_info_buscollection c
            LEFT JOIN bus_info_busdata b ON c.id = b.collection_id
            WHERE c.collection_date = ?
            AND c.is_error = 0
            AND c.is_skipped = 0
            ORDER BY c.query_time, b.plate_no, CAST(b.station_seq AS INTEGER)
        """, (date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 평일/주말 판단
        date_obj = dt.strptime(date, '%Y-%m-%d')
        is_weekend = date_obj.weekday() >= 5  # 5=토요일, 6=일요일
        
        # 데이터 구조화 및 배차 구분
        bus_trips = {}
        bus_last_station = {}
        bus_trip_counter = {}
        
        for row in rows:
            collection_id, query_time, plate_no, station_seq, remain_seat = row
            
            if not plate_no or not station_seq:
                continue
            
            try:
                station_idx = int(station_seq)
                if not (0 <= station_idx < len(BUS_STOPS_8201)):
                    continue
            except:
                continue
            
            # 배차 구분 로직
            if plate_no not in bus_trip_counter:
                bus_trip_counter[plate_no] = 1
                bus_last_station[plate_no] = station_idx
            else:
                if station_idx < bus_last_station[plate_no] - 20:
                    bus_trip_counter[plate_no] += 1
                bus_last_station[plate_no] = station_idx
            
            trip_key = f"{plate_no}_{bus_trip_counter[plate_no]}"
            
            if trip_key not in bus_trips:
                bus_trips[trip_key] = {}
            
            if query_time not in bus_trips[trip_key]:
                bus_trips[trip_key][query_time] = {}
            
            bus_trips[trip_key][query_time][station_idx] = remain_seat
        
        # 배차 수 제한
        max_trips = 16 if is_weekend else 20
        
        # 출발 시간 순서대로 정렬
        trip_start_times = {}
        for trip_key, time_data in bus_trips.items():
            times = sorted(time_data.keys())
            if times:
                trip_start_times[trip_key] = times[0]
        
        sorted_trip_keys = sorted(trip_start_times.keys(), key=lambda x: trip_start_times[x])
        limited_trip_keys = sorted_trip_keys[:max_trips]
        
        # 현재 승객 수 계산
        BUS_CAPACITY = 45
        MIDPOINT_STATION_1 = 26
        MIDPOINT_STATION_2 = 51
        
        result_data = {}
        
        for trip_key in limited_trip_keys:
            time_data = bus_trips[trip_key]
            result_data[trip_key] = {}
            
            times = sorted(time_data.keys())
            
            for current_time in times:
                stations_in_time = time_data[current_time]
                sorted_stations = sorted(stations_in_time.keys())
                
                for station_idx in sorted_stations:
                    remain_seat = stations_in_time[station_idx]
                    
                    if remain_seat == -1:
                        continue
                    
                    if station_idx == MIDPOINT_STATION_1:
                        current_passengers = 0
                    else:
                        current_passengers = BUS_CAPACITY - remain_seat
                        if current_passengers < 0:
                            current_passengers = 0
                    
                    result_data[trip_key][station_idx] = current_passengers
        

            if MIDPOINT_STATION_1 not in result_data[trip_key]:
                result_data[trip_key][MIDPOINT_STATION_1] = 0
            if MIDPOINT_STATION_2 not in result_data[trip_key]:
                result_data[trip_key][MIDPOINT_STATION_2] = 0
            
            
            for station_idx in range(len(BUS_STOPS_8201)):
                if station_idx == MIDPOINT_STATION_1:
                    continue
                
                # 다음 정류장이 (경유)인지 확인하고 대체 (결측치 여부와 관계없이)
                next_is_bypass = False
                next_value = None
                
                for next_idx in range(station_idx + 1, len(BUS_STOPS_8201)):
                    if next_idx < len(BUS_STOPS_8201):
                        if "(경유)" in BUS_STOPS_8201[next_idx]:
                            if next_idx in result_data[trip_key]:
                                next_is_bypass = True
                                next_value = result_data[trip_key][next_idx]
                                break
                        else:
                            break

                

                if next_is_bypass and next_value is not None:
                    result_data[trip_key][station_idx] = next_value
                    continue

                # 결측 데이터
                
                if station_idx not in result_data[trip_key]:
                    filled = False
                    
                    # 1. 현재와 이전이 모두 (경유)
                    if station_idx > 0 and station_idx < len(BUS_STOPS_8201):
                        current_is_bypass = "(경유)" in BUS_STOPS_8201[station_idx]
                        
                        for prev_idx in range(station_idx - 1, -1, -1):
                            if prev_idx in result_data[trip_key]:
                                prev_is_bypass = "(경유)" in BUS_STOPS_8201[prev_idx]
                                
                                if current_is_bypass and prev_is_bypass:
                                    result_data[trip_key][station_idx] = result_data[trip_key][prev_idx]
                                    filled = True
                                break
                
                    # 2. 평균 보간
                    if not filled:
                        prev_value = None
                        next_value = None
                        
                        for prev_idx in range(station_idx - 1, -1, -1):
                            if prev_idx in result_data[trip_key]:
                                prev_value = result_data[trip_key][prev_idx]
                                break
                        
                        for next_idx in range(station_idx + 1, len(BUS_STOPS_8201)):
                            if next_idx in result_data[trip_key]:
                                next_value = result_data[trip_key][next_idx]
                                break
                        
                        if prev_value is not None and next_value is not None:
                            result_data[trip_key][station_idx] = round((prev_value + next_value) / 2)

        
        # 변화량 계산
        change_data = {}
        for trip_key in limited_trip_keys:
            change_data[trip_key] = {}
            
            for station_idx in range(len(BUS_STOPS_8201)):
                if station_idx not in result_data[trip_key]:
                    continue
                
                current_passengers = result_data[trip_key][station_idx]
                
                # 이전 정류장 찾기
                prev_passengers = None
                for prev_idx in range(station_idx - 1, -1, -1):
                    if prev_idx in result_data[trip_key]:
                        prev_passengers = result_data[trip_key][prev_idx]
                        break
                
                if prev_passengers is not None:
                    # 8-26: 승차 인원 (현재 - 이전)
                    # 27-51: 하차 인원 (이전 - 현재)
                    if station_idx <= 26:
                        change = current_passengers - prev_passengers
                    else:
                        change = prev_passengers - current_passengers
                    
                    change_data[trip_key][station_idx] = change
        
        return JsonResponse({
            'success': True,
            'data': {
                'date': date,
                'is_weekend': is_weekend,
                'max_trips': max_trips,
                'buses': limited_trip_keys,
                'stations': BUS_STOPS_8201,
                'passengers': result_data,  # 승객 수
                'changes': change_data  # 변화량
            }
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'분석 데이터 조회 중 오류 발생: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)


def calculate_average_data(temp_db_path, start_date, end_date, weekday_filter=None, is_weekend_only=None):
    """
    평균 데이터 계산 헬퍼 함수
    weekday_filter: None(전체), 0(월), 1(화), ..., 6(일)
    is_weekend_only: None(전체), True(주말만), False(평일만)
    """
    import sqlite3
    from datetime import datetime as dt
    from collections import defaultdict
    
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # 날짜 필터링
    if weekday_filter is not None:
        # 요일별 필터링을 위해 모든 날짜를 가져와서 필터링
        cursor.execute("""
            SELECT DISTINCT collection_date
            FROM bus_info_buscollection
            WHERE collection_date BETWEEN ? AND ?
        """, (start_date, end_date))
        
        all_dates = [row[0] for row in cursor.fetchall()]
        filtered_dates = []
        for date_str in all_dates:
            date_obj = dt.strptime(date_str, '%Y-%m-%d')
            if date_obj.weekday() == weekday_filter:
                filtered_dates.append(date_str)
        
        if not filtered_dates:
            conn.close()
            return None
        
        # 파라미터화된 쿼리를 위한 플레이스홀더 생성
        placeholders = ','.join(['?'] * len(filtered_dates))
        date_condition = f"collection_date IN ({placeholders})"
        query_params = tuple(filtered_dates)
    elif is_weekend_only is not None:
        # 평일/주말 필터링
        cursor.execute("""
            SELECT DISTINCT collection_date
            FROM bus_info_buscollection
            WHERE collection_date BETWEEN ? AND ?
        """, (start_date, end_date))
        
        all_dates = [row[0] for row in cursor.fetchall()]
        filtered_dates = []
        for date_str in all_dates:
            date_obj = dt.strptime(date_str, '%Y-%m-%d')
            is_weekend = date_obj.weekday() >= 5
            if (is_weekend_only and is_weekend) or (not is_weekend_only and not is_weekend):
                filtered_dates.append(date_str)
        
        if not filtered_dates:
            conn.close()
            return None
        
        placeholders = ','.join(['?'] * len(filtered_dates))
        date_condition = f"collection_date IN ({placeholders})"
        query_params = tuple(filtered_dates)
    else:
        date_condition = "collection_date BETWEEN ? AND ?"
        query_params = (start_date, end_date)
    
    # 해당 기간의 성공한 수집 데이터 조회
    cursor.execute(f"""
        SELECT 
            c.id,
            c.query_time,
            c.collection_date,
            b.plate_no,
            b.station_seq,
            b.remain_seat_cnt
        FROM bus_info_buscollection c
        LEFT JOIN bus_info_busdata b ON c.id = b.collection_id
        WHERE {date_condition}
        AND c.is_error = 0
        AND c.is_skipped = 0
        ORDER BY c.collection_date, c.query_time, b.plate_no, CAST(b.station_seq AS INTEGER)
    """, query_params)
    
    rows = cursor.fetchall()
    conn.close()
    
    # 날짜별로 데이터 그룹화
    date_data = defaultdict(list)
    for row in rows:
        collection_id, query_time, collection_date, plate_no, station_seq, remain_seat = row
        date_data[collection_date].append((collection_id, query_time, plate_no, station_seq, remain_seat))
    
    # 각 날짜별로 승객 수 계산
    # 배차 순서를 유지하기 위해 각 날짜별 배차 순서를 저장
    # [배차_순서][station_idx] = [승객 수 리스트]
    all_passenger_data_by_order = defaultdict(lambda: defaultdict(list))
    # 각 날짜별 배차 순서 정보 저장: [날짜] = [(trip_key, start_time), ...]
    date_trip_orders = {}
    
    for date_str, date_rows in date_data.items():
        # 해당 날짜의 데이터 처리 (기존 로직과 동일)
        bus_trips = {}
        bus_last_station = {}
        bus_trip_counter = {}
        
        for row in date_rows:
            collection_id, query_time, plate_no, station_seq, remain_seat = row
            
            if not plate_no or not station_seq:
                continue
            
            try:
                station_idx = int(station_seq)
                if not (0 <= station_idx < len(BUS_STOPS_8201)):
                    continue
            except:
                continue
            
            # 배차 구분 로직
            if plate_no not in bus_trip_counter:
                bus_trip_counter[plate_no] = 1
                bus_last_station[plate_no] = station_idx
            else:
                if station_idx < bus_last_station[plate_no] - 20:
                    bus_trip_counter[plate_no] += 1
                bus_last_station[plate_no] = station_idx
            
            trip_key = f"{plate_no}_{bus_trip_counter[plate_no]}"
            
            if trip_key not in bus_trips:
                bus_trips[trip_key] = {}
            
            if query_time not in bus_trips[trip_key]:
                bus_trips[trip_key][query_time] = {}
            
            bus_trips[trip_key][query_time][station_idx] = remain_seat
        
        # 평일/주말 판단
        date_obj = dt.strptime(date_str, '%Y-%m-%d')
        is_weekend = date_obj.weekday() >= 5
        max_trips = 16 if is_weekend else 20
        
        # 출발 시간 순서대로 정렬
        trip_start_times = {}
        for trip_key, time_data in bus_trips.items():
            times = sorted(time_data.keys())
            if times:
                trip_start_times[trip_key] = times[0]
        
        sorted_trip_keys = sorted(trip_start_times.keys(), key=lambda x: trip_start_times[x])
        limited_trip_keys = sorted_trip_keys[:max_trips]
        
        # 배차 순서 저장 (출발 시간과 함께)
        date_trip_orders[date_str] = [(trip_key, trip_start_times[trip_key]) for trip_key in limited_trip_keys]
        
        # 현재 승객 수 계산
        BUS_CAPACITY = 45
        MIDPOINT_STATION_1 = 26
        MIDPOINT_STATION_2 = 51
        
        result_data = {}
        
        for trip_key in limited_trip_keys:
            time_data = bus_trips[trip_key]
            result_data[trip_key] = {}
            
            times = sorted(time_data.keys())
            
            for current_time in times:
                stations_in_time = time_data[current_time]
                sorted_stations = sorted(stations_in_time.keys())
                
                for station_idx in sorted_stations:
                    remain_seat = stations_in_time[station_idx]
                    
                    if remain_seat == -1:
                        continue
                    
                    if station_idx == MIDPOINT_STATION_1:
                        current_passengers = 0
                    else:
                        current_passengers = BUS_CAPACITY - remain_seat
                        if current_passengers < 0:
                            current_passengers = 0
                    
                    result_data[trip_key][station_idx] = current_passengers
            
            if MIDPOINT_STATION_1 not in result_data[trip_key]:
                result_data[trip_key][MIDPOINT_STATION_1] = 0
            if MIDPOINT_STATION_2 not in result_data[trip_key]:
                result_data[trip_key][MIDPOINT_STATION_2] = 0
            
            # 결측치 처리 (기존 로직과 동일)
            for station_idx in range(len(BUS_STOPS_8201)):
                if station_idx == MIDPOINT_STATION_1:
                    continue
                
                next_is_bypass = False
                next_value = None
                
                for next_idx in range(station_idx + 1, len(BUS_STOPS_8201)):
                    if next_idx < len(BUS_STOPS_8201):
                        if "(경유)" in BUS_STOPS_8201[next_idx]:
                            if next_idx in result_data[trip_key]:
                                next_is_bypass = True
                                next_value = result_data[trip_key][next_idx]
                                break
                        else:
                            break
                
                if next_is_bypass and next_value is not None:
                    result_data[trip_key][station_idx] = next_value
                    continue
                
                if station_idx not in result_data[trip_key]:
                    filled = False
                    
                    if station_idx > 0 and station_idx < len(BUS_STOPS_8201):
                        current_is_bypass = "(경유)" in BUS_STOPS_8201[station_idx]
                        
                        for prev_idx in range(station_idx - 1, -1, -1):
                            if prev_idx in result_data[trip_key]:
                                prev_is_bypass = "(경유)" in BUS_STOPS_8201[prev_idx]
                                
                                if current_is_bypass and prev_is_bypass:
                                    result_data[trip_key][station_idx] = result_data[trip_key][prev_idx]
                                    filled = True
                                break
                    
                    if not filled:
                        prev_value = None
                        next_value = None
                        
                        for prev_idx in range(station_idx - 1, -1, -1):
                            if prev_idx in result_data[trip_key]:
                                prev_value = result_data[trip_key][prev_idx]
                                break
                        
                        for next_idx in range(station_idx + 1, len(BUS_STOPS_8201)):
                            if next_idx in result_data[trip_key]:
                                next_value = result_data[trip_key][next_idx]
                                break
                        
                        if prev_value is not None and next_value is not None:
                            result_data[trip_key][station_idx] = round((prev_value + next_value) / 2)
        
        # 각 배차에서 0의 개수 확인 (10개 이상이면 제외)
        for trip_key in limited_trip_keys:
            zero_count = 0
            for station_idx in range(len(BUS_STOPS_8201)):
                if station_idx in result_data[trip_key] and result_data[trip_key][station_idx] == 0:
                    zero_count += 1
            
            # 0이 10개 미만인 배차만 포함
            if zero_count < 10:
                # 배차 순서에 따라 데이터 누적
                trip_order = limited_trip_keys.index(trip_key)
                for station_idx in range(len(BUS_STOPS_8201)):
                    if station_idx in result_data[trip_key]:
                        all_passenger_data_by_order[trip_order][station_idx].append(result_data[trip_key][station_idx])
    
    # 평균 계산 (배차 순서대로)
    avg_passenger_data = {}
    sorted_trip_keys = []
    
    # 배차 순서대로 정렬 (가장 많은 날짜에서 나타나는 순서 사용)
    if date_trip_orders:
        # 가장 많은 배차를 가진 날짜의 순서를 기준으로 사용
        max_trips_date = max(date_trip_orders.keys(), key=lambda d: len(date_trip_orders[d]))
        base_order = date_trip_orders[max_trips_date]
        
        for order_idx, (trip_key, start_time) in enumerate(base_order):
            if order_idx in all_passenger_data_by_order:
                # 배차 이름 생성 (순서 기반)
                trip_name = f"배차_{order_idx + 1}"
                sorted_trip_keys.append(trip_name)
                avg_passenger_data[trip_name] = {}
                
                for station_idx, values in all_passenger_data_by_order[order_idx].items():
                    if values:
                        avg_passenger_data[trip_name][station_idx] = round(sum(values) / len(values), 1)
    
    # 변화량 계산
    change_data = {}
    for trip_name in sorted_trip_keys:
        change_data[trip_name] = {}
        
        for station_idx in range(len(BUS_STOPS_8201)):
            if station_idx not in avg_passenger_data[trip_name]:
                continue
            
            current_passengers = avg_passenger_data[trip_name][station_idx]
            
            prev_passengers = None
            for prev_idx in range(station_idx - 1, -1, -1):
                if prev_idx in avg_passenger_data[trip_name]:
                    prev_passengers = avg_passenger_data[trip_name][prev_idx]
                    break
            
            if prev_passengers is not None:
                if station_idx <= 26:
                    change = current_passengers - prev_passengers
                else:
                    change = prev_passengers - current_passengers
                
                change_data[trip_name][station_idx] = round(change, 1)
    
    return {
        'buses': sorted_trip_keys,
        'passengers': avg_passenger_data,
        'changes': change_data
    }


@csrf_exempt
@require_http_methods(["GET"])
def get_average_analysis(request):
    """
    전체 평균 또는 요일별 평균 분석 데이터 조회
    """
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        weekday = request.GET.get('weekday')  # None 또는 0-6
        
        if not start_date or not end_date:
            return JsonResponse({
                'success': False,
                'error': '시작 날짜와 종료 날짜를 모두 입력해주세요.'
            }, status=400)
        
        temp_db_path = request.session.get('temp_db_path')
        
        if not temp_db_path or not os.path.exists(temp_db_path):
            return JsonResponse({
                'success': False,
                'error': '업로드된 데이터베이스 파일을 찾을 수 없습니다.'
            }, status=400)
        
        weekday_filter = int(weekday) if weekday is not None and weekday != '' else None
        is_weekend_only = request.GET.get('is_weekend_only')  # 'true' 또는 'false' 또는 None
        
        # is_weekend_only 파라미터 처리
        weekend_filter = None
        if is_weekend_only is not None:
            weekend_filter = is_weekend_only.lower() == 'true'
        
        result = calculate_average_data(temp_db_path, start_date, end_date, weekday_filter, weekend_filter)
        
        if result is None:
            return JsonResponse({
                'success': False,
                'error': '해당 조건에 맞는 데이터가 없습니다.'
            }, status=400)
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        if weekday_filter is not None:
            title = weekday_names[weekday_filter]
        elif weekend_filter is True:
            title = '주말 평균'
        elif weekend_filter is False:
            title = '평일 평균'
        else:
            title = '전체 평균'
        
        return JsonResponse({
            'success': True,
            'data': {
                'title': title,
                'start_date': start_date,
                'end_date': end_date,
                'buses': result['buses'],
                'stations': BUS_STOPS_8201,
                'passengers': result['passengers'],
                'changes': result['changes']
            }
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'평균 분석 데이터 조회 중 오류 발생: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)