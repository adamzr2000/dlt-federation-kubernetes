#!/bin/bash

# Delete all CSV files in consumers/ and providers/ directories
find consumers/ providers/ -type f -name "*.csv" -exec rm -f {} \;

echo "All CSV files in consumers/ and providers/ have been deleted."
