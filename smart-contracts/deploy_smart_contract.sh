#!/bin/bash

# Run truffle migrate command and capture the output
output=$(truffle migrate --network node1)

# Print the output
echo "$output"

# Extract the contract address using grep and awk
contract_address=$(echo "$output" | grep "contract address:" | awk '{print $4}')

# Save the contract address in the ../code/ directory
echo "CONTRACT_ADDRESS=$contract_address" > ./.env
echo "Contract Address saved in ./.env file: $contract_address"