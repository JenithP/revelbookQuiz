// ============================================================
// Firebase 설정 — 여기에 본인 프로젝트 설정값 붙여넣기
// Firebase Console → 프로젝트 설정 → 앱 추가 → 웹
// ============================================================
const FIREBASE_CONFIG = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Firestore 컬렉션 구조
// users/{uid} → { name, group, joinedAt, lastLogin }
// scores/{uid}/verses/{verseId} → { stage, attempts, correct, mastered, masteredAt }
// leaderboard → 실시간 집계용 (Cloud Function 또는 클라이언트 업데이트)
