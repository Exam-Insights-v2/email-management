#!/bin/bash

set -eo pipefail

pnpm install

# Use migrate deploy to apply pending migrations without interactive prompts.
pnpm prisma migrate deploy

pnpm run dev:docker
