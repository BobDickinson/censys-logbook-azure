#!/bin/zsh

# Package appropriate Azure function files for distribution (APM install via WEBSITE_RUN_FROM_PACKAGE)

# Create a temporary directory
tmpdir=$(mktemp -d -t ci-XXXXXXXXXX)

# Use rsync to copy all files and directories to the temporary directory,
# while respecting .funcignore
rsync -a --prune-empty-dirs --exclude-from=.funcignore ./ $tmpdir/

python3 -m venv env
source env/bin/activate

pip install  --target="$tmpdir/.python_packages/lib/site-packages" -r requirements.txt

# Change permissions of the installed packages
chmod -R u+rwX "$tmpdir/.python_packages"

deactivate
rm -rf ./env

# Create the dist directory if it doesn't exist
mkdir -p ./dist

# Use zip to create a zip file in the dist directory from the temporary directory
cd $tmpdir
rm -f $OLDPWD/dist/censys-sentinel.zip
zip -r $OLDPWD/dist/censys-sentinel.zip . -x "*.DS_Store" > /dev/null

# Remove the temporary directory
cd ..
rm -rf $tmpdir