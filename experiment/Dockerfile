FROM python:3.12-slim-bookworm
# Supply the reviewed OpenCode release explicitly; do not silently use latest.
ARG OPENCODE_VERSION
RUN test -n "$OPENCODE_VERSION"
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm git ca-certificates iptables \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}"
RUN pip install --no-cache-dir numpy==2.2.4 pandas==2.2.3 pyreadstat==1.3.6 \
    openpyxl==3.1.5 lxml==6.1.1 reportlab==4.4.9 pdfplumber==0.11.9 pypdf==6.10.0
WORKDIR /workspace
CMD ["opencode", "--version"]
