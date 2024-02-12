#!/bin/bash

# Initialize the selection variable
NODE_SELECTION=""

# Function to print the menu
print_menu() {
    echo "Please select a DLT node to use:"
    echo "1. node2"
    echo "2. node3"
    echo "3. node4"
    echo "Enter the number corresponding to your choice:"
}

# Loop until the user makes a valid selection
while [[ "$NODE_SELECTION" != "1" && "$NODE_SELECTION" != "2" && "$NODE_SELECTION" != "3" ]]; do
    print_menu
    read USER_INPUT

    # Handle the user input
    case $USER_INPUT in
        1)
            NODE_SELECTION="node2"
            ;;
        2)
            NODE_SELECTION="node3"
            ;;
        3)
            NODE_SELECTION="node4"
            ;;
        *)
            # Invalid selection, prompt again
            echo "Invalid selection. Please select 1, 2, or 3."
            ;;
    esac
done

# Construct the start command based on the selection
START_CMD="./${NODE_SELECTION}_start.sh"

# Construct the Docker run command
DOCKER_CMD="docker run -it --name $NODE_SELECTION --hostname $NODE_SELECTION --env-file .env --network host --rm dlt-node $START_CMD"

# Execute the Docker command
echo "Starting $NODE_SELECTION..."
eval $DOCKER_CMD

# Notify the user
echo "$NODE_SELECTION started successfully."
