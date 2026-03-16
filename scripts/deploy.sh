#!/bin/bash
set -e

echo "=== SMTV Translator — Deploy ==="

# Check .env exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ⚠️  .env created from .env.example"
    echo "  ➡️  Edit .env and set OPENAI_API_KEY, then run this script again."
    echo ""
    exit 1
fi

# Check API key is set
if grep -q "YOUR_KEY_HERE" .env; then
    echo ""
    echo "  ❌ OPENAI_API_KEY not set in .env"
    echo "  ➡️  Edit .env and replace sk-proj-YOUR_KEY_HERE with your real key."
    echo ""
    exit 1
fi

echo "✅ .env OK"
echo "🔨 Building and starting containers..."

docker compose down --remove-orphans
docker compose up --build -d

echo ""
echo "✅ Deploy complete!"
echo "🌐 App is running at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f web      ← live app logs"
echo "  docker compose logs -f worker   ← live worker logs"
echo "  docker compose ps               ← container status"
echo "  docker compose down             ← stop everything"
