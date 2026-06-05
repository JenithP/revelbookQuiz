# 요한계시록 암기 훈련 봇 - Fly.io 배포용
# Render의 .python-version(3.12.7)과 동일하게 맞춤
FROM python:3.12.7-slim

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 봇 코드 복사
COPY . .

# 헬스서버 포트 (fly.toml의 internal_port와 일치)
ENV PORT=8080

# polling 봇 실행
CMD ["python", "main.py"]
