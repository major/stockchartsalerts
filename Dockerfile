FROM docker.io/library/rust:1.96-slim AS builder

WORKDIR /app

COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY src ./src

RUN cargo build --locked --release

FROM docker.io/library/debian:trixie-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive \
        apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin stockchartsalerts

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

COPY --from=builder /app/target/release/stockchartsalerts /usr/local/bin/stockchartsalerts

USER stockchartsalerts

CMD ["/usr/local/bin/stockchartsalerts"]
