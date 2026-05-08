FROM python:3.12.10-slim

WORKDIR /

COPY ../requirements.txt ./app/

#TODO change root as user, security hardening
RUN update-ca-certificates && rm -rf /var/lib/apt/lists/* && \
    groupadd -r appuser && useradd -r -g appuser appuser && \
    pip install --upgrade pip && \ 
    pip install --no-cache-dir -r ./app/requirements.txt

COPY ./invoker_impl/app /app

ENV INVOKER_HOST="127.0.0.1"
ENV INVOKER_PORT="8008"
ENV INVOKER_LOG_DIRECTORY_PATH="./app/log/"
ENV INVOKER_LOG_FILENAME_PATH="${LOG_DIRECTORY_PATH}logger"

EXPOSE 8000


# Using `sh -c` allows us to expand environment variables (HOST and PORT) at runtime,
# which Docker's default CMD/ENTRYPOINT parsing does not support.
# Without `sh -c`, Docker passes "${PORT}" literally to uvicorn, resulting in an invalid value.
# We set default values for HOST and PORT here, which can be overridden by docker-compose
# or runtime environment variables.
ENTRYPOINT ["sh", "-c", "uvicorn app.main:app --host ${INVOKER_HOST} --port ${INVOKER_PORT}"]
