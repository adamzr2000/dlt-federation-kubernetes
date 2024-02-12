#!/bin/bash

# Execute the geth init command to initialize the data directory with genesis.json
output=$(geth init --datadir node4 genesis.json)
echo "$output"

# Read environment variables from .env file
source .env

# Define the command
command="geth --identity "node4" --syncmode "full" --ws --ws.addr $IP_NODE_4 --ws.port $WS_PORT_NODE_4 --datadir node4 --port $ETH_PORT_NODE_4 --bootnodes $BOOTNODE_URL --ws.api "eth,net,web3,personal,miner,admin" --networkid 1234 --nat "any" --allow-insecure-unlock --authrpc.port $RPC_PORT_NODE_4 --ipcdisable --unlock $ETHERBASE_NODE_4 --password password.txt --mine --snapshot=false --miner.etherbase $ETHERBASE_NODE_4" 

# Execute the command
eval $command

