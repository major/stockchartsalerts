FROM registry.access.redhat.com/hi/go:1.26-builder@sha256:5ac10b4bf9b674a4d617236c4d4d5a6e64b8a6725ebb91e2b7190d6e3575629d AS builder

WORKDIR /app

COPY go.mod go.sum ./
COPY cmd ./cmd
COPY internal ./internal

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/stockchartsalerts ./cmd/stockchartsalerts

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:8792ecb75763b6a2f783e048722d87bcf41b9479dafe4c6d7f275781b91e9196

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

# Copy CA certificates from builder for TLS verification
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Copy the compiled binary
COPY --from=builder /out/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
