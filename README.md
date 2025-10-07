# Bitcoin Analysis Stack

A comprehensive Docker-based Bitcoin blockchain analysis platform combining Bitcoin Core, Neo4j graph database, GraphQL API, and Python analysis tools for private blockchain research and chain analysis.

## 🎯 Features

- **Bitcoin Core Full Node**: Private node with minimal network participation
- **Neo4j Graph Database**: Transaction graph for network analysis
- **GraphQL API**: Unified query interface for Bitcoin + Neo4j data
- **Electrs**: Fast UTXO indexing and queries
- **Jupyter Notebooks**: Interactive analysis environment
- **Python Analysis Tools**: Pre-built scripts for address clustering and chain analysis

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────┐
│  Bitcoin Core   │◄────►│  Neo4j Graph │◄────►│  GraphQL    │
│  (Full Node)    │      │  (Tx Graph)  │      │  API Server │
└────────┬────────┘      └──────────────┘      └──────┬──────┘
         │                                              │
         │               ┌──────────────┐              │
         └──────────────►│   Electrs    │              │
                         │  (Indexer)   │              │
                         └──────────────┘              │
                                                        │
         ┌──────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│         Jupyter Notebooks + Analysis Tools      │
│  • Address clustering • UTXO tracking           │
│  • Transaction flow   • Network visualization   │
└─────────────────────────────────────────────────┘
```

## 📋 Requirements

- **Docker** & **Docker Compose** (v2.0+)
- **Storage**: ~2TB for full setup (600GB Bitcoin + 600GB Electrs + 600GB Neo4j + 200GB overhead)
- **RAM**: 16GB minimum, 32GB recommended
- **CPU**: 4+ cores recommended

## 🚀 Quick Start

### 1. Clone & Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd bitcoin-analysis-stack

# Copy environment template
cp .env.example .env

# Edit configuration (change passwords!)
nano .env
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Wait for Initial Sync

Bitcoin Core will take **several days** to sync the entire blockchain. Monitor progress:

```bash
# Check Bitcoin sync status
docker-compose exec bitcoin bitcoin-cli getblockchaininfo

# Check Neo4j importer progress
docker-compose logs -f btc-importer
```

### 4. Access Interfaces

Once synced, access:

- **Jupyter Notebooks**: http://localhost:8888
- **Neo4j Browser**: http://localhost:7474 (login: neo4j/bitcoin123)
- **GraphQL Playground**: http://localhost:8000/graphql

## 📊 Usage Examples

### Bitcoin Core RPC (Python)

```python
from bitcoinrpc.authproxy import AuthServiceProxy

btc = AuthServiceProxy("http://btcuser:btcpass@localhost:8332")

# Get blockchain info
info = btc.getblockchaininfo()
print(f"Blocks: {info['blocks']}")

# Get specific transaction
tx = btc.getrawtransaction("txid_here", True)
```

### Neo4j Cypher Queries

```cypher
// Find most active addresses
MATCH (a:Address)<-[r:OUTPUTS_TO]-(t:Transaction)
RETURN a.address, count(t) as tx_count, sum(r.value) as total_received
ORDER BY tx_count DESC
LIMIT 10;

// Find transaction path between addresses
MATCH path = shortestPath(
  (a1:Address {address: 'addr1'})-[:OUTPUTS_TO|SPENT_IN*..10]-(a2:Address {address: 'addr2'})
)
RETURN path;

// Cluster addresses by common spending
MATCH (a1:Address)<-[:OUTPUTS_TO]-(:Transaction)-[:SPENT_IN]->
      (:Transaction)-[:OUTPUTS_TO]->(a2:Address)
WHERE a1 <> a2
RETURN a1.address, collect(DISTINCT a2.address) as cluster
LIMIT 10;
```

### GraphQL Queries

```graphql
query {
  blockchainInfo {
    blocks
    chain
    difficulty
  }

  block(height: 800000) {
    hash
    time
    txCount
  }

  addressInfo(address: "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") {
    balance
    txCount
    firstSeen
  }

  addressConnections(address: "...", limit: 10) {
    fromAddress
    toAddress
    totalAmount
    txCount
  }
}
```

### Python Analysis Scripts

```bash
# Analyze specific address
docker-compose exec jupyter python /home/jovyan/scripts/analyze_address.py 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

# Or from host (if you have dependencies installed)
python scripts/analyze_address.py <address>
```

## 📁 Project Structure

```
bitcoin-analysis-stack/
├── docker-compose.yml          # Main orchestration file
├── .env.example               # Environment template
├── config/
│   └── bitcoin.conf           # Bitcoin Core configuration
├── services/
│   ├── importer/              # Bitcoin → Neo4j importer
│   │   ├── Dockerfile
│   │   ├── importer.py
│   │   └── requirements.txt
│   ├── graphql/               # GraphQL API server
│   │   ├── Dockerfile
│   │   ├── server.py
│   │   └── requirements.txt
│   └── blocksci/              # BlockSci analysis (optional)
│       └── Dockerfile
├── scripts/
│   └── analyze_address.py     # Address analysis tool
├── notebooks/
│   └── 01_getting_started.ipynb  # Tutorial notebook
└── README.md
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Bitcoin RPC
BITCOIN_RPC_USER=btcuser
BITCOIN_RPC_PASSWORD=btcpass

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=bitcoin123
NEO4J_HEAP_SIZE=4G

