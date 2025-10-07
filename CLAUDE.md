# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Bitcoin Analysis Stack is a Docker-based blockchain analysis platform combining Bitcoin Core, Neo4j graph database, GraphQL API, and Python analysis tools for private blockchain research and chain analysis. It enables transaction flow analysis, address clustering, UTXO tracking, and network visualization.

## Key Commands

### Service Management
```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d bitcoin neo4j

# Stop all services
docker-compose down

# View logs for specific service
docker-compose logs -f bitcoin
docker-compose logs -f neo4j
docker-compose logs -f btc-importer
docker-compose logs -f graphql

# Restart a service
docker-compose restart btc-importer
```

### Bitcoin Core
```bash
# Check blockchain sync status
docker-compose exec bitcoin bitcoin-cli getblockchaininfo

# Get block count
docker-compose exec bitcoin bitcoin-cli getblockcount

# Get peer info
docker-compose exec bitcoin bitcoin-cli getpeerinfo

# Get specific transaction (requires txindex=1)
docker-compose exec bitcoin bitcoin-cli getrawtransaction <txid> true
```

### Neo4j Database
```bash
# Access Cypher shell
docker-compose exec neo4j cypher-shell -u neo4j -p bitcoin123

# Backup Neo4j database
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/data/neo4j-backup.dump
```

### GraphQL API
```bash
# Health check
curl http://localhost:8000/health

# Access playground at http://localhost:8000/graphql
```

### Python Analysis
```bash
# Run analysis scripts from Jupyter container
docker-compose exec jupyter python /home/jovyan/scripts/analyze_address.py <address>
```

## Architecture

The stack consists of 8 interconnected services orchestrated via Docker Compose:

### Core Data Flow
1. **Bitcoin Core** (`bitcoin`) - Full node providing blockchain data via RPC
   - Exposes RPC on port 8332
   - ZMQ feeds on ports 28332-28335 for real-time notifications
   - Configured with `txindex=1` for complete transaction lookup
   - Minimal network participation (`maxconnections=8`, `listen=0`)

2. **BTC-Importer** (`btc-importer`) - Custom Python service
   - Reads blocks from Bitcoin Core RPC (`services/importer/importer.py`)
   - Imports transactions, addresses, and relationships into Neo4j graph
   - Maintains import state in `/app/state/import_state.json`
   - Processes blocks in batches (default 100 blocks)
   - Supports two modes: `continuous` (follows chain tip) or `range` (one-time import)

3. **Neo4j** (`neo4j`) - Graph database storing transaction network
   - Stores blockchain as graph: `Block -> Transaction -> Address` nodes
   - Relationships: `CONTAINS`, `OUTPUTS_TO`, `SPENT_IN`, `INPUTS_TO`
   - Browser UI on port 7474, Bolt protocol on 7687
   - Includes APOC procedures for advanced graph algorithms

4. **GraphQL API** (`graphql`) - Unified query interface
   - Bridges Bitcoin Core RPC and Neo4j queries (`services/graphql/server.py`)
   - Built with Strawberry GraphQL + FastAPI
   - Provides queries for blocks, transactions, address info, address connections, and transaction paths
   - Playground at http://localhost:8000/graphql

### Supporting Services
5. **Electrs** (`electrs`) - Fast UTXO indexer on port 50001
6. **Redis** (`redis`) - Caching layer for GraphQL on port 6379
7. **Jupyter** (`jupyter`) - Interactive analysis environment on port 8888
8. **BlockSci** (`blocksci`) - Optional advanced analysis engine (placeholder, needs manual compilation)

## Configuration

### Environment Variables (.env)
Copy `.env.example` to `.env` and modify:
- `BITCOIN_RPC_USER`, `BITCOIN_RPC_PASSWORD` - Bitcoin Core RPC credentials
- `NEO4J_USER`, `NEO4J_PASSWORD` - Neo4j database credentials
- `NEO4J_HEAP_SIZE`, `NEO4J_PAGECACHE` - Memory allocation for Neo4j
- `IMPORT_START_BLOCK` - Starting block for import (0 for genesis, or higher to skip old blocks)
- `IMPORT_BATCH_SIZE` - Number of blocks processed per batch
- `IMPORT_MODE` - `continuous` or `range`

### Bitcoin Configuration (config/bitcoin.conf)
Critical settings:
- `txindex=1` - **Required** for full transaction lookup
- `prune=0` - Keep full blockchain (change to 550 for pruned mode, but limits analysis)
- `listen=0` - Don't accept incoming connections
- `maxconnections=8` - Minimal network participation
- `dbcache=2048` - Increase for faster sync (can go higher if RAM available)

## Neo4j Graph Schema

The importer creates this schema in Neo4j:

### Node Types
- **Block**: `{hash, height, time, size, tx_count}`
- **Transaction**: `{txid, block_hash, time, size}`
- **Address**: `{address, first_seen}`
- **Coinbase**: `{id}` (for coinbase transactions)

