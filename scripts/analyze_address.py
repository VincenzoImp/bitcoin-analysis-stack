#!/usr/bin/env python3
"""
Address Analysis Script
Performs comprehensive analysis on a Bitcoin address including:
- Transaction history
- Connected addresses (graph analysis)
- Balance calculations
- Temporal patterns
"""

import os
import sys
import argparse
from bitcoinrpc.authproxy import AuthServiceProxy
from py2neo import Graph
import pandas as pd
from datetime import datetime

def analyze_address(address, neo4j_graph, btc_rpc):
    """Perform comprehensive address analysis"""

    print(f"\n{'='*60}")
    print(f"Address Analysis: {address}")
    print(f"{'='*60}\n")

    # 1. Get basic stats from Neo4j
    query = """
    MATCH (a:Address {address: $address})
    OPTIONAL MATCH (a)<-[r:OUTPUTS_TO]-(t:Transaction)
    RETURN a.address as address,
           a.first_seen as first_seen,
           count(DISTINCT t) as tx_count,
           sum(r.value) as total_received
    """

    result = neo4j_graph.run(query, address=address).data()

    if not result or not result[0]['address']:
        print(f"❌ Address not found in database: {address}")
        return

    stats = result[0]

    print(f"📊 Basic Statistics:")
    print(f"   Total Transactions: {stats['tx_count']}")
    print(f"   Total Received: {stats['total_received']:.8f} BTC")

    if stats['first_seen']:
        first_seen_dt = datetime.fromtimestamp(stats['first_seen'])
        print(f"   First Seen: {first_seen_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # 2. Find connected addresses
    print(f"\n🔗 Top 10 Connected Addresses:")
    conn_query = """
    MATCH (a1:Address {address: $address})<-[:OUTPUTS_TO]-(t:Transaction)-[:OUTPUTS_TO]->(a2:Address)
    WHERE a1 <> a2
    RETURN a2.address as connected_address,
           count(t) as connection_count,
           sum(t.value) as total_amount
    ORDER BY connection_count DESC
    LIMIT 10
    """

    connections = neo4j_graph.run(conn_query, address=address).data()

    if connections:
        for i, conn in enumerate(connections, 1):
            print(f"   {i}. {conn['connected_address']}")
            print(f"      Transactions: {conn['connection_count']}")
            print(f"      Total: {conn['total_amount']:.8f} BTC")
    else:
        print("   No connections found")

    # 3. Transaction timeline
    print(f"\n📈 Recent Transactions:")
    tx_query = """
    MATCH (a:Address {address: $address})<-[r:OUTPUTS_TO]-(t:Transaction)
    RETURN t.txid as txid, t.time as time, r.value as value
    ORDER BY t.time DESC
    LIMIT 5
    """

    transactions = neo4j_graph.run(tx_query, address=address).data()

    if transactions:
        for tx in transactions:
            tx_time = datetime.fromtimestamp(tx['time']) if tx['time'] else 'Unknown'
            print(f"   TX: {tx['txid'][:16]}...")
            print(f"      Time: {tx_time}")
            print(f"      Value: {tx['value']:.8f} BTC")
    else:
        print("   No recent transactions")

    # 4. Clustering analysis
    print(f"\n🎯 Clustering Analysis:")
    cluster_query = """
    MATCH (a:Address {address: $address})<-[:OUTPUTS_TO]-(:Transaction)-[:SPENT_IN]->
          (:Transaction)-[:OUTPUTS_TO]->(related:Address)
    WHERE a <> related
    RETURN count(DISTINCT related) as cluster_size
    """

    cluster_result = neo4j_graph.run(cluster_query, address=address).data()
    if cluster_result and cluster_result[0]['cluster_size']:
        print(f"   Estimated cluster size: {cluster_result[0]['cluster_size']} addresses")
    else:
        print("   Insufficient data for clustering")

    print(f"\n{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description='Analyze a Bitcoin address')
    parser.add_argument('address', help='Bitcoin address to analyze')
    parser.add_argument('--neo4j-uri', default=os.getenv('NEO4J_URI', 'bolt://localhost:7687'))
    parser.add_argument('--neo4j-user', default=os.getenv('NEO4J_USER', 'neo4j'))
    parser.add_argument('--neo4j-pass', default=os.getenv('NEO4J_PASSWORD', 'bitcoin123'))
    parser.add_argument('--btc-rpc', default=None, help='Bitcoin RPC URL')

    args = parser.parse_args()

    # Connect to Neo4j
    print("Connecting to Neo4j...")
    graph = Graph(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_pass))

    # Connect to Bitcoin Core (optional)
    btc = None
    if args.btc_rpc:
        print("Connecting to Bitcoin Core...")
        btc = AuthServiceProxy(args.btc_rpc)

    # Perform analysis
    analyze_address(args.address, graph, btc)

if __name__ == '__main__':
    main()
