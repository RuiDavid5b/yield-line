ARG AIRFLOW_IMAGE_NAME=apache/airflow:slim-3.3.1-python3.14
FROM ${AIRFLOW_IMAGE_NAME}
ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.14

USER airflow

COPY --chown=airflow:root constraints-3.14.txt /opt/airflow/constraints.txt

RUN pip install --no-cache-dir \
    "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
    "apache-airflow-providers-fab==3.8.0" \
    "apache-airflow-providers-docker==4.5.9" \
    --constraint /opt/airflow/constraints.txt
    #--constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
