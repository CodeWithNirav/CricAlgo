#!/bin/bash
# Istio VirtualService Weight Replacer
# Usage: ./istio_weight_replacer.sh <canary_weight> <output_file>

set -euo pipefail

CANARY_WEIGHT=${1:-10}
OUTPUT_FILE=${2:-k8s/istio/virtualservice-canary-${CANARY_WEIGHT}.yaml}

# Calculate stable weight
STABLE_WEIGHT=$((100 - CANARY_WEIGHT))

# Create output directory if it doesn't exist
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Replace placeholders in template
sed -e "s/WEIGHT_PLACEHOLDER/$CANARY_WEIGHT/g" \
    -e "s/WEIGHT_STABLE_PLACEHOLDER/$STABLE_WEIGHT/g" \
    -e "s/WEIGHT_CANARY_PLACEHOLDER/$CANARY_WEIGHT/g" \
    k8s/istio/virtualservice-canary-template.yaml > "$OUTPUT_FILE"

echo "Generated Istio VirtualService with $CANARY_WEIGHT% canary traffic: $OUTPUT_FILE"
