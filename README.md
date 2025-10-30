# 경기도 버스 좌석수 조회 시스템

이 프로젝트는 경기도 버스 정보 시스템(GBIS) API를 활용하여 버스의 잔여 좌석수를 조회하는 Django 웹 애플리케이션입니다.


## 중요 사항

⚠️ **서비스키 설정 필요**: 실제 사용을 위해서는 공공데이터포털(https://data.go.kr)에서 GBIS API 서비스키를 발급받아 `bus_info/views.py` 파일의 `service_key` 변수를 실제 키로 교체해야 합니다.


## 참고 자료

- [GBIS 공유서비스](https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusLocation)
- [공공데이터포털](https://data.go.kr)
