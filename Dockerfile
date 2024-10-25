FROM python:3.13.0-slim

RUN apt-get update && \
	apt-get install -y --no-install-recommends \
	build-essential \
	apache2 \
	apache2-dev \
	python3-dev \
	default-libmysqlclient-dev \
	supervisor \
	git \
	pkg-config \
	curl \
	locales && \
	rm -rf /var/lib/apt/lists/*

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
	locale-gen

ENV LANG=en_US.UTF-8 \
	LANGUAGE=en_US:en \
	LC_ALL=en_US.UTF-8

WORKDIR /

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install -U --quiet --no-cache-dir pip setuptools && \
	pip install --quiet --no-cache-dir --force-reinstall -r requirements.txt 

ENV MODE=production
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
