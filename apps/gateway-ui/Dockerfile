# syntax=docker/dockerfile:1
# Multi-stage frontend image: node build -> nginx serve.
#
# NOTE (deviation from contracts/compose-services.md): the build context is the
# REPOSITORY ROOT, not apps/gateway-ui. An Nx app build needs the workspace root
# (node_modules, nx.json, tsconfig.base.json) to resolve React/Vite and the
# project graph, so the compose service sets `context: .` with this Dockerfile
# path. Documented limitation — see README.

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS builder
WORKDIR /workspace

COPY package.json package-lock.json nx.json tsconfig.base.json tsconfig.json ./

# OPTIONAL corporate CA for `npm ci` behind a TLS-inspecting proxy. Supplied as
# the build secret `ca_cert` (CA_CERT_FILE=...); a no-op when absent.
RUN --mount=type=secret,id=ca_cert,required=false \
    sh -eu -c 'if [ -s /run/secrets/ca_cert ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca_cert; fi; npm ci'

COPY apps/gateway-ui ./apps/gateway-ui
# Build is local-only; disable Nx Cloud so no network/TLS is needed here.
ENV NX_NO_CLOUD=true NX_DAEMON=false
RUN npx nx build gateway-ui --skip-nx-cache

# ---- Stage 2: nginx serves the static bundle ----
FROM nginx:1.25-alpine AS runtime
COPY apps/gateway-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/apps/gateway-ui/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
