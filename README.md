# 구간별 버스 좌석수 조회 시스템

> 경기도 버스 정보 시스템(GBIS) API를 활용하여 버스의 잔여 좌석수를 수집하는 시스템
> 
> PaaS에 배포하여 자동 수집 및 통계 열람 가능


## 중요 사항

⚠️ **서비스키 설정 필요**: 실제 사용을 위해서는 공공데이터포털(https://data.go.kr)에서 GBIS API 서비스키를 발급받아 `bus_info/views.py` 파일의 `service_key` 변수를 실제 키로 교체해야 합니다.


## 참고 자료

- [GBIS 공유서비스](https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusLocation)
- [공공데이터포털](https://data.go.kr)

## 업데이트

11/01
UTC+9 반영
