#!/usr/bin/env python3
from lib60870 import *
import time

class IEC60870_5_104_client:
  # Connection event handler 
  def connectionHandler (self, parameter, connection, event):
    if event == CS104_CONNECTION_OPENED:
          print("Connection established")
    elif event == CS104_CONNECTION_CLOSED:
          print("Connection closed")
    elif event == CS104_CONNECTION_STARTDT_CON_RECEIVED:
          print("Received STARTDT_CON")
    elif event == CS104_CONNECTION_STOPDT_CON_RECEIVED:
          print("Received STOPDT_CON")


  #CS101_ASDUReceivedHandler implementation
  #For CS104 the address parameter has to be ignored
  def asduReceivedHandler (self, parameter, address, asdu):
    print("RECVD ASDU type: %s(%i) elements: %i" % (
            TypeID_toString(CS101_ASDU_getTypeID(asdu)),
            CS101_ASDU_getTypeID(asdu),
            CS101_ASDU_getNumberOfElements(asdu)))

    if (CS101_ASDU_getTypeID(asdu) == M_ME_TE_1):

        print("  measured scaled values with CP56Time2a timestamp:")

        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), MeasuredValueScaledWithCP56Time2a) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io, InformationObject) ),
                    MeasuredValueScaled_getValue(cast(io, MeasuredValueScaled) )
            ))
            MeasuredValueScaledWithCP56Time2a_destroy(io)

    elif (CS101_ASDU_getTypeID(asdu) == M_SP_NA_1):
        print("  single point information:")

        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), SinglePointInformation) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io,InformationObject) ),
                    SinglePointInformation_getValue(cast(io,SinglePointInformation) )
            ))
            SinglePointInformation_destroy(io)
    elif (CS101_ASDU_getTypeID(asdu) == M_DP_NA_1):
        print("  double point information:")

        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), DoublePointInformation) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io,InformationObject) ),
                    DoublePointInformation_getValue(cast(io,DoublePointInformation) )
            ))
            DoublePointInformation_destroy(io)
    elif (CS101_ASDU_getTypeID(asdu) == M_ME_NB_1):
        print("  measured value scaled:")

        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), MeasuredValueScaled) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io,InformationObject) ),
                    MeasuredValueScaled_getValue(cast(io,MeasuredValueScaled) )
            ))
            MeasuredValueScaled_destroy(io)     
    elif (CS101_ASDU_getTypeID(asdu) == C_SC_NA_1):
        print("received single command response")
        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), SinglePointInformation) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io,InformationObject) ),
                    SinglePointInformation_getValue(cast(io,SinglePointInformation) )
            ))
            SinglePointInformation_destroy(io)

    elif (CS101_ASDU_getTypeID(asdu) == C_DC_NA_1):
        print("received double command response")
        for i in range(CS101_ASDU_getNumberOfElements(asdu)):

            io = cast(CS101_ASDU_getElement(asdu, i), DoublePointInformation) 
            print("    IOA: %i value: %i" % (
                    InformationObject_getObjectAddress(cast(io,InformationObject) ),
                    DoublePointInformation_getValue(cast(io,DoublePointInformation) )
            ))
            DoublePointInformation_destroy(io)

    return True


  def __init__(self, ip = "localhost", port = IEC_60870_5_104_DEFAULT_PORT):
    print("Connecting to: %s:%i" % ( ip, port))
    self.con = CS104_Connection_create(ip, port)

    self.p_connectionHandler = CS104_ConnectionHandler(self.connectionHandler)
    self.p_asduReceivedHandler = CS101_ASDUReceivedHandler(self.asduReceivedHandler)

    CS104_Connection_setConnectionHandler(self.con, self.p_connectionHandler, None)
    CS104_Connection_setASDUReceivedHandler(self.con, self.p_asduReceivedHandler, None)

  def start(self):
    if (CS104_Connection_connect(self.con)):
        print("Connected!")

        CS104_Connection_sendStartDT(self.con)
        time.sleep( 5 )
        CS104_Connection_sendInterrogationCommand(self.con, CS101_COT_ACTIVATION, 1, IEC60870_QOI_STATION)
        time.sleep( 5 )
        #sc = cast(SingleCommand_create(None, 5000, True, False, 0), InformationObject)

        #print("Send control command C_SC_NA_1")
        #CS104_Connection_sendProcessCommandEx(self.con, CS101_COT_ACTIVATION, 1, sc)

        #InformationObject_destroy(sc)
        #time.sleep( 5 )
        dc = cast(DoubleCommand_create(None, 6000, 1, True, 0), InformationObject)

        print("Send control command C_DC_NA_1")
        CS104_Connection_sendProcessCommandEx(self.con, CS101_COT_ACTIVATION, 1, dc)

        InformationObject_destroy(dc)
        time.sleep( 0.5 )

        dc = cast(DoubleCommand_create(None, 6000, 1, False, 0), InformationObject)

        print("Send control command C_DC_NA_1")
        CS104_Connection_sendProcessCommandEx(self.con, CS101_COT_ACTIVATION, 1, dc)

        InformationObject_destroy(dc)
        time.sleep( 5 )
        # Send clock synchronization command 
        #newTime = sCP56Time2a() 
        #CP56Time2a_createFromMsTimestamp(CP56Time2a(newTime), Hal_getTimeInMs())

        #print("Send time sync command")
        #CS104_Connection_sendClockSyncCommand(self.con, 1, CP56Time2a(newTime))

        #time.sleep( 1 )
        CS104_Connection_sendStopDT(self.con)
    else:
        print("Connect failed!")

    CS104_Connection_destroy(self.con)
    print("exit")

#test the class
if __name__== "__main__":
  client = IEC60870_5_104_client()
  client.start()



