"""Dependency-free YouTube collection pilot; credentials stay server-side."""
import argparse
import calendar
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

HANDLES = ['@bunseok_zwa', '@edward98777', '@공여사들']


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def cutoff(now):
    month_index = now.year * 12 + now.month - 1 - 3
    year, month = divmod(month_index, 12)
    month += 1
    return now.replace(year=year, month=month,
                       day=min(now.day, calendar.monthrange(year, month)[1]))


def seconds(value):
    match = re.fullmatch(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value)
    return sum(int(n or 0) * unit for n, unit in zip(match.groups(), [86400, 3600, 60, 1])) if match else None


class API:
    def __init__(self, key, limit=200):
        self.key, self.limit, self.calls = key, limit, 0

    def get(self, resource, **params):
        if self.calls >= self.limit:
            raise RuntimeError('요청 한도 도달')
        self.calls += 1
        url = 'https://www.googleapis.com/youtube/v3/' + resource + '?' + urlencode(dict(params, key=self.key))
        try:
            with urlopen(url, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            # Never print request URLs, headers, or raw exceptions containing keys.
            raise RuntimeError(f'YouTube API 응답 오류 HTTP {error.code}') from None
        except (URLError, TimeoutError, ValueError):
            raise RuntimeError('YouTube 연결 또는 응답 해석 실패') from None


def collect_channel(api, handle, now, max_pages=20):
    result = {'handle': handle, 'videos': [], 'complete': False, 'issues': []}
    try:
        matches = api.get('channels', part='snippet,contentDetails', forHandle=handle).get('items', [])
        if not matches:
            raise RuntimeError('채널을 찾지 못함')
        channel = matches[0]
        result.update(id=channel['id'], title=channel['snippet']['title'])
        playlist = channel['contentDetails']['relatedPlaylists']['uploads']
        token, seen = '', set()
        # Traverse the full uploads list: do not assume playlist ordering is a reliable date boundary.
        for _ in range(max_pages):
            page = api.get('playlistItems', part='contentDetails', playlistId=playlist,
                           maxResults=50, pageToken=token)
            ids = [x['contentDetails']['videoId'] for x in page.get('items', [])]
            ids = list(dict.fromkeys(x for x in ids if x not in seen))
            seen.update(ids)
            if ids:
                videos = api.get('videos', part='snippet,statistics,contentDetails,liveStreamingDetails',
                                 id=','.join(ids)).get('items', [])
                if len(videos) != len(ids):
                    result['issues'].append('일부 업로드의 공개 정보 누락: 평균 판정 보류')
                for video in videos:
                    snippet = video['snippet']
                    published = timestamp(snippet['publishedAt'])
                    if not cutoff(now) <= published <= now:
                        continue
                    duration = seconds(video['contentDetails'].get('duration', ''))
                    live = 'liveStreamingDetails' in video or snippet.get('liveBroadcastContent', 'none') != 'none'
                    # Public Data API has no definitive isShorts flag. Short videos need confirmation.
                    kind = 'live' if live else ('long' if duration is not None and duration > 180 else 'unknown')
                    raw_views = video.get('statistics', {}).get('viewCount')
                    result['videos'].append(dict(id=video['id'], title=snippet['title'],
                        published=snippet['publishedAt'], views=int(raw_views) if raw_views is not None else None,
                        duration=duration, kind=kind, format_evidence='라이브 정보' if live else ('180초 초과' if kind == 'long' else '형식 확인 필요'),
                        url='https://www.youtube.com/watch?v=' + video['id'],
                        caption_available=video['contentDetails'].get('caption') == 'true',
                        transcript_status='미수집', comments_status='미수집'))
            token = page.get('nextPageToken', '')
            if not token:
                result['complete'] = not result['issues']
                break
        if token:
            result['issues'].append('업로드 목록 페이지 한도 도달: 전체 평균 판정 보류')
    except RuntimeError as error:
        result['issues'].append(str(error))
    return result


def classify(channel, now, overrides=None):
    overrides = overrides or {}
    for video in channel['videos']:
        if video['id'] in overrides:
            if overrides[video['id']] not in ('long', 'short', 'live'):
                raise ValueError('형식은 long, short, live만 허용됩니다.')
            video['kind'] = overrides[video['id']]
            video['format_evidence'] = '사용자 확인'
        video.update(label='보류', ratio=None, average=None, sample=0, selected=False)
    unresolved = any(v['kind'] == 'unknown' and timestamp(v['published']) <= now - timedelta(days=3) for v in channel['videos'])
    channel['groups'] = []
    for kind, days in [('long', 7), ('short', 3)]:
        population = [v for v in channel['videos'] if v['kind'] == kind and cutoff(now) <= timestamp(v['published']) <= now - timedelta(days=days)]
        valid = channel['complete'] and not unresolved and all(v['views'] is not None for v in population)
        total = sum(v['views'] or 0 for v in population)
        average = total / len(population) if population and valid else None
        channel['groups'].append(dict(kind=kind, count=len(population), average=average,
                                     status='확인 가능' if valid and total else '자료 부족 또는 형식 미확인'))
        for video in population:
            video.update(average=average, sample=len(population))
            if valid and total:
                video['ratio'] = video['views'] * len(population) / total
                # Integer comparisons avoid floating point threshold errors.
                video['label'] = '고성과' if video['views'] * len(population) >= 3 * total else ('저성과' if video['views'] * len(population) * 2 <= total else '일반')
        for label, reverse in [('고성과', True), ('저성과', False)]:
            chosen = sorted((v for v in population if v['label'] == label), key=lambda v: (v['views'], v['id']), reverse=reverse)[:10]
            for video in chosen:
                video['selected'] = True
    return channel


def render(data, output):
    template = Path(__file__).with_name('report.html').read_text(encoding='utf-8')
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    output.write_text(template.replace('/*REPORT_DATA*/null', encoded), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='private-data/pilot')
    parser.add_argument('--snapshot', help='Reclassify saved JSON without API requests')
    parser.add_argument('--formats', help='JSON object mapping video IDs to long/short/live')
    parser.add_argument('--max-pages', type=int, default=20)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.snapshot:
        data = json.loads(Path(args.snapshot).read_text(encoding='utf-8'))
        now = timestamp(data['collected_at'])
    else:
        key = os.environ.get('YOUTUBE_API_KEY')
        if not key:
            parser.exit(2, 'YOUTUBE_API_KEY 비밀 설정이 필요합니다.\n')
        api = API(key)
        data = dict(collected_at=now.isoformat(), cutoff=cutoff(now).isoformat(),
                    channels=[collect_channel(api, h, now, args.max_pages) for h in HANDLES],
                    source='YouTube Data API', keywords=['AI', '자동화', '심리학'])
        data['requests'] = api.calls
    overrides = json.loads(Path(args.formats).read_text(encoding='utf-8')) if args.formats else {}
    for channel in data['channels']:
        classify(channel, now, overrides)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'snapshot.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    render(data, out / 'report.html')
    print('보고서 생성 완료. 요청 수:', data.get('requests', 0))
    print('실제 수집은 영상 기본 정보만 포함. 댓글·자막·AI 분석은 미실행.')


if __name__ == '__main__':
    main()