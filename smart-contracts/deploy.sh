#!/bin/bash

host_dir="./"

# Construct the start command based on the selection
START_CMD="./deploy_smart_contract.sh"

# Start a Docker container with the specified configurations
docker run \
  -it \
  --rm \
  --name truffle \
  --hostname truffle \
  --network host \
  -v ${host_dir}:/smart-contracts \
  truffle:latest 

#$START_CMD
