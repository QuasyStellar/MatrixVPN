FROM python:3.10.12
WORKDIR /backend

RUN apt-get update && \
    apt-get install -y \
    xvfb \
    libfontconfig \
    libjpeg62-turbo \
    libxrender1

RUN mkdir "tmp"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt update && apt install -y --no-install-recommends locales; rm -rf /var/lib/apt/lists/*; sed -i '/^#.* ru_RU.UTF-8 /s/^#//' /etc/locale.gen; locale-gen
