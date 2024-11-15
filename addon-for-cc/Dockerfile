FROM python:3.9

RUN apt-get update

WORKDIR /app

#RUN apk add --no-cache gcc musl-dev
RUN pip install requests \
                paho-mqtt \
                aiohttp \
                getmac \
                loguru

COPY . .

RUN chmod a+x run.sh

CMD ["sh", "run.sh" ]