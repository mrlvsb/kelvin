#!/bin/bash
set -eux

# Run the image builder to ensure all required images are present
# Skip image build if running as scheduler (detected via --with-scheduler arg)
if [[ "$*" != *"--with-scheduler"* ]]; then
    echo "Building evaluator images..."
    python /app/evaluator/images/build.py
fi

# Execute the passed command
exec python manage.py "$@"
