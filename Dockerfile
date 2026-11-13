FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production PORT=8080 MAX_PLAYERS_PER_ROOM=8
WORKDIR /opt/oc2
COPY tools/requirements-native.txt tools/requirements-resources.txt ./tools/
RUN pip install --no-cache-dir -r tools/requirements-native.txt -r tools/requirements-resources.txt
COPY deploy/package.json deploy/package-lock.json ./deploy/
RUN npm ci --omit=dev --prefix deploy
COPY tools/ ./tools/
COPY deploy/ ./deploy/
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --start-period=180s --interval=30s --timeout=5s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:'+process.env.PORT+'/health').then(r=>{if(!r.ok)process.exit(1);return r.json()}).then(j=>{if(!j.ok)process.exit(1)}).catch(()=>process.exit(1))"
ENTRYPOINT ["/opt/venv/bin/python", "/opt/oc2/deploy/bootstrap.py"]
