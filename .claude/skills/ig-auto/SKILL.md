---
name: ig-auto
description: >-
  @uks_camper 자동 운영. 사용자가 영상을 첨부하거나 "영상 올렸어", "이거 릴스로
  만들어", "알아서 해줘"라고 하면 이 스킬 하나로 끝까지 간다: 영상 분석, 지금
  잘 되는 릴스 조사, 기획, 편집(1080x1920 + 한글 자막), 캡션, 미리보기, 승인
  후 인스타 게시, 기록. 사용자는 영상만 올리고 마지막에 "올려" 한 마디만 한다.
---

# ig-auto

사용자는 영상만 올린다. 나머지는 전부 여기서 한다. 사용자에게 방식이나 공식을
설명하지 않는다. 결과물(미리보기 영상, 캡션, 올릴 시간)만 보여주고 "올려"를
기다린다.

## 절대 규칙

- **게시 전 승인은 딱 한 번.** 미리보기 영상 + 캡션 + 계정을 보여주고 사용자가
  "올려/yes/ㅇㅇ"라고 하기 전에는 `vidiq_instagram_publish_reel`을 부르지 않는다.
- **다른 사람 게시물에 자동 댓글 금지.** 공식 API에 없는 기능이고 봇 우회는
  계정 정지 위험. 댓글은 초안만 만든다 (아래 "댓글" 참고).
- **지어내지 않는다.** 시간, 횟수, 장소, 장비는 영상에 보이거나 사용자가 말한
  것만. 모르면 그 자막을 빼거나 질문형으로 바꾼다. 캠핑장 위치는 절대 안 씀.
- **아이 얼굴**은 클로즈업 첫 프레임이나 썸네일로 쓰지 않는다. 뒷모습·손·실루엣 우선.
- 질문은 한 번에 묶어서, 정말 필요할 때만.

## 1. 영상 받기

작업 폴더: `work/YYYY-MM-DD-<짧은이름>/` (git에 안 올라감).

- 채팅 첨부가 디스크에 있으면 그 파일을 `work/.../raw_1.mp4`로 복사.
- 디스크에 없으면 `vidiq_file_upload`로 업로드 창을 띄우고, 받은 uploadId를
  `vidiq_video_upload(uploadId)`에 넣어 videoUrl을 얻은 뒤
  `curl -L -o work/.../raw_1.mp4 "<videoUrl>"`로 내려받는다.
- 여러 개면 raw_1, raw_2 ... 순서대로.

## 2. 영상 보기

```bash
python3 autopilot/analyze.py work/.../raw_1.mp4 work/.../an1
```

- 출력된 `sheet_*.jpg`를 **전부 Read로 직접 본다.** 1초당 1프레임, 타임스탬프 있음.
- 무엇이 몇 초에 있는지 메모: 사람(뒷모습/얼굴), 불, 손, 하늘, 텐트, 움직임 큰 구간.
- `analysis.json`의 scene_cuts(컷 경계), motion_per_second(0.5 미만 = 거의 정지),
  quiet_stretches(조용한 구간), 소리 크기를 편집 지점 고르는 데 쓴다.
- 가로 영상이면 focus_x로 피사체 쪽을 잡는다.

## 3. 무엇이 먹히는지 확인

먼저 읽는다: `.claude/instagram/voice.md`, `feed.md`(시리즈·커버) (말투·금지·채널 방향 — 최우선),
`log.md`(지난 릴스), `plan.md`, 가장 최근 `audit-*.md`, `swipe.md`(있으면).

`swipe.md`가 없거나 7일보다 오래됐으면 갱신한다 (5크레딧):

```
vidiq_instagram_tiktok_outlier_search
  query: 이번 영상의 장면을 한 줄로 (예: "가족 캠핑 모닥불 불멍, 말 없이 현장음")
  embeddingType: concept   (훅만 볼 땐 hook)
  descriptionLanguage: ["ko"], resultsPerPlatform: 8
  audienceQuery: "Culture/Region: South Korea; Global: false; Demographics: 30-40대 주말 캠퍼, 가족·감성 캠핑;"
```

