#!/bin/zsh

# Package appropriate Azure function files for distribution (APM install via WEBSITE_RUN_FROM_PACKAGE)
#
# As input, we take a squashfs volume containing the Azure Function files as created by VS Code using
# their internal-ish build tool Oryx, which does a platform-specific build targeting the native Linux
# envrionment of the Azure Functions runtime (debian/bullseye). All other build methods, including 
# using the Azure command line or Powershell, simply package the current platform (in my case, MaxOS)
# files. Given that this project is Python, that SHOULD work, but in some cases when there are Python
# modules that have native dependencies or native built elements, the resulting package will not work
# on the Azure Functions runtime (this is incredibly hard to track down, as there are no useful 
# diagnostics when the package is installed using WEBSITE_RUN_FROM_PACKAGE, the module just fails to 
# load).
#
# It is possible that a an automated build using Oryx via Docker to target Linux (similar to what VS 
# Code does internally) would work. This method seems somewhat supported by Microsoft, but is not well
# documented. Alternatively, the naive (simple packaging) method using the ./pack.sh script (in this 
# project) should work fine if the build was run on Linux.  I have not tested either of these methods.
#
# So we're going to deploy the function to Azure using VS Code, then we're going go get the package
# that it creates, located at:
#
#   [Azure storage account for the function app]
#     Blob Containers
#       scm-releases
#         scm-latest-[function app name].zip
#
# Download that file, which will be in squashfs format, then run this script against it (pass in the
# path to that file as an argument to this script). This script will unsquash it, then zip it up and
# put the resulting zip file in /dist/censys-sentinel.zip. That resulting zip file can then by put 
# somewhere public to be referenced from ARM deploys using the WEBSITE_RUN_FROM_PACKAGE app setting.
#
# You will need to have squashfs installed locally to run this script.  On MacOS, you can install it
# using Homebrew: brew install squashfs
#

# Create a temporary directory
tmpdir=$(mktemp -d -t ci-XXXXXXXXXX)

# Expand the squashfs file into the temporary directory
unsquashfs -d $tmpdir $1

# Create the dist directory if it doesn't exist
mkdir -p ./dist

# Use zip to create a zip file in the dist directory from the temporary directory
cd $tmpdir
rm -f $OLDPWD/dist/censys-sentinel.zip
zip -r $OLDPWD/dist/censys-sentinel.zip . -x "*.DS_Store" -x "env/*" -x "oryx*" > /dev/null

# Remove the temporary directory
cd ..
rm -rf $tmpdir
