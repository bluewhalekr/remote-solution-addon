FROM python:3.9-alpine

WORKDIR /app

RUN apk add --no-cache gcc musl-dev
RUN pip install requests \
                paho-mqtt \
                aiohttp \
                getmac

COPY . .

RUN chmod a+x run.sh

CMD ["sh", "run.sh" ]