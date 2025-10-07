#!/usr/bin/env python3
"""
Bitcoin to Neo4j Importer
Imports blockchain data from Bitcoin Core into Neo4j graph database
"""

import os
import sys
import time
import json
from typing import Dict, List, Optional
from bitcoinrpc.authproxy import AuthServiceProxy
from neo4j import GraphDatabase
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BitcoinNeo4jImporter:
    def __init__(self):
        # Bitcoin RPC connection
        self.btc_rpc_host = os.getenv('BITCOIN_RPC_HOST', 'bitcoin')
        self.btc_rpc_port = os.getenv('BITCOIN_RPC_PORT', '8332')
        self.btc_rpc_user = os.getenv('BITCOIN_RPC_USER', 'btcuser')
        self.btc_rpc_password = os.getenv('BITCOIN_RPC_PASSWORD', 'btcpass')

        # Neo4j connection
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD', 'bitcoin123')

        # Import settings
        self.start_block = int(os.getenv('IMPORT_START_BLOCK', '0'))
        self.batch_size = int(os.getenv('IMPORT_BATCH_SIZE', '100'))
        self.import_mode = os.getenv('IMPORT_MODE', 'continuous')

        # State file
        self.state_file = '/app/state/import_state.json'

        # Initialize connections
        self.btc = None
        self.neo4j = None

    def connect(self):
        """Establish connections to Bitcoin Core and Neo4j"""
        logger.info("Connecting to Bitcoin Core...")
        rpc_url = f"http://{self.btc_rpc_user}:{self.btc_rpc_password}@{self.btc_rpc_host}:{self.btc_rpc_port}"
        self.btc = AuthServiceProxy(rpc_url)

        # Test connection
        info = self.btc.getblockchaininfo()
        logger.info(f"Connected to Bitcoin Core - Chain: {info['chain']}, Blocks: {info['blocks']}")

        logger.info("Connecting to Neo4j...")
        self.neo4j = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        # Test connection
        with self.neo4j.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        logger.info("Connected to Neo4j")

    def setup_schema(self):
        """Create Neo4j indexes and constraints"""
        logger.info("Setting up Neo4j schema...")

        with self.neo4j.session() as session:
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Block) REQUIRE b.hash IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaction) REQUIRE t.txid IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Address) REQUIRE a.address IS UNIQUE",
            ]

            for constraint in constraints:
                session.run(constraint)

            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (b:Block) ON (b.height)",
                "CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.block_hash)",
                "CREATE INDEX IF NOT EXISTS FOR (a:Address) ON (a.first_seen)",
            ]

            for index in indexes:
                session.run(index)

        logger.info("Schema setup complete")

    def load_state(self) -> int:
        """Load last imported block from state file"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                return state.get('last_block', self.start_block)
        return self.start_block

    def save_state(self, block_height: int):
        """Save current import state"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({'last_block': block_height, 'timestamp': time.time()}, f)

    def import_block(self, block_height: int):
        """Import a single block into Neo4j"""
        block_hash = self.btc.getblockhash(block_height)
        block = self.btc.getblock(block_hash, 2)  # Verbosity 2 includes tx details

        with self.neo4j.session() as session:
            # Import block
            session.run("""
                MERGE (b:Block {hash: $hash})
                SET b.height = $height,
                    b.time = $time,
                    b.size = $size,
                    b.tx_count = $tx_count
            """, hash=block['hash'], height=block['height'],
                 time=block['time'], size=block['size'],
                 tx_count=len(block['tx']))

            # Import transactions
            for tx in block['tx']:
                self.import_transaction(session, tx, block)

    def import_transaction(self, session, tx: Dict, block: Dict):
        """Import a transaction and its inputs/outputs"""
        # Create transaction node
        session.run("""
            MERGE (t:Transaction {txid: $txid})
            SET t.block_hash = $block_hash,
                t.time = $time,
                t.size = $size

            WITH t
            MATCH (b:Block {hash: $block_hash})
            MERGE (b)-[:CONTAINS]->(t)
        """, txid=tx['txid'], block_hash=block['hash'],
             time=block['time'], size=tx.get('size', 0))

        # Process inputs
        for vin in tx.get('vin', []):
            if 'coinbase' in vin:
                # Coinbase transaction
                session.run("""
                    MATCH (t:Transaction {txid: $txid})
                    MERGE (cb:Coinbase {id: $coinbase_id})
                    MERGE (cb)-[:INPUTS_TO]->(t)
                """, txid=tx['txid'], coinbase_id=f"{tx['txid']}_coinbase")
            else:
                # Regular input - spending previous output
                prev_txid = vin.get('txid')
                prev_vout = vin.get('vout')
                if prev_txid:
                    session.run("""
                        MATCH (t:Transaction {txid: $txid})
                        MATCH (prev:Transaction {txid: $prev_txid})
                        MERGE (prev)-[s:SPENT_IN {vout: $prev_vout}]->(t)
                    """, txid=tx['txid'], prev_txid=prev_txid, prev_vout=prev_vout)

        # Process outputs
        for vout in tx.get('vout', []):
            addresses = vout.get('scriptPubKey', {}).get('addresses', [])
            value = vout.get('value', 0)
            n = vout.get('n', 0)

            for address in addresses:
                session.run("""
                    MATCH (t:Transaction {txid: $txid})
                    MERGE (a:Address {address: $address})
                    ON CREATE SET a.first_seen = $time

                    MERGE (t)-[r:OUTPUTS_TO {vout: $n}]->(a)
                    SET r.value = $value
                """, txid=tx['txid'], address=address,
                     time=block['time'], n=n, value=value)

    def run(self):
        """Main import loop"""
        logger.info("Starting Bitcoin to Neo4j importer...")

        # Connect to services
        self.connect()

        # Setup schema
        self.setup_schema()

        # Load last state
        current_block = self.load_state()
        logger.info(f"Resuming from block {current_block}")

        # Get blockchain info
        blockchain_info = self.btc.getblockchaininfo()
        total_blocks = blockchain_info['blocks']

        logger.info(f"Total blocks in chain: {total_blocks}")

        try:
            while True:
                if current_block >= total_blocks:
                    if self.import_mode == 'continuous':
                        logger.info("Caught up with blockchain. Waiting for new blocks...")
                        time.sleep(60)
                        blockchain_info = self.btc.getblockchaininfo()
                        total_blocks = blockchain_info['blocks']
                        continue
                    else:
                        logger.info("Import complete!")
                        break

                # Import batch
                end_block = min(current_block + self.batch_size, total_blocks)
                logger.info(f"Importing blocks {current_block} to {end_block}")

                for block_height in tqdm(range(current_block, end_block)):
                    try:
                        self.import_block(block_height)
                        current_block = block_height + 1

                        # Save state every 10 blocks
                        if block_height % 10 == 0:
                            self.save_state(current_block)

                    except Exception as e:
                        logger.error(f"Error importing block {block_height}: {e}")
                        time.sleep(5)
                        continue

                # Save final state
                self.save_state(current_block)

        except KeyboardInterrupt:
            logger.info("Import interrupted by user")
            self.save_state(current_block)
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            self.save_state(current_block)
            raise
        finally:
            if self.neo4j:
                self.neo4j.close()

if __name__ == '__main__':
    importer = BitcoinNeo4jImporter()
    importer.run()
