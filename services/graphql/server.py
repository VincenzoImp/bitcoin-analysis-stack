#!/usr/bin/env python3
"""
GraphQL API Server for Bitcoin Blockchain Analysis
Provides unified GraphQL interface for Bitcoin Core RPC and Neo4j graph queries
"""

import os
import strawberry
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from bitcoinrpc.authproxy import AuthServiceProxy
from neo4j import GraphDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BITCOIN_RPC_HOST = os.getenv('BITCOIN_RPC_HOST', 'bitcoin')
BITCOIN_RPC_PORT = os.getenv('BITCOIN_RPC_PORT', '8332')
BITCOIN_RPC_USER = os.getenv('BITCOIN_RPC_USER', 'btcuser')
BITCOIN_RPC_PASSWORD = os.getenv('BITCOIN_RPC_PASSWORD', 'btcpass')

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'bitcoin123')

# Initialize connections
btc_rpc_url = f"http://{BITCOIN_RPC_USER}:{BITCOIN_RPC_PASSWORD}@{BITCOIN_RPC_HOST}:{BITCOIN_RPC_PORT}"
btc = AuthServiceProxy(btc_rpc_url)
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# GraphQL Types
@strawberry.type
class BlockInfo:
    hash: str
    height: int
    time: int
    size: int
    tx_count: int
    confirmations: Optional[int] = None

@strawberry.type
class TransactionOutput:
    address: str
    value: float
    n: int

@strawberry.type
class TransactionInput:
    txid: Optional[str] = None
    vout: Optional[int] = None
    coinbase: Optional[str] = None

@strawberry.type
class Transaction:
    txid: str
    size: int
    time: Optional[int] = None
    block_hash: Optional[str] = None
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]

@strawberry.type
class AddressInfo:
    address: str
    balance: float
    tx_count: int
    first_seen: Optional[int] = None

@strawberry.type
class AddressRelation:
    from_address: str
    to_address: str
    total_amount: float
    tx_count: int

@strawberry.type
class NetworkStats:
    blocks: int
    difficulty: float
    hashrate: float
    chain: str
    size_on_disk: int

# Queries
@strawberry.type
class Query:
    @strawberry.field
    def blockchain_info(self) -> NetworkStats:
        """Get blockchain statistics"""
        info = btc.getblockchaininfo()
        return NetworkStats(
            blocks=info['blocks'],
            difficulty=info['difficulty'],
            hashrate=0,  # Would need additional calculation
            chain=info['chain'],
            size_on_disk=info['size_on_disk']
        )

    @strawberry.field
    def block(self, height: Optional[int] = None, hash: Optional[str] = None) -> Optional[BlockInfo]:
        """Get block by height or hash"""
        try:
            if height is not None:
                block_hash = btc.getblockhash(height)
            elif hash is not None:
                block_hash = hash
            else:
                return None

            block = btc.getblock(block_hash, 1)
            return BlockInfo(
                hash=block['hash'],
                height=block['height'],
                time=block['time'],
                size=block['size'],
                tx_count=len(block['tx']),
                confirmations=block.get('confirmations')
            )
        except Exception as e:
            logger.error(f"Error fetching block: {e}")
            return None

    @strawberry.field
    def transaction(self, txid: str) -> Optional[Transaction]:
        """Get transaction by txid"""
        try:
            tx = btc.getrawtransaction(txid, True)

            inputs = []
            for vin in tx.get('vin', []):
                if 'coinbase' in vin:
                    inputs.append(TransactionInput(coinbase=vin['coinbase']))
                else:
                    inputs.append(TransactionInput(
                        txid=vin.get('txid'),
                        vout=vin.get('vout')
                    ))

            outputs = []
            for vout in tx.get('vout', []):
                addresses = vout.get('scriptPubKey', {}).get('addresses', [])
                for addr in addresses:
                    outputs.append(TransactionOutput(
                        address=addr,
                        value=vout['value'],
                        n=vout['n']
                    ))

            return Transaction(
                txid=tx['txid'],
                size=tx['size'],
                time=tx.get('time'),
                block_hash=tx.get('blockhash'),
                inputs=inputs,
                outputs=outputs
            )
        except Exception as e:
            logger.error(f"Error fetching transaction: {e}")
            return None

    @strawberry.field
    def address_info(self, address: str) -> Optional[AddressInfo]:
        """Get address information from Neo4j graph"""
        try:
            with neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (a:Address {address: $address})
                    OPTIONAL MATCH (a)<-[r:OUTPUTS_TO]-()
                    RETURN a.address as address,
                           a.first_seen as first_seen,
                           sum(r.value) as balance,
                           count(r) as tx_count
                """, address=address)

                record = result.single()
                if not record:
                    return None

                return AddressInfo(
                    address=record['address'],
                    balance=record['balance'] or 0,
                    tx_count=record['tx_count'] or 0,
                    first_seen=record['first_seen']
                )
        except Exception as e:
            logger.error(f"Error fetching address info: {e}")
            return None

    @strawberry.field
    def address_connections(self, address: str, limit: int = 10) -> List[AddressRelation]:
        """Find addresses connected to the given address"""
        try:
            with neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (a1:Address {address: $address})<-[r1:OUTPUTS_TO]-(t:Transaction)-[r2:OUTPUTS_TO]->(a2:Address)
                    WHERE a1 <> a2
                    RETURN a1.address as from_address,
                           a2.address as to_address,
                           sum(r2.value) as total_amount,
                           count(DISTINCT t) as tx_count
                    ORDER BY tx_count DESC
                    LIMIT $limit
                """, address=address, limit=limit)

                relations = []
                for record in result:
                    relations.append(AddressRelation(
                        from_address=record['from_address'],
                        to_address=record['to_address'],
                        total_amount=record['total_amount'] or 0,
                        tx_count=record['tx_count']
                    ))
                return relations
        except Exception as e:
            logger.error(f"Error fetching address connections: {e}")
            return []

    @strawberry.field
    def transaction_path(self, from_address: str, to_address: str, max_hops: int = 5) -> List[str]:
        """Find shortest transaction path between two addresses"""
        try:
            with neo4j_driver.session() as session:
                result = session.run("""
                    MATCH path = shortestPath(
                        (a1:Address {address: $from_address})-[:OUTPUTS_TO|SPENT_IN*..%d]-(a2:Address {address: $to_address})
                    )
                    RETURN [node in nodes(path) | node.address] as addresses
                """ % (max_hops * 2), from_address=from_address, to_address=to_address)

                record = result.single()
                if record:
                    return [addr for addr in record['addresses'] if addr]
                return []
        except Exception as e:
            logger.error(f"Error finding transaction path: {e}")
            return []

# Create schema
schema = strawberry.Schema(query=Query)

# Create FastAPI app
app = FastAPI(title="Bitcoin Analysis GraphQL API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GraphQL route
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Check Bitcoin RPC
        btc.getblockcount()

        # Check Neo4j
        with neo4j_driver.session() as session:
            session.run("RETURN 1")

        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/")
async def root():
    return {
        "message": "Bitcoin Analysis GraphQL API",
        "graphql_endpoint": "/graphql",
        "health_endpoint": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('GRAPHQL_PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
