#!/bin/bash
# Bitcoin Analysis Stack - Status Check Script

set -e

echo "📊 Bitcoin Analysis Stack Status"
echo "================================"
echo ""

# Check if services are running
echo "🔍 Service Status:"
docker-compose ps
echo ""

# Bitcoin sync status
echo "⛓️  Bitcoin Blockchain Sync:"
if docker-compose ps bitcoin | grep -q "Up"; then
    docker-compose exec -T bitcoin bitcoin-cli getblockchaininfo | grep -E '(chain|blocks|headers|verificationprogress|size_on_disk)' || echo "   Bitcoin RPC not ready yet"
else
    echo "   ❌ Bitcoin service not running"
fi
echo ""

# Neo4j status
echo "📊 Neo4j Graph Database:"
if docker-compose ps neo4j | grep -q "Up"; then
    docker-compose exec -T neo4j cypher-shell -u neo4j -p bitcoin123 "MATCH (n) RETURN count(n) as nodes, 'Nodes in graph' as label UNION ALL MATCH ()-[r]->() RETURN count(r) as nodes, 'Relationships' as label;" 2>/dev/null || echo "   Neo4j not ready yet"
else
    echo "   ❌ Neo4j service not running"
fi
echo ""

# GraphQL API
echo "🌐 GraphQL API:"
if docker-compose ps graphql | grep -q "Up"; then
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "   GraphQL API not ready yet"
else
    echo "   ❌ GraphQL service not running"
fi
echo ""

# Disk usage
echo "💾 Docker Volume Disk Usage:"
docker system df -v | grep bitcoin-analysis-stack || echo "   No volumes found"
echo ""

echo "================================"
echo "📝 For detailed logs: docker-compose logs -f [service]"
echo "   Available services: bitcoin, neo4j, graphql, btc-importer, jupyter, electrs"
echo ""
