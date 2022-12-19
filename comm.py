from multiprocessing import Process, Pipe
import multiprocessing
from tkinter import Pack
import serial
from struct import pack, unpack
from serial.tools import list_ports
from sympy import false
import gui
import numpy as np
import pygame
import math
from joystick_regulator import regulator, translate_hat
import queue
import time

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

            print(f'{len(self.payload)}, {self.message_lenght}, {self.deserializer_state }, {tmp}')
            if(len(self.payload) == self.message_lenght and self.deserializer_state == 4):
                tmp_crc = (sum([ord(c) for c in str(bytes(self.payload), 'utf-8')]) + len(self.payload)) % 256

                if(tmp_crc == self.crc):
                    self.callback(self.message_type, self.payload)
                
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

communicates = queue.Queue(512)
states = {}
refresh_gui = False

def callback(type, payload):
    global communicates
    global states
    global refresh_gui

    if(type == 0):
        tmp = Packet(0, '')
        communicates.put_nowait(tmp.get_packet)
    
    elif(type == 7 or type == 2):
        states['diag'] = payload
        refresh_gui = True

    elif(type == 4):
        states['GPS'] = payload
        refresh_gui = True
    
    elif(type == 3):
        states['IMU'] = payload
        refresh_gui = True

def joystick_process(pipe, joystick):
    global communicates
    axes = [0.0] * joystick.get_numaxes()
    buttons = [False] * joystick.get_numbuttons()
    reg = regulator()

    while True:
        event = pygame.event.wait()
        if event.type == pygame.JOYAXISMOTION:
               e = event.dict
               axes[e["axis"]] = e["value"]
        elif event.type in [pygame.JOYBUTTONUP, pygame.JOYBUTTONDOWN]:
               e = event.dict
               buttons[e["button"]] ^= True

        x1_val = axes[1] * -100.0
        x2_val = axes[0] * 100.0
        x3_val = axes[2] * 100.0

        u1_val, u2_val = reg(x1_val, x2_val, x3_val)
        hat_readings = translate_hat(joystick.get_hat(0))

        tmp1 = Packet(1, f'D{u1_val},{u2_val}')
        # communicates.put_nowait(tmp1.get_packet())

        tmp2 = Packet(1, f'C{hat_readings}')
        # communicates.put_nowait(tmp2.get_packet())

        pipe.send([tmp1, tmp2])

        time.sleep(0.005)





def run_com():
    global communicates
    global states
    global refresh_gui
    pygame.init()
    pygame.joystick.init()
    controller = pygame.joystick.Joystick(0)
    controller.init()
    # comm = communication()
    # joysticks = get_joysticks()
    # ports = comm.get_ports()
    # user_interface = gui.UserInterface()
    # comm_pipe_to_gui, gui_pipe = multiprocessing.Pipe()  
    # gui_process = multiprocessing.Process(target=user_interface.run, args=(gui_pipe,([ports], [joysticks])))
    comm_pipe_to_joy, joy_pipe = multiprocessing.Pipe()  
    controller_process = multiprocessing.Process(target = joystick_process, args=(joy_pipe,controller))
    # gui_process.start()
    controller_process.start()

    while True:
        if(refresh_gui):
            # logic to refresh gui info
            refresh_gui = False
            pass
        
        if(comm_pipe_to_joy.poll(0.005)):
            tmp = comm_pipe_to_joy.recv()
            for p in tmp:
                print(p.get_packet())
        # while not communicates.empty():
        #     print(communicates.get())

        #logic to get joystick readings in man mode
        
        # msg = []
        # if(comm_pipe_to_gui.poll(0.001)):
        #     msg = comm_pipe_to_gui.recv()

run_com()