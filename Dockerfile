FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy source
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["pipeline-guardian"]
CMD ["--help"]
