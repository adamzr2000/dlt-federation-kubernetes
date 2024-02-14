#!/bin/bash

echo "Current configuration files in the directory:"
ls *-config 2>/dev/null || echo "No configuration files found."

# Improved function or direct reading
read -p "Enter a number to name the config file as 'microk8s-X-config': " number

filename="microk8s-${number}-config"

if [[ -f "$filename" ]]; then
    echo "File $filename already exists."
    read -p "Are you sure you want to overwrite this file? (y/n): " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        microk8s config > "$filename"
        echo "MicroK8s configuration has been saved to $filename."
    else
        echo "Operation canceled."
    fi
else
    microk8s config > "$filename"
    echo "MicroK8s configuration has been saved to $filename."
fi
    