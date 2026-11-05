# 수집 시험 사용법

이 시험은 GitHub Actions에서 수동으로 실행한다. 앱 배포와 Supabase 연결은 아직 하지 않는다.

1. 저장소 Settings → Secrets and variables → Actions → New repository secret.
2. Name은 YOUTUBE_API_KEY, Secret에는 기존 YouTube API 키를 직접 입력한다.
3. Actions → YouTube collection pilot → Run workflow.
4. 완료된 실행의 Artifacts에서 youtube-pilot-report를 내려받아 압축을 풀고 report.html을 브라우저로 연다.

공개 저장소의 실행 로그와 결과 파일은 기밀 보관 공간이 아니다. 이 시험은 공개 영상 메타데이터만 저장한다. 비공개 브랜드 기획·키·사용자 자료는 결과에 넣지 않는다. 결과는 7일 보존한다. 키 원문과 요청 URL을 로그에 출력하지 않는다.

## 범위와 보류
세 참고 채널의 업로드 목록을 조회하고 최근 달력상 3개월을 선택한다. UTC 수집 시각을 기준으로 비교한다. 채널당 최대 20페이지, 전체 요청 최대 200회. 전체 업로드 목록 순서를 가정하지 않아 목록 끝까지 확인하며, 한도 또는 누락으로 완결성을 확인하지 못하면 성과 판정을 보류한다.

API의 자막 존재 표시는 자막 추출 성공이 아니다. 댓글·자막·Gemini 분석은 이 시험에서 미실행이다. 검색 키워드는 기록만 하며 계정 발굴 검색은 후속 구현이다.

180초 이하 영상을 Shorts로 단정하지 않는다. 긴 영상·Shorts 여부가 미확인인 적격 영상이 있으면 채널 평균 판정을 보류한다. 180초 초과 비라이브 영상만 긴 영상으로 분류한다. 라이브는 초기 시험에서 제외한다.

형식을 직접 확인한 뒤 JSON 파일로 {"VIDEO_ID":"short"} 또는 long/live를 지정하면 기존 데이터를 재수집하지 않고 계산할 수 있다:

    python pilot/collect.py --snapshot path/to/snapshot.json --formats path/to/formats.json

수집 성공과 성과 계산 성공은 별개다. 보류를 고성과·저성과로 강제로 채우지 않는다. 긴 영상 7일, Shorts 3일 제외는 정확한 경과 시간으로 적용한다.

## 검증
    python -m unittest discover -s pilot -v

실제 API 키 연결 전 테스트는 합성 데이터로 수행한다. 실제 수집 성공률·사용량은 실행 결과에서 확인한다. Gemini 키는 아직 등록할 필요가 없다.