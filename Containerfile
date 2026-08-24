FROM registry.access.redhat.com/hi/go:1.26-builder@sha256:fe920e4b2428c11499e2307715ab31797f4d7528edfeb4460a3aad5e592628e4 AS builder

WORKDIR /app

COPY go.mod go.sum ./
COPY cmd ./cmd
COPY internal ./internal

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/stockchartsalerts ./cmd/stockchartsalerts

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:7ea0a84c21948360e62f51cf2f087e8a994f3da487d92b3f81536a1c13be63d8

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

# Copy CA certificates from builder for TLS verification
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Copy the compiled binary
COPY --from=builder /out/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
