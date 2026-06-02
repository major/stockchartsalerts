.PHONY: all fmt fmt-fix clippy test build audit

all: fmt clippy test build

fmt:
	cargo fmt --check

fmt-fix:
	cargo fmt

clippy:
	cargo clippy --all-targets --locked -- -D warnings

test:
	cargo test --locked

build:
	cargo build --locked

audit:
	cargo audit
