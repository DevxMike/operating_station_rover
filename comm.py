from multiprocessing import Process, Pipe
import multiprocessing
import serial
from struct import pack, unpack
from serial.tools import list_ports
import gui
import numpy as np
import pygame
import math
from joystick_regulator import regulator, translate_hat

class Packet:
    def __init__(self, message_type: int, message: str) -> None:
        self.start = 0x69
        self.message_type = message_type
        self.message_lengh = len(message) % 256
        self.crc = (sum([ord(c) for c in message]) + len(message)) % 256
        self.message = message

    def get_packet(self) -> bytearray:
        header = pack(
            f"BBBB",
            self.start,
            self.message_type,
            self.message_lengh,
            self.crc,
        )
        return header + self.message.encode("ascii")

class dePacket:
    def __init__(self, callback):
        self.start = 0
        self.message_type = 0
        self.message_lenght = 0
        self.crc = 0
        self.payload = []
        self.deserializer_state = 0
        self.callback = callback
    # waiting_for_start = 0,
    #     waiting_for_type = 1,
    #     waiting_for_len = 2,
    #     waiting_for_crc = 3,
    #     data_acquisition = 4
    def deserialize(self, data):
        for i in range(len(data)):  
            s = self.deserializer_state
            tmp = data[i]
            packet_start = 0x69

            # case waiting_for_start:
            if(s == 0):
                if(tmp == packet_start):
                    self.start = tmp
                    self.payload = []
                    self.deserializer_state = 1
                    
            
            # case waiting_for_type:
            elif(s == 1):
                self.message_type = tmp
                self.deserializer_state = 2
                

            # case waiting_for_len:
            elif(s == 2):
                self.message_lenght = tmp
                self.deserializer_state = 3
                
            
            # case waiting_for_crc:
            elif(s == 3):
                self.crc = tmp
                self.deserializer_state = 4
            
            # case data_acquisition:
            elif(s == 4):
                self.payload.append(tmp)

            if(len(self.payload == self.message_lenght) and s == 4):
                tmp_crc = (sum([ord(c) for c in self.payload]) + len(self.payload)) % 256

                if(tmp_crc == self.crc):
                    self.callback(self.type, self.payload)
                
                if(i > 0): 
                    i -= 1
                self.deserializer_state = 0
                
def code_decode(packet):
    return bytes([byte ^ 0x69 for byte in packet])

class communication:
    devices = dict()
    radio_alive = False

    def get_ports(this):
        res = []
        ports = list_ports.comports()

        for port, desc, hwid in sorted(ports):
            res.append("{}".format(desc))
            this.devices[desc] = port

        return res

    def get_radio_connection(this, name):
        try:
            this.radio = serial.Serial(this.devices[name])
            this.radio_alive = True
            return True
        except:
            return False
    
    def send_data_over_radio(this, data, type):
        try:
            packet = Packet(type, data).get_packet()
            this.radio.write(code_decode(packet))
        except:
            pass

    def read_data_over_radio(this, packet):
        try:
            this.radio.write(code_decode(packet))
        except:
            return None

    def close_radio_connection(this):
        try:
            this.radio.close()
        except:
            pass

def get_joysticks():
    return [pygame.joystick.Joystick(x).get_name() for x in range(pygame.joystick.get_count())]

def run_com():
    pygame.init()
    comm = communication()
    joysticks = get_joysticks()
    ports = comm.get_ports()
    user_interface = gui.UserInterface()
    comm_pipe_to_gui, gui_pipe = multiprocessing.Pipe()  
    gui_process = multiprocessing.Process(target=user_interface.run, args=(gui_pipe,([ports], [joysticks])))

    gui_process.start()

    while True:
        msg = []
        if(comm_pipe_to_gui.poll(0.001)):
            msg = comm_pipe_to_gui.recv()
            
            for message in msg:
                print(message)
                if(type(message) == dict):
                    for k, v in message.items():
                        if(k == 'connect_radio'):
                            if(comm.get_radio_connection(v)):
                                comm_pipe_to_gui.send('radio_ok')
                            else:
                                comm_pipe_to_gui.send('radio_nok')
                elif(type(message) == list):
                    for m in message:
                        if(m == 'get_ports'):
                            pygame.quit()
                            pygame.init()
                            comm_pipe_to_gui.send((comm.get_ports(), get_joysticks()))
                        elif(m == 'exit'):
                            gui_process.join()
                            comm.close_radio_connection()
                            print("Exit 0")
                            break

        comm.send_data_over_radio('', 0)

run_com()