# 말씀 암기 훈련 앱 — 배포 가이드

## 파일 구조
```
index.html      → 로그인 / 가입
app.html        → 4단계 암기 학습
dashboard.html  → 내 현황 + 전체 순위
netlify.toml    → Netlify 설정
```

---

## 1단계: Firebase 설정

1. https://console.firebase.google.com 접속
2. 새 프로젝트 생성 (예: revelation-memory)
3. **Firestore Database** 생성 → "프로덕션 모드"로 시작
4. **프로젝트 설정** → **앱 추가** → 웹(</>) 클릭
5. 앱 등록 후 나오는 firebaseConfig 복사

### firebaseConfig 붙여넣기 위치
아래 3개 파일에서 `YOUR_API_KEY` 등을 실제 값으로 교체:
- `index.html` (하단 script 블록)
- `app.html` (하단 script 블록)
- `dashboard.html` (하단 script 블록)

```js
const FIREBASE_CONFIG = {
  apiKey: "실제값",
  authDomain: "실제값.firebaseapp.com",
  projectId: "실제값",
  ...
};
```

---

## 2단계: Firestore 보안 규칙

Firebase Console → Firestore → 규칙 탭에 붙여넣기:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid} {
      allow read, write: if true;
    }
    match /scores/{uid} {
      allow read, write: if true;
    }
    match /leaderboard/{uid} {
      allow read: if true;
      allow write: if true;
    }
  }
}
```

> ⚠️ 프로덕션에서는 인증 후 본인 데이터만 쓰도록 강화하세요

---

## 3단계: Netlify 배포

### 방법 A — 드래그 앤 드롭 (가장 쉬움)
1. https://netlify.com 로그인
2. Sites → "drag and drop your site folder here"
3. 폴더 전체 드래그

### 방법 B — GitHub 연동
```bash
git init
git add .
git commit -m "first commit"
git push origin main
```
Netlify에서 GitHub 저장소 연결

---

## 4단계: 텔레그램 봇 (선택)

텔레그램 봇은 별도 서버(예: Python + python-telegram-bot) 또는
Netlify Functions로 구현 가능합니다.

기본 기능:
- `/계1장` → 계 1장 1~3절 구절 전송
- `/점수` → 해당 유저 점수 조회 (이름 입력 요청)
- `/순위` → 상위 10명 리더보드

---

## Firestore 데이터 구조

```
users/{uid}
  name: "홍길동"
  group: "청년부"
  joinedAt: Timestamp
  lastLogin: Timestamp

scores/{uid}
  rev1: { stage: 4, mastered: true, attempts: 8, correct: 6, masteredAt: "..." }
  rev7: { stage: 2, mastered: false, attempts: 3, correct: 2 }
  ...

leaderboard/{uid}
  name: "홍길동"
  group: "청년부"
  totalMastered: 3
  accuracy: 75
  updatedAt: Timestamp
```
