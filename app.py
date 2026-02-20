#!/usr/bin/env python3

import socket
import json
import subprocess
import time
import sys
import os
import logging

import libiec61850client
import libmodbusmaster
import libiec60870server
import lib60870
import configparser
from urllib.parse import urlparse

hosts_info = {}
async_msg = []
async_rpt = {}

# to keep teack of different client type instances
supported_schemes = {}
clients = {}

# poll insterval
INTERVAL = 0.1

def read_value(id):
  _client = get_client(str(id))
  logger.debug("read value:" + str(id)  )
  return _client.ReadValue(id)


def write_value(id, value):
  _client = get_client(str(id))
  logger.debug("write value:" + str(value) + ", element:" + str(id) )
  retValue = _client.registerWriteValue(str(id),str(value))
  if retValue > 0:
    return retValue, _client.ErrorCodes(retValue)
  if retValue == 0:
    return retValue, "no error"
  return retValue, "general error"


def operate(id, value):
  _client = get_client(str(id))
  if value == 1:
    return _client.operate(str(id),"true")
  else:
    return _client.operate(str(id),"false")


def select(id, value):
  _client = get_client(str(id))
  logger.debug("select:" + str(id)  )
  if value == 1:
    return _client.select(str(id),"true")
  else:
    return _client.select(str(id),"false")


def cancel(id):
  _client = get_client(str(id))
  logger.debug("cancel:" + str(id)  )
  return _client.cancel(str(id))


def register_datapoint(id):
  _client = get_client(str(id))
  logger.debug("register datapoint:" + str(id) )
  _client.registerReadValue(str(id))


def register_datapoint_finished():
  logger.info("finsished registering datapoints")
  #_client = get_client(str(id))
  #ieds = client.getRegisteredIEDs()
  #for key in ieds:
    #tupl = key.split(':')
    #hostname = tupl[0]

    #port = None
    #if len(tupl) > 1 and tupl[1] != "":
    #  port = int(tupl[1])
    #model = client.getDatamodel(hostname=hostname, port=port)



# callbacks from libiec61850client
# called by client.poll
def readvaluecallback(key,data):
  global iec104_server
  global config
  logger.debug("callback: %s - %s" % (key,data))
  for item_type in config:
    for ioa in config[item_type]:
      if config[item_type][ioa] == key:
          iec104_server.update_ioa(int(ioa), data['value'])
          return
  logger.debug("could not find IOA for key:" + str(key)  )


# callback commandtermination
def cmdTerm_cb(msg):
  async_msg.append(msg)

# callback report
def Rpt_cb(key, value):
  async_rpt[key] = value
  readvaluecallback(key,value)


def read_60870_callback(ioa, ioa_data, iec104server):
  global config
  print("read callback called from lib60870")
  for item_type in config:
    if ioa in config[item_type]:
      return read_value(config[item_type][ioa])

  return -1


def command_60870_callback(ioa, ioa_data, iec104server, select_value):
  print("operate callback called from lib60870")
  for item_type in config:
    if ioa in config[item_type]:
      if select_value == True:
        return select(config[item_type][ioa],  ioa_data['data'])
      else:
        return operate(config[item_type][ioa],  ioa_data['data'])

  return -1


# returns a client for a certain type of communication such as iec61850 or modbus, based on the scheme definition in the uri
def get_client(ref):
  global supported_schemes
  global clients
  global logger
  uri_ref = urlparse(ref)
  # check if scheme exists
  if not uri_ref.scheme in supported_schemes:
    logger.error("incorrect scheme, %s is not supported as client" % uri_ref.scheme)
    return None
  
  # check if client is already initialised
  if uri_ref.scheme in clients:
    return clients[uri_ref.scheme]

  # check if there is an init function if no client exitst yet
  init_func = supported_schemes[uri_ref.scheme]
  if init_func == None:
    logger.error("no init function for scheme %s" % uri_ref.scheme)
    return None

  # initialise the client
  _client = init_func(readvaluecallback, logger, cmdTerm_cb, Rpt_cb)
  if _client == None:
    logger.error("init function not succesfull for scheme %s" % uri_ref.scheme)
    return None

  # store the client instance
  clients[uri_ref.scheme] = _client

  return _client


# add a scheme and init function to the set of supported schemes, to be used by get_client(ref)
def register_scheme(scheme,_init):
  global supported_schemes

  if scheme == None or _init == None:
    logger.error("unable to register scheme")
    return -1

  supported_schemes[scheme] = _init
  return 0




if __name__ == '__main__':
  logger = logging.getLogger('gateway')
  logging.basicConfig(format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    level=logging.INFO)

  config = configparser.ConfigParser()
  config.optionxform = str # to retain case sentistivy

  if len(sys.argv) > 1:
    config.read(sys.argv[1])
  else:
    config.read('config.local.ini')


  logger.info("started")
  # registering supported downstream protocols
  register_scheme(libiec61850client.scheme(), libiec61850client.iec61850client)
  register_scheme(libmodbusmaster.scheme(), libmodbusmaster.libmodbusmaster)

  # instantiating upstream protocol
  iec104_server = libiec60870server.IEC60870_5_104_server()
  iec104_server.start()

  #REGISTER ALL IOA's and associated IEC61850 datapoints
  if 'measuredvaluescaled' in config:
    for item in config['measuredvaluescaled']:
      #create 104 data for GI
      if iec104_server.add_ioa(int(item), lib60870.MeasuredValueScaled,0,read_60870_callback,True) == 0:
        register_datapoint(config['measuredvaluescaled'][item])
      else:
        logger.error("duplicate IOA:" + item + ", IOA not added to list")
        continue

  if 'singlepointinformation' in config:
    for item in config['singlepointinformation']:
      #create 104 data for GI
      if iec104_server.add_ioa(int(item), lib60870.SinglePointInformation,0,read_60870_callback,True) == 0:
        register_datapoint(config['singlepointinformation'][item])
      else:
        logger.error("duplicate IOA:" + item + ", IOA not added to list")
        continue

  if 'doublepointinformation' in config:
    for item in config['doublepointinformation']:
      #create 104 data for GI
      if iec104_server.add_ioa(int(item), lib60870.DoublePointInformation,0,read_60870_callback,True) == 0:
        register_datapoint(config['doublepointinformation'][item])
      else:
        logger.error("duplicate IOA:" + item + ", IOA not added to list")
        continue
    register_datapoint_finished()

  if 'singlepointcommand' in config:
    for item in config['singlepointcommand']:
      #create 104 data for GI
      if iec104_server.add_ioa(int(item), lib60870.SingleCommand,0,command_60870_callback,False) == 0:
        print("SingleCommand registered")
      else:
        logger.error("duplicate IOA:" + item + ", IOA not added to list")
        continue

  if 'doublepointcommand' in config:
    for item in config['doublepointcommand']:
      #create 104 data for GI
      if iec104_server.add_ioa(int(item), lib60870.DoubleCommand,0,command_60870_callback,False) == 0:
        print("DoubleCommand registered")
      else:
        logger.error("duplicate IOA:" + item + ", IOA not added to list")
        continue



  while True:
    time.sleep(INTERVAL)
    for _client in clients.values():
      _client.poll()

    logger.debug("values polled")
    
    for key in list(async_rpt):
      val = async_rpt.pop(key)
      logger.debug("%s updated via report" % key)


