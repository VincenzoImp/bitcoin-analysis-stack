#!/bin/bash
# Bitcoin Analysis Stack - Stop Script

set -e

echo "🛑 Stopping Bitcoin Analysis Stack..."
echo ""

# Stop services
docker-compose down

echo ""
echo "✅ All services stopped."
echo ""
echo "📝 To start again: ./start.sh"
echo "⚠️  To remove all data: docker-compose down -v"
echo ""
