# GBIS API 설정
# 실제 사용시에는 공공데이터포털(https://data.go.kr)에서 발급받은 서비스키를 사용하세요

# 공공데이터포털에서 발급받은 GBIS API 서비스키
GBIS_SERVICE_KEY = "KkkVy4H1CGa8fSuj2QR5%2BSHvd1oyW2RO%2FmtyS2Sr6ExzX34N5NoaduPT%2BpIuyWLRcQcIkJGT3OI%2Bu3Mv7mH9qA%3D%3D"

# API 기본 설정
GBIS_API_BASE_URL = "https://apis.data.go.kr/6410000/buslocationservice/v2"
GBIS_API_ENDPOINT = f"{GBIS_API_BASE_URL}/getBusLocationListv2"

# API 요청 타임아웃 (초)
API_TIMEOUT = 10

# 응답 포맷
RESPONSE_FORMAT = "json"

