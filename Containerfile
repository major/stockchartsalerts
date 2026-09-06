FROM registry.access.redhat.com/hi/go:1.26-builder@sha256:1e72a4a0881a8fb25e5f38434d55884318af37941a494d2cc44f5ba0c954e677 AS builder

WORKDIR /app

COPY go.mod go.sum ./
COPY cmd ./cmd
COPY internal ./internal

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/stockchartsalerts ./cmd/stockchartsalerts

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:114d1b0ba3e2a1fc4ef42f8c1a388c6a7a2f8dca42a38a433464d0edb15bd56b

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

# Copy CA certificates from builder for TLS verification
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Copy the compiled binary
COPY --from=builder /out/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
