FROM registry.access.redhat.com/hi/go:1.26-builder@sha256:cd5db2786c71db0d3a1c9a239b8bc18c64ece53b156de0ca6a330939e564d5cc AS builder

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
