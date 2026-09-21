FROM docker.io/library/golang:1.27.1-bookworm@sha256:69a7b9788769bec032d238959b61854e9ae87f57be9029ec04e9885fabf99195 AS builder

WORKDIR /app

COPY go.mod go.sum ./
COPY cmd ./cmd
COPY internal ./internal

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/stockchartsalerts ./cmd/stockchartsalerts

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:b9e0bf16ff3afe7f1a45451128a091af54065baaff80aec27ac18de7aca27253

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

# Copy CA certificates from builder for TLS verification
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Copy the compiled binary
COPY --from=builder /out/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