# Importer
IMPORT_START_BLOCK=0
IMPORT_BATCH_SIZE=100
IMPORT_MODE=continuous
```

### Bitcoin Configuration (config/bitcoin.conf)

Key settings:
- `listen=0` - Don't accept incoming connections
- `maxconnections=8` - Minimal network participation
- `txindex=1` - Required for full transaction lookup
- `prune=0` - Keep full blockchain (change to 550 for pruned)

## 🛠️ Management Commands

### Service Control

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d bitcoin neo4j

# Stop all services
docker-compose down

# Restart service
docker-compose restart btc-importer

# View logs
docker-compose logs -f bitcoin
docker-compose logs -f neo4j
docker-compose logs -f btc-importer
```

### Data Management

```bash
# Backup Bitcoin data
docker-compose stop bitcoin
docker run --rm -v bitcoin-analysis-stack_bitcoin_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/bitcoin-backup.tar.gz /data

# Backup Neo4j data
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/data/neo4j-backup.dump

# Clean up everything (⚠️ DELETES ALL DATA)
docker-compose down -v
```

### Database Access

```bash
# Bitcoin Core CLI
docker-compose exec bitcoin bitcoin-cli getblockcount
docker-compose exec bitcoin bitcoin-cli getpeerinfo

# Neo4j Cypher Shell
docker-compose exec neo4j cypher-shell -u neo4j -p bitcoin123

# GraphQL health check
curl http://localhost:8000/health
```

## 📈 Performance Tuning

### Bitcoin Core

Edit `config/bitcoin.conf`:
```ini
dbcache=4096          # Increase for faster sync (MB)
par=8                 # Parallel script verification threads
maxmempool=1000       # Max mempool size (MB)
```

### Neo4j

Edit `.env`:
```bash
NEO4J_HEAP_SIZE=8G           # Increase for better performance
NEO4J_PAGECACHE=4G           # Cache for graph data
```

### Importer

Edit `.env`:
```bash
IMPORT_BATCH_SIZE=500        # Process more blocks at once
IMPORT_START_BLOCK=800000    # Skip old blocks
```

## 🔍 Analysis Capabilities

### 1. Address Clustering
Identify addresses controlled by the same entity using common-input-ownership heuristic:

```python
from py2neo import Graph
graph = Graph("bolt://localhost:7687", auth=("neo4j", "bitcoin123"))

# Find co-spent addresses (likely same wallet)
query = """
MATCH (a1:Address)<-[:OUTPUTS_TO]-(:Transaction)-[:SPENT_IN]->
      (spend:Transaction)-[:SPENT_IN]->(:Transaction)-[:OUTPUTS_TO]->(a2:Address)
WHERE a1 <> a2
RETURN a1.address, collect(DISTINCT a2.address) as cluster
"""
result = graph.run(query).data()
```

### 2. Transaction Flow Analysis
Track BTC flow through the network:

```python
# Find all transactions between two addresses
query = """
MATCH path = (a1:Address {address: $from})-[:OUTPUTS_TO|SPENT_IN*..10]->(a2:Address {address: $to})
RETURN path
LIMIT 10
"""
```

### 3. UTXO Set Analysis
Query unspent outputs via Electrs or Bitcoin Core RPC.

### 4. Network Visualization
Use NetworkX or Pyvis to visualize transaction graphs (see notebooks).

## ⚠️ Limitations

1. **Initial sync time**: 3-7 days for full Bitcoin blockchain
2. **Storage**: ~2TB required for complete setup (Bitcoin + Electrs + Neo4j)
3. **Neo4j size**: Graph database is similar in size to blockchain (~600GB) due to relationship storage
4. **BlockSci**: Requires manual compilation (Dockerfile is placeholder)
5. **Privacy**: While minimizing network participation, your node still connects to peers

## 🔐 Security Notes

- Change default passwords in `.env`
- Don't expose RPC/GraphQL ports to public internet
- Use firewalls to restrict access
- This is for **research only**, not production use

## 🐛 Troubleshooting

### Bitcoin won't sync
```bash
# Check logs
docker-compose logs bitcoin

# Verify connectivity
docker-compose exec bitcoin bitcoin-cli getpeerinfo

# Increase connections
# Edit config/bitcoin.conf: maxconnections=16
```

### Neo4j out of memory
```bash
# Increase heap size in .env
NEO4J_HEAP_SIZE=8G

# Restart
docker-compose restart neo4j
```

### Importer fails
```bash
# Check if Bitcoin is synced
docker-compose exec bitcoin bitcoin-cli getblockchaininfo

# Check Neo4j connection
docker-compose logs btc-importer

# Restart importer
docker-compose restart btc-importer
```

### GraphQL not responding
```bash
# Check service status
curl http://localhost:8000/health

# Check logs
docker-compose logs graphql

# Restart
docker-compose restart graphql
```

## 📚 Resources

- [Bitcoin Core RPC Documentation](https://developer.bitcoin.org/reference/rpc/)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [GraphQL Documentation](https://graphql.org/learn/)
- [BlockSci Documentation](https://citp.github.io/BlockSci/)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## ⚡ Quick Reference

| Service | Port | Purpose |
|---------|------|---------|
| Bitcoin Core RPC | 8332 | Blockchain queries |
| Neo4j Browser | 7474 | Graph UI |
| Neo4j Bolt | 7687 | Graph queries |
| GraphQL API | 8000 | Unified API |
| Jupyter | 8888 | Analysis notebooks |
| Electrs | 50001 | UTXO indexer |

## 🎓 Learning Path

1. Start with `notebooks/01_getting_started.ipynb`
2. Explore Neo4j Browser with sample queries
3. Try GraphQL Playground queries
4. Run `analyze_address.py` on known addresses
5. Build custom analysis scripts

---

**Note**: This stack is designed for **research and educational purposes**. Use responsibly and respect privacy considerations when analyzing blockchain data.
