ARG AIRFLOW_IMAGE_NAME=apache/airflow:slim-3.3.1-python3.14
FROM ${AIRFLOW_IMAGE_NAME}
ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.14

USER airflow
RUN pip install --no-cache-dir \
    "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
