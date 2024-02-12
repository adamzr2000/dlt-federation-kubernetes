#!/bin/bash

# Function to print the menu
print_menu() {
    echo "Please select a DLT node to use:"
    echo "1. node2"
    echo "2. node3"
    echo "3. node4"
    echo -n "Enter the number (1-3) corresponding to your choice, or 'q' to quit: "
}

# Function to handle the selection
handle_selection() {
    case $1 in
        1)
            NODE_SELECTION="node2"
            ;;
        2)
            NODE_SELECTION="node3"
            ;;
        3)
            NODE_SELECTION="node4"
            ;;
        'q'|'Q')
            echo "Exiting."
            exit 0
            ;;
        *)
            echo "Invalid selection: $1. Please select 1, 2, 3, or 'q' to quit."
            return 1 # Indicates invalid selection
            ;;
    esac
    return 0 # Indicates valid selection
}

# Main loop
while true; do
    print_menu
    read -r USER_INPUT

    if handle_selection "$USER_INPUT"; then
        # Valid selection, proceed with the operation
        START_CMD="./${NODE_SELECTION}_start.sh"
        DOCKER_CMD="docker run -it --name $NODE_SELECTION --hostname $NODE_SELECTION --network host --rm -v $(pwd)/.env:/dlt-network/.env dlt-node $START_CMD"

        echo "Starting $NODE_SELECTION with command $START_CMD..."
        eval "$DOCKER_CMD"

        echo "$NODE_SELECTION started successfully with command $START_CMD."
        break # Exit the loop after successful operation
    else
        # Invalid selection, the loop will repeat
        continue
    fi
done
