FROM registry.access.redhat.com/hi/rust:latest-builder@sha256:ee2a5e7320b0e1e1efa0bebeda1bb0ba4487671d284429e58b8c9f113cbdd795 AS builder

ENV RUSTUP_INIT_SKIP_PATH_CHECK=yes
ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN /bin/bash -o pipefail -c \
        "curl --proto '=https' --tlsv1.2 --silent --show-error --fail https://sh.rustup.rs \
            | sh -s -- -y --profile minimal --default-toolchain 1.96.0" \
    && rustc --version \
    && cargo --version

WORKDIR /app

COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY src ./src

RUN cargo build --locked --release

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:c85f5e01b7f638cb30e75a8a79d06b0cbeb44209945f62572166448bb56b53e9

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

COPY --from=builder /app/target/release/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
