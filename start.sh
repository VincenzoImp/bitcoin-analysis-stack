#!/bin/bash
# Bitcoin Analysis Stack - Start Script

set -e

echo "🚀 Starting Bitcoin Analysis Stack..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please review and update passwords!"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to edit .env first..."
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Pull images first
echo "📦 Pulling Docker images (this may take a while)..."
docker-compose pull

# Start services
echo ""
echo "🏗️  Starting services..."
docker-compose up -d

# Wait for services to start
echo ""
echo "⏳ Waiting for services to initialize..."
sleep 10

# Check service health
echo ""
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "✅ Bitcoin Analysis Stack is starting!"
echo ""
echo "📊 Access points:"
echo "   • Jupyter Notebooks: http://localhost:8888"
echo "   • Neo4j Browser:     http://localhost:7474 (neo4j/bitcoin123)"
echo "   • GraphQL API:       http://localhost:8000/graphql"
echo ""
echo "📝 Useful commands:"
echo "   • View logs:         docker-compose logs -f [service]"
echo "   • Stop services:     ./stop.sh"
echo "   • Check sync:        docker-compose exec bitcoin bitcoin-cli getblockchaininfo"
echo ""
echo "⚠️  Note: Bitcoin Core will take several days to sync the blockchain."
echo "   Monitor progress: docker-compose logs -f bitcoin"
echo ""