결과가 적으면 descriptionLanguage를 빼고 한 번 더. 상위 2~3개는
`vidiq_watch_shortform_content`로 장면 구성을 본다 (개당 10크레딧, 최대 3개).
`swipe.md`에 날짜, 링크, 배수(outlier), 첫 화면 문구, 구성, 우리 채널에 쓸 점을
적는다. 같은 패턴이 2개 이상일 때만 "패턴"이라고 부른다.

## 4. 기획

voice.md 대본 규칙을 따른다: **말 없음, 현장음 + 화면 자막만.**

- 길이 15~30초. 컷은 2~4초, 같은 화면 4초 넘기지 않기.
- **첫 자막은 질문형** (audit 결과: 질문형 2.4~4.4배, 제목형 0.7배). 0초부터 보이게.
  첫 컷은 움직임 있는 장면 (motion 높은 초).
- 훅 후보 3개를 `ig-reel/hooks.json` 공식으로 만들고 직접 비교해서 하나 고른다.
  (`hookscore.py`, `beats.py`는 영어만 셀 수 있어서 한글엔 쓰지 않는다.)
- 훅이 약속한 답은 영상 중반 전에 보여준다.
- 자막 없는 소리 구간 1~2컷 (장작 소리 등).
- 마지막 자막은 첫 자막 단어 하나를 다시 받아 루프. 요청은 하나 (보통 저장).
- 자막 한 장 15자 안팎, 해요체. 줄바꿈은 `\n`으로 직접 의미 단위로.
- 시리즈 태그(예: 느려터진 주말)는 첫 화면 말고 마지막 자막이나 캡션에.

## 4-1. 커버

`.claude/instagram/feed.md`의 매거진 템플릿:
```bash
python3 autopilot/cover_mag.py work/.../raw_N.mp4 work/.../cover.jpg --series "빨리 차리기" --title "4단계로 끝내는\n캠핑 {크림파스타}" --at <초>
```
plan.json에 `"cover": "cover.jpg"`를 넣으면 영상 앞 2프레임이 커버가 되어 게시 후 자동으로 커버로 잡힌다.
`cover_grid.jpg`(프로필 3:4)도 직접 확인.
자막 스타일은 feed.md "자막 스타일" 표대로 (요리·세팅은 굵게+노란 강조, 느려터진 주말은 차분하게).

## 5. 편집

`work/.../plan.json` 작성 (형식은 `autopilot/edit.py` 맨 위 설명) 후:

```bash
python3 autopilot/edit.py work/.../plan.json
```

확인 — 꼭 직접 본다:

```bash
for t in 0.5 <각 자막 중간 시간들>; do
  ffmpeg -loglevel error -y -ss $t -i work/.../reel.mp4 -frames:v 1 -vf scale=540:-2 work/.../chk_$t.jpg
done
```

이미지를 Read로 보고: 자막이 피사체를 가리는지, 글자가 잘리는지, 첫 프레임에
움직임이 있는지, 얼굴 노출. 문제 있으면 plan.json 고치고 다시 렌더.

## 6. 캡션

**감성 캡션이 기본** (사용자 요청 2026-11-27): 첫 줄 검색어 → 장면을 감각으로 3~4줄(소리·김·빛, 영상에 보이는 것만) →
"준비는 빠르게, 주말은 느리게." → (요리면) 재료·번호 단계 → 저장 요청 하나 → 해시태그.

