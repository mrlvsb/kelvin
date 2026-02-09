#!/bin/bash
set -eux

# Run the image builder to ensure all required images are present
echo "Building evaluator images..."
python /app/evaluator/images/build.py

# Execute the passed command
exec python manage.py "$@"
