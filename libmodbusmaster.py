import pymodbus
import logging

import pymodbus.client
from abstract_client import abstract_client
from urllib.parse import urlparse
from pymodbus.exceptions import ConnectionException

logger = logging.getLogger(__name__)

def scheme():
    return "modbus"


# Modbus address range boundaries (1-indexed, as used in register maps)
HOLDING_REGISTER_MIN = 40001   # 4xxxx  FC03 read / FC06 write
HOLDING_REGISTER_MAX = 49999
INPUT_REGISTER_MIN   = 30001   # 3xxxx  FC04 read only
INPUT_REGISTER_MAX   = 39999


def parse_path(path):
    """Parse the URI path into (device_id, register_address).

    The register address is the 1-indexed logical address as used in the
    device register map (e.g. 40001, 30005).  Protocol-level conversion
    to 0-based addressing is handled at read/write time.

    Expected formats:
      /1/40001  -> device_id=1, address=40001
      /40001    -> device_id=1, address=40001  (legacy, no device_id segment)
    """
    parts = path.lstrip("/").split("/")
    if len(parts) >= 2:
        return int(parts[0]), int(parts[1])
    elif len(parts) == 1:
        return 1, int(parts[0])
    else:
        raise ValueError("Invalid modbus URI path: %s" % path)


def address_to_protocol(address):
    """Convert a 1-indexed register map address to the 0-based protocol address.

    E.g. 40001 -> 0,  30005 -> 4
    """
    if HOLDING_REGISTER_MIN <= address <= HOLDING_REGISTER_MAX:
        return address - HOLDING_REGISTER_MIN
    elif INPUT_REGISTER_MIN <= address <= INPUT_REGISTER_MAX:
        return address - INPUT_REGISTER_MIN
    else:
        raise ValueError("Address %i is outside supported ranges (3xxxx / 4xxxx)" % address)


