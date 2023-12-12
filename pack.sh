#!/bin/bash

# Package appropriate Azure function files for distribution (APM install via WEBSITE_RUN_FROM_PACKAGE)

# Create a temporary directory
tmpdir=$(mktemp -d -t ci-XXXXXXXXXX)

# Use rsync to copy all files and directories to the temporary directory,
# while respecting .funcignore
rsync -av --prune-empty-dirs --exclude-from=.funcignore ./ $tmpdir/

# Create the dist directory if it doesn't exist
mkdir -p ./dist

# Use zip to create a zip file in the dist directory from the temporary directory
cd $tmpdir
zip -r $OLDPWD/dist/censys-sentinel.zip .

# Remove the temporary directory
cd ..
rm -rf $tmpdir