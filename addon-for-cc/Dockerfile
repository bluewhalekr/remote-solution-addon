FROM python:3.9-alpine

WORKDIR /app

# 필요한 패키지 설치
RUN apk add --no-cache gcc musl-dev
RUN pip install requests \
                paho-mqtt \
                aiohttp \
                getmac

# 애플리케이션 파일 복사
COPY app/ .

# 실행 스크립트 복사 및 권한 설정
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]