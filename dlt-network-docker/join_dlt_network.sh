#!/bin/bash

# Function to handle the selection
handle_selection() {
    case $1 in
        node2)
            NODE_SELECTION="node2"
            ;;
        node3)
            NODE_SELECTION="node3"
            ;;
        node4)
            NODE_SELECTION="node4"
            ;;
        *)
            echo "Invalid selection: $1. Please select node2, node3, or node4."
            exit 1 # Indicates invalid selection
            ;;
    esac
}

# Check if an argument is provided
if [ $# -eq 0 ]; then
    NODE_SELECTION="node2"
else
    handle_selection "$1"
fi

# Proceed with the operation
START_CMD="./${NODE_SELECTION}_start.sh"
DOCKER_CMD="docker run -it --name $NODE_SELECTION --hostname $NODE_SELECTION --network host --rm -v $(pwd)/.env:/dlt-network/.env dlt-node $START_CMD"

echo "Starting $NODE_SELECTION with command $START_CMD..."
eval "$DOCKER_CMD"

echo "$NODE_SELECTION started successfully with command $START_CMD."
