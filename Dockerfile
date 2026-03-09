FROM python:3.12-slim

WORKDIR /app

# Copy source first for better caching
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8888

# Run web server by default
CMD ["pg-server"]
