# Rex CRM analytics job (PySpark, local mode). On Databricks the same package runs on a cluster.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
    PYSPARK_SUBMIT_ARGS="--jars /opt/jars/postgresql.jar pyspark-shell"
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
# PostgreSQL JDBC driver from Maven Central, checked against Maven's published SHA-1.
ARG PG_JDBC=42.7.14
RUN mkdir -p /opt/jars \
    && curl -fsSL -o /opt/jars/postgresql.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_JDBC}/postgresql-${PG_JDBC}.jar \
    && echo "$(curl -fsSL https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_JDBC}/postgresql-${PG_JDBC}.jar.sha1)  /opt/jars/postgresql.jar" | sha1sum -c -
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY rex_analytics ./rex_analytics

FROM base AS test
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS job
RUN useradd --uid 10001 --create-home rex && mkdir -p /data/warehouse && chown rex /data/warehouse
USER rex
CMD ["python", "-m", "rex_analytics.job"]