`ig-caption` 스킬 규칙 + voice.md "캡션 형식"으로 쓴다 (Job A: 영상이 훅).
첫 줄에 검색어, 첫 자막 질문의 답은 캡션에서 미리 말하지 않기, 요청 하나,
해시태그 5개(#느려터진주말 등 시리즈 먼저) + # 없는 검색 키워드.

```bash
python3 .claude/skills/ig-caption/caption.py work/.../caption.txt --keywords "검색어1,검색어2"
```

(해시태그·요청 개수는 한글을 못 세니 무시하고 길이·링크·이모지·첫 줄만 본다.)
`.claude/instagram/drafts/YYYY-MM-DD-<이름>-caption.txt`에도 저장.

## 7. 승인 받기

`SendUserFile`로 `reel.mp4`를 보내고 (display: render), 아래만 짧게 보여준다:

```
릴스 준비됐어요
- 첫 화면: "<첫 자막>"
- 길이: 24초, 컷 7개
- 올릴 시간 추천: <plan.md 기준 요일·시간, 없으면 저녁 8시>
- 캡션: (코드블록)

"올려"라고 하시면 바로 @uks_camper에 올릴게요. 고칠 곳은 말로 알려주세요.
```

사용자가 자리에 없을 수 있으니 `PushNotification`도 보낸다 (도구가 있으면).

## 8. 게시 ("올려" 받은 뒤에만)

1. `vidiq_social_account_list(platform: INSTAGRAM)` → canPublish가 true인 계정.
   없으면 `vidiq_social_account_connect`(INSTAGRAM, oauth) 카드를 띄우고
   "인스타 프로페셔널(크리에이터/비즈니스) 계정으로 로그인해 주세요" 한 줄.
2. `vidiq_video_upload(localFile: {path, sizeBytes(wc -c), contentType: video/mp4})`
   → 돌려준 명령을 Bash로 실행 → 같은 도구에 uploadId로 다시 호출 → videoUrl.
3. `vidiq_instagram_publish_reel(platformAccountId, videoUrl, caption)` →
   inprogress면 안내대로 이어서 호출. PUBLISHED면 링크를 보여준다.
   에러면 재시도하지 말고 그대로 알린다.
4. `log.md`에 한 줄 추가 (날짜, 훅 공식, 첫 자막, 메모: 길이·컷·자막 수·링크).
5. 영상 말고 텍스트 파일만 커밋하고 작업 브랜치에 푸시.

## 댓글 자동 답글: 하지 않음 (사용자 결정 2026-11-27)

내 게시물이든 남의 게시물이든 **댓글·답글을 자동으로 게시하지 않는다.** 사용자가 다시 켜 달라고 하기 전까지
`autopilot/comments.py reply`를 실행하지 않는다. 댓글은 아래 "매일 초안"처럼 초안만 만든다.
(도구는 남겨 둠: 다시 켜면 내용별 규칙은 git 기록의 이전 버전 참고.)

## 댓글 (매일 초안)

- **내 게시물 답글:** `vidiq_ig_profile_reels`로 @uks_camper 최근 릴스 →
  댓글 있는 것만 `vidiq_instagram_comment_list` → `ig-reply` 규칙으로 답글 초안.
  (도구가 작성자 아이디는 안 줘서, 댓글 내용을 인용해 어느 댓글인지 표시.)
- **다른 계정 댓글:** plan.md 참여 계정 + swipe.md 계정의 최신 릴스 3~5개 →
  `ig-comment` 규칙으로 하나씩, 그 게시물을 실제로 본 사람처럼. 링크와 함께.
- 모두 `ig-human` 규칙으로 다듬고 `.claude/instagram/comments/YYYY-MM-DD.md`에
  "복사해서 붙여넣기만 하면 되는" 형태로 저장.

## 주간 기획 (매주)

`ig-plan` 규칙으로 다음 주 계획을 `plan.md`에 덮어쓴다: 릴스 3~4개, 각각
**찍어야 할 장면 목록**(몇 초짜리 어떤 컷), 첫 자막 질문, 올릴 요일·시간.
최근 log.md 성과와 swipe.md를 근거로. 사용자에게는 "이번 주 찍을 것" 목록만
짧게 보낸다.
