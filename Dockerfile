# Use Alpine as the base image for smaller size and potentially fewer vulnerabilities
FROM alpine:latest AS builder


# Set working directory in builder
WORKDIR /app

# Install build dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    gcc \
    musl-dev \
    python3-dev \
    linux-headers

# Create and use a virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install external dependencies in the virtual environment
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy the source code
COPY . .

# Create a non-privileged system user and group for running the application
RUN addgroup -S plana && \
    adduser -S -G plana -s /sbin/nologin -h /app -g "Non-privileged app user" plana

    
# Create a runtime stage to minimize the final image size
FROM alpine:latest AS runtime

# Add image metadata
LABEL org.opencontainers.image.description="Project Plana: The only discord bot you need." \
      org.opencontainers.image.source="https://github.com/Independent-Federal-Investigation-Club/plana-core" \
      org.opencontainers.image.licenses="AGPL 3.0"

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=America/Chicago

# Install Python runtime only (no build tools)
RUN apk add --no-cache python3 ffmpeg

# Create the same user in the runtime image
RUN addgroup -S plana && \
    adduser -S -G plana -s /sbin/nologin -h /app -g "Non-privileged app user" plana

# Copy virtual environment from builder stage
COPY --from=builder --chown=plana:plana /opt/venv /opt/venv

# Copy the application from the builder stage  
COPY --from=builder --chown=plana:plana /app /app

# Switch to non-root user
USER plana

# add ~/.local/bin to PATH
ENV PATH=/home/plana/.local/bin:$PATH


# Run the application
CMD ["python", "main.py"]
