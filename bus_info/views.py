from .data_collector import bus_collector
from .models import BusCollection, BusData
import os
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Q, Max, Prefetch
from django.db import models
from datetime import datetime, date





def home(request):
    """
    홈페이지 뷰
    """
    return render(request, 'bus_info/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def start_data_collection(request):
    """
    자동 데이터 수집 시작
    """
    try:
        bus_collector.start_collection()
        return JsonResponse({
            'success': True,
            'message': '자동 데이터 수집이 시작되었습니다.',
            'status': bus_collector.get_status()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def stop_data_collection(request):
    """
    자동 데이터 수집 중지
    """
    try:
        bus_collector.stop_collection()
        return JsonResponse({
            'success': True,
            'message': '자동 데이터 수집이 중지되었습니다.',
            'status': bus_collector.get_status()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_collection_status(request):
    """
    데이터 수집 상태 조회
    """
    try:
        status = bus_collector.get_status()
        
        # 오늘 날짜 수집 데이터 조회
        today = date.today()
        today_collections = BusCollection.objects.filter(
            route_id=bus_collector.route_id,
            collection_date=today
        )
        
        # 전체 수집 날짜 조회
        all_dates = BusCollection.objects.filter(
            route_id=bus_collector.route_id
        ).values('collection_date').annotate(
            count=Count('id')
        ).order_by('-collection_date')
        
        # 최신 수집 데이터 조회
        latest_collection = BusCollection.objects.filter(
            route_id=bus_collector.route_id
        ).first()
        
        status['collection_count'] = today_collections.count()
        status['total_dates'] = all_dates.count()
        status['last_updated'] = latest_collection.query_time.isoformat() if latest_collection else 'N/A'
        
        # 페이지네이션 파라미터
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        
        # 날짜별 목록 페이지네이션
        paginator = Paginator(all_dates, per_page)
        page_obj = paginator.get_page(page)
        
        date_list = []
        for item in page_obj:
            date_list.append({
                'date': item['collection_date'].strftime('%Y-%m-%d'),
                'count': item['count']
            })
        
        status['date_list'] = date_list
        status['pagination'] = {
            'current_page': page,
            'per_page': per_page,
            'total_dates': paginator.count,
            'total_pages': paginator.num_pages,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next()
        }
        
        return JsonResponse({
            'success': True,
            'status': status
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def collect_data_once(request):
    """
    한 번만 데이터 수집 실행
    """
    try:
        bus_collector.collect_and_save()
        return JsonResponse({
            'success': True,
            'message': '데이터 수집이 완료되었습니다.',
            'status': bus_collector.get_status()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_latest_data(request):
    """
    최신 수집 데이터 조회
    """
    try:
        # 최신 수집 데이터 조회 (버스는 정류소 순번 순으로 정렬)
        latest_collection = BusCollection.objects.filter(
            route_id=bus_collector.route_id
        ).prefetch_related('buses').first()
        
        if not latest_collection:
            return JsonResponse({
                'success': False,
                'message': '수집된 데이터가 없습니다.'
            })
        
        # 버스 데이터 구성 (정류소 순번 순으로 정렬)
        buses_data = []
        sorted_buses = latest_collection.buses.all().order_by('station_seq')
        for bus in sorted_buses:
            buses_data.append({
                'plateNo': bus.plate_no,
                'remainSeatCnt': bus.remain_seat_cnt,
                'stationSeq': bus.station_seq
            })
        
        # 추가 정렬 (숫자 순서로)
        def sort_key(bus):
            try:
                return int(bus['stationSeq'])
            except (ValueError, TypeError):
                return float('inf')
        
        buses_data.sort(key=sort_key)
        
        data = {
            'query_time': latest_collection.query_time.strftime('%Y-%m-%d %H:%M:%S'),
            'buses': buses_data,
            'is_error': latest_collection.is_error,
            'is_skipped': latest_collection.is_skipped
        }
        
        # 해당 날짜의 총 수집 횟수
        total_collections = BusCollection.objects.filter(
            route_id=bus_collector.route_id,
            collection_date=latest_collection.collection_date
        ).count()
        
        return JsonResponse({
            'success': True,
            'data': data,
            'total_collections': total_collections,
            'collection_date': latest_collection.collection_date.strftime('%Y-%m-%d'),
            'last_updated': latest_collection.query_time.isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def download_data_file(request):
    """
    특정 데이터 파일 다운로드
    """
    try:
        filename = request.GET.get('filename')
        if not filename:
            return JsonResponse({
                'success': False,
                'error': '파일명이 필요합니다.'
            }, status=400)
        
        status = bus_collector.get_status()
        data_dir = status['data_directory']
        filepath = os.path.join(data_dir, filename)
        
        if not os.path.exists(filepath):
            return JsonResponse({
                'success': False,
                'error': '파일을 찾을 수 없습니다.'
            }, status=404)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        response = HttpResponse(content, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_daily_list(request):
    """
    일별 수집 데이터 목록 조회
    """
    try:
        # 페이지네이션 파라미터
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        # 날짜별 수집 데이터 조회
        daily_data = BusCollection.objects.filter(
            route_id=bus_collector.route_id
        ).values('collection_date').annotate(
            total_collections=Count('id'),
            successful_collections=Count('id', filter=Q(is_error=False, is_skipped=False)),
            error_collections=Count('id', filter=Q(is_error=True)),
            skipped_collections=Count('id', filter=Q(is_skipped=True)),
            last_collection_time=models.Max('query_time')
        ).order_by('-collection_date')
        
        # 페이지네이션 적용
        paginator = Paginator(daily_data, per_page)
        page_obj = paginator.get_page(page)
        
        daily_list = []
        for item in page_obj:
            daily_list.append({
                'date': item['collection_date'].strftime('%Y-%m-%d'),
                'total_collections': item['total_collections'],
                'successful_collections': item['successful_collections'],
                'error_collections': item['error_collections'],
                'skipped_collections': item['skipped_collections'],
                'last_collection_time': item['last_collection_time'].strftime('%H:%M:%S') if item['last_collection_time'] else 'N/A'
            })
        
        return JsonResponse({
            'success': True,
            'daily_list': daily_list,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_dates': paginator.count,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_date_data(request):
    """
    특정 날짜의 수집 데이터 조회 (팝업용)
    """
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return JsonResponse({
                'success': False,
                'error': '날짜 파라미터가 필요합니다.'
            }, status=400)
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': '올바른 날짜 형식이 아닙니다. (YYYY-MM-DD)'
            }, status=400)
        
        # 페이지네이션 파라미터
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        
        # 해당 날짜의 수집 데이터 조회 (버스는 정류소 순번 순으로 정렬)
        collections = BusCollection.objects.filter(
            route_id=bus_collector.route_id,
            collection_date=target_date
        ).prefetch_related('buses').order_by('-query_time')
        
        # 페이지네이션 적용
        paginator = Paginator(collections, per_page)
        page_obj = paginator.get_page(page)
        
        collections_data = []
        for collection in page_obj:
            # 각 수집 시점의 버스 데이터 (정류소 순번 순으로 정렬)
            buses_data = []
            # 정류소 순번 순으로 정렬된 버스 데이터 가져오기
            sorted_buses = collection.buses.all().order_by('station_seq')
            for bus in sorted_buses:
                buses_data.append({
                    'plateNo': bus.plate_no,
                    'remainSeatCnt': bus.remain_seat_cnt,
                    'stationSeq': bus.station_seq
                })
            
            # 추가 정렬 (숫자 순서로)
            def sort_key(bus):
                try:
                    return int(bus['stationSeq'])
                except (ValueError, TypeError):
                    return float('inf')
            
            buses_data.sort(key=sort_key)
            
            collections_data.append({
                'id': collection.id,
                'query_time': collection.query_time.strftime('%H:%M:%S'),
                'buses': buses_data,
                'bus_count': len(buses_data),
                'is_error': collection.is_error,
                'is_skipped': collection.is_skipped,
                'error_message': collection.error_message,
                'skip_reason': collection.skip_reason
            })
        
        return JsonResponse({
            'success': True,
            'date': date_str,
            'collections': collections_data,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_collections': paginator.count,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def download_all_files(request):
    """
    데이터베이스 파일 다운로드
    """
    try:
        import shutil
        from django.conf import settings
        
        # 데이터베이스 파일 경로 확인
        db_path = settings.DATABASES['default']['NAME']
        
        if not os.path.exists(db_path):
            return JsonResponse({
                'success': False,
                'error': '데이터베이스 파일을 찾을 수 없습니다.'
            }, status=404)
        
        # 임시 복사본 생성 (다운로드 중 데이터베이스 잠금 방지)
        current_date = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        temp_filename = f'bus_data_db_{current_date}.sqlite3'
        temp_path = os.path.join(settings.BASE_DIR, temp_filename)
        
        try:
            # 데이터베이스 파일 복사
            shutil.copy2(db_path, temp_path)
            
            # 파일 읽기
            with open(temp_path, 'rb') as f:
                file_content = f.read()
            
            # 임시 파일 삭제
            os.remove(temp_path)
            
            # 응답 생성
            response = HttpResponse(file_content, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{temp_filename}"'
            response['Content-Length'] = len(file_content)
            
            return response
            
        except Exception as copy_error:
            # 임시 파일이 생성되었다면 삭제
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise copy_error
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'데이터베이스 파일 다운로드 실패: {str(e)}'
        }, status=500)



