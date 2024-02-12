#!/bin/bash

# Execute the geth init command to initialize the data directory with genesis.json
output=$(geth init --datadir node1 genesis.json)
echo "$output"

# Read environment variables from .env file
source .env

# Define the command
command="geth --identity "node1" --syncmode "full" --ws --ws.addr $IP_NODE_1  --ws.port $WS_PORT_NODE_1 --datadir node1 --port $ETH_PORT_NODE_1 --bootnodes $BOOTNODE_URL --ws.api "eth,net,web3,personal,miner,admin" --networkid 1234 --nat "any" --allow-insecure-unlock --authrpc.port $RPC_PORT_NODE_1 --ipcdisable --unlock $ETHERBASE_NODE_1 --password password.txt --mine --snapshot=false --miner.etherbase $ETHERBASE_NODE_1" 

# Execute the command
eval $command