### Relationships
- **CONTAINS**: `(Block)-[:CONTAINS]->(Transaction)`
- **OUTPUTS_TO**: `(Transaction)-[:OUTPUTS_TO {vout, value}]->(Address)`
- **SPENT_IN**: `(Transaction)-[:SPENT_IN {vout}]->(Transaction)` (spending previous output)
- **INPUTS_TO**: `(Coinbase)-[:INPUTS_TO]->(Transaction)` (coinbase inputs)

### Indexes and Constraints
- Unique constraints on `Block.hash`, `Transaction.txid`, `Address.address`
- Indexes on `Block.height`, `Transaction.block_hash`, `Address.first_seen`

## Common Analysis Patterns

### Address Clustering (Common Input Ownership Heuristic)
Addresses used as inputs in the same transaction are likely controlled by the same entity:
```cypher
MATCH (a1:Address)<-[:OUTPUTS_TO]-(:Transaction)-[:SPENT_IN]->
      (spend:Transaction)-[:SPENT_IN]->(:Transaction)-[:OUTPUTS_TO]->(a2:Address)
WHERE a1 <> a2
RETURN a1.address, collect(DISTINCT a2.address) as cluster
```

### Transaction Flow Between Addresses
```cypher
MATCH path = shortestPath(
  (a1:Address {address: 'addr1'})-[:OUTPUTS_TO|SPENT_IN*..10]-(a2:Address {address: 'addr2'})
)
RETURN path
```

### Most Active Addresses
```cypher
MATCH (a:Address)<-[r:OUTPUTS_TO]-(t:Transaction)
RETURN a.address, count(t) as tx_count, sum(r.value) as total_received
ORDER BY tx_count DESC
LIMIT 10
```

## Service Dependencies

When modifying services, understand these dependencies:
- **btc-importer** depends on both `bitcoin` (healthy) and `neo4j` (healthy)
- **graphql** depends on both `bitcoin` and `neo4j`
- **electrs** depends on `bitcoin` (healthy)
- **jupyter** depends on `bitcoin`, `neo4j`, `graphql`
- **blocksci** depends on `bitcoin`

Health checks ensure services wait for dependencies before starting.

## Important Limitations

1. **Initial sync time**: Bitcoin Core takes 3-7 days to sync full blockchain
2. **Storage requirements**: ~1.4TB total (600GB Bitcoin + 600GB Neo4j + 200GB overhead)
3. **Neo4j size**: Graph database grows to ~6x blockchain size due to relationship storage
4. **txindex=1 requirement**: Bitcoin must be configured with full transaction index
5. **prune=0 requirement**: Pruned nodes cannot provide historical block data for import
6. **BlockSci**: Service is placeholder only; requires manual compilation

## Troubleshooting

### Importer Not Processing Blocks
Check these in order:
1. Verify Bitcoin is fully synced: `docker-compose exec bitcoin bitcoin-cli getblockchaininfo`
2. Check importer logs: `docker-compose logs -f btc-importer`
3. Verify Neo4j connection: `docker-compose exec neo4j cypher-shell -u neo4j -p bitcoin123 "RETURN 1"`
4. Check import state file: `/app/state/import_state.json` in btc-importer container

### GraphQL Query Failures
- Ensure both Bitcoin RPC and Neo4j are accessible
- Check health endpoint: `curl http://localhost:8000/health`
- Verify credentials in `.env` match both Bitcoin and Neo4j configurations

### Neo4j Out of Memory
- Increase `NEO4J_HEAP_SIZE` in `.env` (default 4G, increase to 8G or 16G)
- Increase `NEO4J_PAGECACHE` (default 2G, increase to 4G or higher)
- Restart Neo4j: `docker-compose restart neo4j`

### Bitcoin Won't Sync
- Check peer count: `docker-compose exec bitcoin bitcoin-cli getpeerinfo`
- If no peers, increase `maxconnections` in `config/bitcoin.conf`
- Check logs: `docker-compose logs bitcoin`

## Development Notes

### Adding New GraphQL Queries
1. Add Strawberry type definitions in `services/graphql/server.py`
2. Add query method to `Query` class
3. Use `btc` (Bitcoin RPC) or `neo4j_driver` (Neo4j) to fetch data
4. Restart graphql service: `docker-compose restart graphql`

### Adding New Analysis Scripts
1. Place scripts in `scripts/` directory
2. Access from Jupyter container at `/home/jovyan/scripts/`
3. Use environment variables for credentials (already set in Jupyter)

### Modifying Import Logic
Edit `services/importer/importer.py`:
- `import_block()` - Processes individual blocks
- `import_transaction()` - Creates transaction nodes and relationships
- Schema changes require Neo4j constraints/indexes in `setup_schema()`

## Security Considerations

- **Change default passwords** in `.env` before deployment
- **Do not expose ports publicly** - Use firewall or VPN for remote access
- **RPC credentials** in bitcoin.conf should match `.env` settings
- This stack is for **research only**, not production use