class libmodbusmaster(abstract_client):

    def __init__(self, readvaluecallback, loggerRef, arg1=None, arg2=None):
        global logger
        if loggerRef is not None:
            logger = loggerRef

        self.connections = {}
        self.keys = []
        self.values = {}
        self.readvaluecallback = readvaluecallback
        self.modbusconnection_failed_message = {}
        logging.getLogger("pymodbus").setLevel(logging.CRITICAL)
        logger.info("libmodbusmaster initialised")

    @staticmethod
    def ErrorCodes(value):
        return "general error: %i" % value


    def registerReadValue(self, id):
        con = self.getRegisteredConnections(id)
        if con is not None:
            self.keys.append(id)
            self.values[id] = None
        else:
            logger.error("could not register %s: no connection to modbus node" % id)
        return -1


    def registerWriteValue(self, id, value):
        con = self.getRegisteredConnections(id)
        if con is not None:
            device_id, address = parse_path(urlparse(id).path)
            error = self.writeholdingregister(con, address, int(value), device_id)
            if error == 0:
                logger.debug("Value '%s' written to %s" % (value, id))
                return 0
            else:
                logger.error("could not write '%s' to %s with error: %i" % (str(value), id, error))
                if error == 3:  # lost connection
                    con.close()
                return error
        else:
            logger.error("could not write to %s: no connection to modbus node" % id)
        return -1


    def getRegisteredConnections(self, id):
        uri_ref = urlparse(id)
        port = uri_ref.port
        if not port:
            port = 502

        if uri_ref.scheme != "modbus":
            logger.error("incorrect scheme, only modbus is supported by this client, not %s" % uri_ref.scheme)
            return None

        if uri_ref.hostname is None:
            logger.error("missing hostname: %s" % id)
            return None

        tupl = uri_ref.hostname + ":" + str(port)

        con = None
        if tupl in self.connections:
            con = self.connections[tupl]["con"]
            if con.connected:
                return con
        else:
            con = pymodbus.client.ModbusTcpClient(uri_ref.hostname, port=port)

        try:
            con.connect()
        except ConnectionException as e:
            logger.error("Failed to connect to %s: %s" % (tupl, e))
            con.close()
            return None

        if con.connected:
            if tupl in self.modbusconnection_failed_message and self.modbusconnection_failed_message[tupl] == True:
                logger.info("Modbus reconnected to %s" % tupl)
            self.modbusconnection_failed_message[tupl] = False
            self.connections[tupl] = {"con": con}
            return con
        else:
            if tupl in self.modbusconnection_failed_message and self.modbusconnection_failed_message[tupl] == False:
                logger.error("no valid modbus connection with %s" % tupl)
            self.modbusconnection_failed_message[tupl] = True
            con.close()
            return None


    def ReadValue(self, id):
        """Read a register value, routing to FC03 or FC04 based on address range."""
        con = self.getRegisteredConnections(id)
        if con is None:
            logger.debug("could not read from %s: no connection to modbus node" % id)
            return None

        device_id, address = parse_path(urlparse(id).path)

        if HOLDING_REGISTER_MIN <= address <= HOLDING_REGISTER_MAX:
            value = self.readholdingregister(con, address, device_id)
        elif INPUT_REGISTER_MIN <= address <= INPUT_REGISTER_MAX:
            value = self.readinputregister(con, address, device_id)
        else:
            logger.error("address %i in %s is outside supported ranges (3xxxx / 4xxxx)" % (address, id))
            return None

        if value is not None and value != self.values[id]:
            self.readvaluecallback(id, {'value': value})
        self.values[id] = value
        return value


    def poll(self):
        for key in self.keys:
            self.ReadValue(key)


    def readholdingregister(self, con, address, device_id=1):
        """Read a single holding register (FC03)."""
        proto_address = address_to_protocol(address)
        try:
            result = con.read_holding_registers(proto_address, count=1, slave=device_id)
        except ConnectionException as e:
            logger.error("Connection lost during FC03 read: %s" % e)
            con.close()
            # Remove the connection from self.connections
            for tupl, data in list(self.connections.items()):
                if data["con"] is con:
                    del self.connections[tupl]
                    break
            return None
        if result.isError():
            logger.error("FC03 read failed at address %i (protocol %i), device_id %i"
                         % (address, proto_address, device_id))
            return None
        return result.registers[0]

    def readinputregister(self, con, address, device_id=1):
        """Read a single input register (FC04)."""
        proto_address = address_to_protocol(address)
        #logger.info("FC04 read at address %i (protocol %i), device_id %i"
        #                 % (address, proto_address, device_id))
        try:
            result = con.read_input_registers(proto_address, count=1, slave=device_id)
        except ConnectionException as e:
            logger.error("Connection lost during FC04 read: %s" % e)
            con.close()
            # Remove the connection from self.connections
            for tupl, data in list(self.connections.items()):
                if data["con"] is con:
                    del self.connections[tupl]
                    break
            return None
        if result.isError():
            logger.error("FC04 read failed at address %i (protocol %i), device_id %i"
                         % (address, proto_address, device_id))
            return None
        #logger.info("value:" + str(result.registers[0]))
        return result.registers[0]

    def writeholdingregister(self, con, address, value, device_id=1):
        """Write a single holding register (FC06)."""
        if not (HOLDING_REGISTER_MIN <= address <= HOLDING_REGISTER_MAX):
            logger.error("FC06 write rejected: address %i is not in holding register range (4xxxx)" % address)
            return 1
        proto_address = address_to_protocol(address)
        try:
            result = con.write_register(proto_address, value, slave=device_id)
        except ConnectionException as e:
            logger.error("Connection lost during FC06 write: %s" % e)
            con.close()
            # Remove the connection from self.connections
            for tupl, data in list(self.connections.items()):
                if data["con"] is con:
                    del self.connections[tupl]
                    break
            return 1
        if result.isError():
            logger.error("FC06 write failed at address %i (protocol %i), device_id %i"
                         % (address, proto_address, device_id))
            return 1
        return 0


    def operate(self, id, value):
        """Write a breaker command to a holding register (FC06).

        value: 0 = no action, 1 = open breaker, 2 = close breaker

        Config example:
          6002=modbus://10.0.0.3:502/1/40001

        The URI always points to the 4xxxx command address.
        The corresponding 3xxxx status address (command_address - 10000) is
        available for independent polling via a separate config mapping.
        """
        int_value = 0
        if value == 'true':
            int_value = 2
        if value == 'false':
            int_value = 1

        if int_value == 0:
            logger.debug("operate called with value 0 (no action) for %s, ignoring" % id)
            return 0

        if int_value not in (1, 2):
            logger.error("operate: invalid value %s for %s — expected 0 (no action), 1 (open), 2 (close)" % (value, id))
            return -1

        con = self.getRegisteredConnections(id)
        if con is None:
            logger.error("operate failed for %s: no connection to modbus node" % id)
            return -1

        device_id, address = parse_path(urlparse(id).path)

        if not (HOLDING_REGISTER_MIN <= address <= HOLDING_REGISTER_MAX):
            logger.error("operate: address %i in %s is not a holding register (4xxxx)" % (address, id))
            return -1

        action = "open" if int_value == 1 else "close"
        logger.info("operate: %s — writing %i to address %i, device_id %i (%s)"
                    % (action, int_value, address, device_id, id))

        error = self.writeholdingregister(con, address, int_value, device_id)
        if error != 0:
            logger.error("operate FC06 write failed for %s" % id)
            return error

        logger.debug("operate command written successfully to %s" % id)
        return 0


    def select(self, id, value):
        logger.error("select is not implemented for modbus")

    def cancel(self, id, value):
        logger.error("cancel is not implemented for modbus")