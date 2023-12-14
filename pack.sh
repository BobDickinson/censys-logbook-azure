#!/bin/zsh

# Package appropriate Azure function files for distribution (APM install via WEBSITE_RUN_FROM_PACKAGE)
#
# If you are building on Linux, you can use this script to package the function for deployment.  If you
# are building on any other OS (including MacOS), you will need to use the repack.sh script and the 
# process described therein to generate a Linux-native package that is guaranteed to work on Azure.
#

# Create a temporary directory
tmpdir=$(mktemp -d -t ci-XXXXXXXXXX)

# Use rsync to copy all files and directories to the temporary directory,
# while respecting .funcignore
rsync -a --prune-empty-dirs --exclude-from=.funcignore ./ $tmpdir/

# Create a Python virtual environment, install deps in the temporary directory, and clean up environment
python3 -m venv env
source env/bin/activate
pip install  --target="$tmpdir/.python_packages/lib/site-packages" -r requirements.txt
deactivate

# Create the dist directory if it doesn't exist
mkdir -p ./dist

# Use zip to create a zip file in the dist directory from the temporary directory
cd $tmpdir
rm -f $OLDPWD/dist/censys-sentinel.zip
zip -r $OLDPWD/dist/censys-sentinel.zip . -x "*.DS_Store" -x "env/*" > /dev/null

# Remove the temporary directory and the Python env directory
cd ..
rm -rf $tmpdir
rm -rf ./env
