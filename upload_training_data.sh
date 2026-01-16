#!/bin/bash
# Upload training data to mARB 2.0 API
# This script uploads the generated mock training data

set -e

echo "Uploading training data to mARB 2.0..."
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "❌ Server is not running on http://localhost:8000"
    echo ""
    echo "Please start the server first:"
    echo "  source venv/bin/activate"
    echo "  python run.py"
    echo ""
    exit 1
fi

echo "✅ Server is running"
echo ""

# Check if files exist
if [ ! -f "samples/training/training_837_claims.edi" ]; then
    echo "❌ Claims file not found: samples/training/training_837_claims.edi"
    echo "   Generate it first: python ml/training/generate_training_data.py --episodes 200"
    exit 1
fi

if [ ! -f "samples/training/training_835_remittances.edi" ]; then
    echo "❌ Remittances file not found: samples/training/training_835_remittances.edi"
    echo "   Generate it first: python ml/training/generate_training_data.py --episodes 200"
    exit 1
fi

echo "Uploading 837 claims file..."
RESPONSE1=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/claims/upload -F "file=@samples/training/training_837_claims.edi")
HTTP_CODE1=$(echo "$RESPONSE1" | tail -n1)
BODY1=$(echo "$RESPONSE1" | head -n-1)

if [ "$HTTP_CODE1" = "200" ] || [ "$HTTP_CODE1" = "202" ]; then
    echo "✅ Claims uploaded successfully (HTTP $HTTP_CODE1)"
else
    echo "❌ Failed to upload claims (HTTP $HTTP_CODE1)"
    echo "$BODY1"
    exit 1
fi

echo ""
echo "Uploading 835 remittances file..."
RESPONSE2=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/remits/upload -F "file=@samples/training/training_835_remittances.edi")
HTTP_CODE2=$(echo "$RESPONSE2" | tail -n1)
BODY2=$(echo "$RESPONSE2" | head -n-1)

if [ "$HTTP_CODE2" = "200" ] || [ "$HTTP_CODE2" = "202" ]; then
    echo "✅ Remittances uploaded successfully (HTTP $HTTP_CODE2)"
else
    echo "❌ Failed to upload remittances (HTTP $HTTP_CODE2)"
    echo "$BODY2"
    exit 1
fi

echo ""
echo "✅ All training data uploaded successfully!"
echo ""
echo "Next steps:"
echo "  1. Check data: python ml/training/check_historical_data.py"
echo "  2. Train model: python ml/training/train_models.py --start-date 2024-01-01 --end-date 2024-12-31"

