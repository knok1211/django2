from django.db import models
from django.utils import timezone


class BusCollection(models.Model):
    """
    버스 데이터 수집 정보를 저장하는 모델
    """
    route_id = models.CharField(max_length=20, verbose_name="노선 ID")
    query_time = models.DateTimeField(verbose_name="쿼리 시간")
    collection_date = models.DateField(verbose_name="수집 날짜", db_index=True)
    result_code = models.IntegerField(default=0, verbose_name="결과 코드")
    result_message = models.CharField(max_length=200, blank=True, verbose_name="결과 메시지")
    is_error = models.BooleanField(default=False, verbose_name="오류 여부")
    error_message = models.TextField(blank=True, verbose_name="오류 메시지")
    is_skipped = models.BooleanField(default=False, verbose_name="건너뛰기 여부")
    skip_reason = models.CharField(max_length=200, blank=True, verbose_name="건너뛰기 사유")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 시간")
    
    class Meta:
        verbose_name = "버스 수집 정보"
        verbose_name_plural = "버스 수집 정보들"
        ordering = ['-query_time']
        indexes = [
            models.Index(fields=['route_id', 'collection_date']),
            models.Index(fields=['collection_date']),
        ]
    
    def __str__(self):
        return f"{self.route_id} - {self.collection_date} {self.query_time.strftime('%H:%M:%S')}"


class BusData(models.Model):
    """
    개별 버스 데이터를 저장하는 모델
    """
    collection = models.ForeignKey(
        BusCollection, 
        on_delete=models.CASCADE, 
        related_name='buses',
        verbose_name="수집 정보"
    )
    plate_no = models.CharField(max_length=20, verbose_name="차량 번호")
    remain_seat_cnt = models.IntegerField(verbose_name="잔여 좌석 수")
    station_seq = models.CharField(max_length=10, verbose_name="정류소 순번")
    
    class Meta:
        verbose_name = "버스 데이터"
        verbose_name_plural = "버스 데이터들"
        ordering = ['station_seq', 'plate_no']
    
    def __str__(self):
        return f"{self.plate_no} - 잔여좌석: {self.remain_seat_cnt}개"
