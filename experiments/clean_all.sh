#!/bin/bash

# Delete all CSV files in consumer/ and provider/ directories
find consumer/ provider/ merged/ -type f -name "*.csv" -exec rm -f {} \;

# Delete all TXT files in logs/ directory
find logs/ -type f -name "*.txt" -exec rm -f {} \;

echo "All CSV files in consumer/ and provider/ have been deleted."
echo "All TXT files in logs/ have been deleted."

