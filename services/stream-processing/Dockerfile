FROM apache/spark:3.5.3-python3

USER root

# Kafka source for Structured Streaming. Baked into the image (instead of --packages)
# so the container starts without downloading anything. Versions match Spark 3.5.3.
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar /opt/spark/jars/
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar /opt/spark/jars/
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar /opt/spark/jars/
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar /opt/spark/jars/

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && mkdir -p /checkpoints && chown spark:spark /checkpoints

COPY pytest.ini ./
COPY jobs ./jobs
COPY tests ./tests

# pyspark ships inside the image; make it importable for plain `python`/`pytest` too.
ENV PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:/app \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

USER spark

CMD ["/opt/spark/bin/spark-submit", "--master", "local[2]", "--driver-memory", "1g", \
     "--conf", "spark.sql.session.timeZone=UTC", "jobs/stream_main.py"]
