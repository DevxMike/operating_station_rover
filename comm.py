from multiprocessing import Process, Pipe
import multiprocessing
from tkinter import Pack
import serial
from struct import pack, unpack
from serial.tools import list_ports
from sympy import false
from gui import UserInterface 
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

def code_decode(packet):
    return bytes([byte ^ 0x69 for byte in packet])

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
            # tmp = data[i]
            s = self.deserializer_state
            # print(f"{tmp}, {type(tmp)}")
            tmp = ord(data[i]) ^ 0x69

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

            # print(f'{len(self.payload)}, {self.message_lenght}, {self.deserializer_state }, {tmp}')
            if(len(self.payload) == self.message_lenght and self.deserializer_state == 4):
                tmp_crc = (sum([ord(c) for c in str(bytes(self.payload), 'utf-8')]) + len(self.payload)) % 256

                if(tmp_crc == self.crc):
                    self.callback(self.message_type, self.payload)
                
                if(i > 0): 
                    i -= 1
                self.deserializer_state = 0




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

    def read_data_over_radio(this):
        try:
            if(this.radio.inWaiting() > 0):
                return this.radio.read(1)
            else:
                return None
            # this.radio.write(code_decode(packet))
        except:
            return None

    def close_radio_connection(this):
        try:
            this.radio.close()
        except:
            pass

def get_joysticks():
    pygame.init()
    tmp = [pygame.joystick.Joystick(x).get_name() for x in range(pygame.joystick.get_count())]
    pygame.quit()
    return tmp

def time_ms():
    return int(time.time() * 1000)

communicates = queue.Queue(512)
com_timeout = time_ms()

states = {
    'diag' : [],
    'GPS'  : [],
    'IMU'  : []
}
refresh_gui = False

def callback(type, payload):
    global communicates
    global states
    global refresh_gui
    if(type == 0):
        communicates.put_nowait({'type' : 0, 'payload' : ''})
        com_timeout = time_ms()
    
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
    axes = [0.0] * joystick.get_numaxes()
    buttons = [False] * joystick.get_numbuttons()
    reg = regulator()

    while True:
        event = pygame.event.wait(5)
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

        tmp2 = Packet(1, f'C{hat_readings}')

        pipe.send([tmp1, tmp2])
        if(pipe.poll(0.005)):
            tmp = pipe.recv()
            if('EXIT' in tmp):
                break
        # time.sleep(0.01)

mode = 'man'
millis = 0

coords = {
        'longitude' : 0,
        'latitude' : 0
    }

def run_com():
    global communicates
    global states
    global refresh_gui
    global mode
    global millis 
    global coords
    global com_timeout

    comm = communication()
    joysticks = get_joysticks()
    ports = comm.get_ports()
    # user_interface = gui.UserInterface()
    comm_pipe_to_gui, gui_pipe = multiprocessing.Pipe()  
    gui_process = multiprocessing.Process(target=UserInterface().run, args=(gui_pipe,[[ports], [joysticks]]))
    comm_pipe_to_joy, joy_pipe = multiprocessing.Pipe()  
    
    gui_process.start()

    while True:
        if(comm_pipe_to_gui.poll(0.01)):
            tmp = comm_pipe_to_gui.recv()
            if('connect' in tmp['gui_requests']):
                # params = tmp['params']
                print(tmp['params'])
                joysticks_available = get_joysticks()
                print(tmp['params'][1][0])
                pygame.init()
                pygame.joystick.init()
                index_of_joystick = joysticks_available.index(tmp['params'][1][0])
                controller = pygame.joystick.Joystick(index_of_joystick)
                controller.init()
                comm.get_radio_connection(tmp['params'][0][0])
                break 
            
            elif('refresh' in tmp['gui_requests']):
                comm_pipe_to_gui.send({'radio' : comm.get_ports(), 'joystick' : get_joysticks()})
                # print('refresh')

    controller_process = multiprocessing.Process(target = joystick_process, args=(joy_pipe,controller))
    controller_process.start()
    comm.send_data_over_radio('', 0)
    deserializer = dePacket(callback)

    millis = time_ms()
    # 100 - coords
    while True:
        read_data = []

        if(time_ms() - millis > 500):
            comm.send_data_over_radio('', 7)
            comm.send_data_over_radio('', 8)
            if(mode == 'man'):
                comm.send_data_over_radio('M', 5)
            else:
                comm.send_data_over_radio('A', 5)
                lon = coords['longitude']
                lat = coords['latitude']
                comm.send_data_over_radio(f'lon:{lon},lat:{lat}', 100)
            millis = time_ms()

        while True:
            tmp = comm.read_data_over_radio()
            if(tmp != None):
                read_data.append(tmp)
            else:
                break
        
        deserializer.deserialize(read_data)

        while not communicates.empty():
            tmp = communicates.get()
            comm.send_data_over_radio(tmp['payload'], tmp['type'])

        if(refresh_gui):
            comm_pipe_to_gui.send({'comm_refresh_request' : states})
            refresh_gui = False
            pass
        
        if(comm_pipe_to_gui.poll(0.001)):
            tmp = comm_pipe_to_gui.recv()
            if('EXIT' in tmp['gui_requests']):
                comm_pipe_to_joy.send('EXIT')
                controller_process.join()
                comm.close_radio_connection()
                break

            elif('manual' in tmp['gui_requests']):
                mode = 'man'
            
            elif('auto' in tmp['gui_requests']):
                mode = 'auto'
                coords['latitude'] = float(tmp['gui_requests'][1])
                coords['longitude'] = float(tmp['gui_requests'][2])
                print(coords)

        if(comm_pipe_to_joy.poll(0.005)):
            tmp = comm_pipe_to_joy.recv()
            for p in tmp:
                if(mode == 'man'):
                    print(f'{p.message}, {p.message_type}')
                else:
                    pass
        
        # if(time_ms() - com_timeout < 5000):
        #     comm_pipe_to_gui.send({'comm_status_refresh' : 'green'})
        # else:
        #     comm_pipe_to_gui.send({'comm_status_refresh' : 'red'})

run_com()