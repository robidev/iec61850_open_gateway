# iec61850_open_gateway

This is an open implementation of an IEC 61850 based gateway to IEC60870. It is a python3 based iec61850 to IEC60870 gateway implementation that uses ctypes for the wrappers.

The gateway is configured by using an ini-file; config.ini
This file describes the mapping. the [] defines the IEC60870 datatype
The format for connecting a datapoint is: IOA = iec61850://[IED-IP]:[port]/[LD]/[LN]/[Do]/[Da]. 

# getting started(docker):

build the container

`$ sudo docker build -f Dockerfile.libiec61850_gateway --tag gateway .`

run the container

`$ sudo docker run --rm -p 2404:2404 gateway`

# getting started(localhost):

## libiec61850

this gateway needs libiec61850.so installed in /usr/local/lib/libiec61850.so This can be done by doing:

get  the library

`$ git clone https://github.com/mz-automation/libiec61850.git`

cd into the directory

`$ cd libiec61850`

compile the library

`$ make dynlib`

install the library in the right place for the ctypes wrapper 
(you can modify this in lib61850.py if you prefer a different location)

`$ sudo cp build/libiec61850.so /usr/local/lib/`

## lib60870

this gateway also needs lib60870.so installed in /usr/local/lib/lib60870.so This can be done by doing:

get  the library

`$ git clone https://github.com/mz-automation/lib60870.git`

cd into the directory

`$ cd lib60870/lib60870-C`

compile the library

`$ make dynlib`

install the library in the right place for the ctypes wrapper 
(you can modify this in lib61850.py if you prefer a different location)

`$ sudo cp build/lib60870.so /usr/local/lib/`

## run the gateway

cd to the client project dir.

`$ cd ../iec61850_open_gateway`

then start the app;

`$ python3 app.py`

WARNING: the default config file used is config.local.ini. This assumes you have IEC61850 IED's running. You can set these up by cloning iec61850_open_server:

`$ git clone git@github.com:robidev/iec61850_open_server.git`

build it local

`$ cmake . && make`

and then run the iec61850 servers on localhost with

`$ ./local_test.sh`


