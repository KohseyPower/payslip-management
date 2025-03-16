# Use Ubuntu image
FROM ubuntu:24.04

# Install curl and cron
RUN apt-get update && apt-get install -y curl cron

# Installer uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Define the working directory
WORKDIR /app

# Copy the source files
COPY pyproject.toml /app/
COPY edoc_retriever.py /app/
COPY google_info.json /app/

RUN echo "0 * * * * cd /app/ && /root/.local/bin/uv run edoc_retriever.py > /tmp/cronlog.txt 2>&1" | crontab -

CMD ["cron", "-f"]
