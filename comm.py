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
import pynmea2

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
                try:
                    tmp_crc = (sum([ord(c) for c in str(bytes(self.payload), 'utf-8')]) + len(self.payload)) % 256
                    if(tmp_crc == self.crc):
                        self.callback(self.message_type, self.payload)
                except:
                    pass
                
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
            this.radio = serial.Serial(this.devices[name], 38400)
            this.radio_alive = True
            return True
        except:
            return False

        
    
    def send_data_over_radio(this, data, type):
        try:
            packet = Packet(type, data).get_packet()
            this.radio.write(code_decode(packet))
        except Exception as e:
            print(e)

    def read_data_over_radio(this):
        try:
            for i in range(50):
                if(this.radio.inWaiting() > 0):
                    return this.radio.read(1)
                else:
                    pass
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
# com_timeout = time_ms()

states = {
    'diag' : [],
    'GPS'  : [],
    'IMU'  : []
}
refresh_gui = False

def translate_drive(data):
    ctrl = {
        'left' : 0,
        'right': 0,
        'cam'  : 0
    }

    tmp = data.split(',')
    if(len(tmp) == 1):
        ctrl['cam'] = int(tmp[0][1])
    elif(len(tmp) == 2):
        ctrl['left'] = int(tmp[0][1:]) * 1000
        ctrl['right'] = int(tmp[1]) * 1000 

        if(ctrl['left'] > 0):
            ctrl['left'] -= 1
        if(ctrl['right'] > 0):
            ctrl['right'] -= 1
        

    print(ctrl)
    return ctrl

values = {
            'actual_latitude' : 0,
            'actual_longitude': 0,
            'desired_latitude' : 0,
            'desired_longitude' : 0,
            'roll'     : 0,
            'yaw'      : 0,
            'pitch'    : 0,
            'LEFT'     : 0,
            'CENTER'   : 0,
            'RIGHT'    : 0
        }

def stringify(list_of_ints):
    return ''.join([chr(c) for c in list_of_ints])

def callback(type, payload):
    global communicates
    global states
    global refresh_gui
    global values
    # global com_timeout
    # print(payload)
    if(type == 0):
        communicates.put({'type' : 0, 'payload' : ''})
        # com_timeout = time_ms()
    
    elif(type == 7 or type == 2):
        states['diag'] = payload
        refresh_gui = True

    elif(type == 4):
        states['GPS'] = payload
        refresh_gui = True
        tmp = stringify(payload.copy())
        # print(tmp)
        try:
            tmp = tmp.split(',')
            # print(tmp)
            tmp2 = []
            for i in range(len(tmp)):
                tmp2.append(tmp[i].strip())
            # print(tmp2)
            # print(tmp2[1][5:len(tmp2)])
            lon = str(tmp2[0])
            lat = str(tmp2[1])
            print(lat[5:])
            print(lon[5:])
            lat = lat[5:]
            lon = lon[5:]
            values['actual_latitude'] = float(pynmea2.dm_to_sd(lat))
            values['actual_longitude'] = float(pynmea2.dm_to_sd(lon))
        except Exception as e: print(e)
        # print(payload)
    
    elif(type == 3):
        states['IMU'] = payload
        refresh_gui = True
        tmp = stringify(payload.copy())
        try:
            tmp = tmp.split(',')
            values['yaw'] = float(tmp[0][2:len(tmp[0])])
            values['pitch'] = float(tmp[1][2:len(tmp[1])])
            values['roll'] = float(tmp[2][2:len(tmp[2])])
        except Exception as e: print(e)

    elif(type == 102):
        print(stringify(payload))
        # print(payload)

def joystick_process(pipe, joystick):
    axes = [0.0] * joystick.get_numaxes()
    buttons = [False] * joystick.get_numbuttons()
    reg = regulator()

    while True:
        event = pygame.event.wait(30)
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
        # tmp = translate_drive(f'D,{int(u1_val)},{int(u2_val)}')
        # u1_val = tmp['left']
        # u2_val = tmp['right']
        # tmp1 = Packet(1, f'D,{int(u1_val)},{int(u2_val)}')
        # tmp = translate_drive(f'C,{int(hat_readings)}')
        # cam = tmp['cam']
        # tmp2 = Packet(1, f'C,{int(cam)}')
        coef = 0.4

        pwm_left = int(u1_val * 10 * coef)
        pwm_right = int(u2_val * 10 * coef)


        result = []


        result.append(Packet(101, f'L,{pwm_left},R,{pwm_right}'))

        flags = hat_readings

        if(flags & 8):
            result.append(Packet(101,'D,F')) # RIGHT
        if(flags & 4):
            result.append(Packet(101,'D,R')) # LEFT
        if(flags & 2):
            result.append(Packet(101,'S,+')) # UP
        if(flags & 1):
            result.append(Packet(101,'S,-')) # DOWN
        
        # print(result)
        pipe.send(result)
        if(pipe.poll(0.001)):
            tmp = pipe.recv()
            if('EXIT' in tmp):
                break
        # time.sleep(0.01)

mode = 'man'
millis = 0

import GPS
import fuzzy

coords = {
        'longitude' : 0,
        'latitude' : 0
    }

azimuth = GPS.azimuth()
distance = GPS.distance()
navi = fuzzy.navi()
navi_state = 0
course = 0

def run_com():
    global communicates
    global states
    global refresh_gui
    global mode
    global millis 
    global coords
    global values
    global navi
    global azimuth
    global distance
    global navi_state
    global course

    timeout = time_ms()
    i = 0

    comm = communication()
    joysticks = get_joysticks()
    ports = comm.get_ports()
    # user_interface = gui.UserInterface()
    comm_pipe_to_gui, gui_pipe = multiprocessing.Pipe()  
    gui_process = multiprocessing.Process(target=UserInterface().run, args=(gui_pipe,[[ports], [joysticks]]))
    comm_pipe_to_joy, joy_pipe = multiprocessing.Pipe()  
    
    gui_process.start()

    while True:
        if(comm_pipe_to_gui.poll(0.001)):
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
    # millis_timeout = time_ms()

    # 100 - coords
    # 101 - motors 
    while True:
        read_data = []

        if(time_ms() - millis > 700):
            # print(values)
            comm.send_data_over_radio('', 7)
            comm.send_data_over_radio('', 8)
            millis = time_ms()
            if(mode == 'man'):
                comm.send_data_over_radio('M', 5)
            else:
                comm.send_data_over_radio('A', 5)
                comm.send_data_over_radio('', 100)
                # lon = coords['longitude']
                # lat = coords['latitude']
                # comm.send_data_over_radio(f'{lon},{lat}', 100)
                try:
                    if(navi_state == 0):
                        course = azimuth(
                            (values['actual_latitude'], values['actual_longitude']),
                            (values['desired_latitude'], values['desired_longitude'])
                        ) 
                        navi_state = 1

                    elif(navi_state == 1):
                        THETA = (course - values['yaw']) % 180
                        Z = distance(
                            (values['actual_latitude'], values['actual_longitude']),
                            (values['desired_latitude'], values['desired_longitude'])
                        )

                    
                        print(f'Z:{Z}, diff:{THETA}, course:{course}')
                        left, right = navi.get_output(Z, THETA)
                        coef = 0.4
                        if(abs(THETA) > 30):
                            left = 60
                            right = -60
                        else:
                            left = 60
                            right = 60

                        if(Z <= 0.001):
                            left = right = 0
                        tmp = f'L,{int(left*10*coef)},R,{int(right*10*coef)}'
                        print(tmp)
                        comm.send_data_over_radio(tmp, 101)
                    


                except:
                    pass

            
        # if(time_ms() - millis_timeout > 5):
        #     millis_timeout = time_ms()
        #     if(time_ms() - com_timeout < 5000):
        #         comm_pipe_to_gui.send({'comm_status_refresh' : 'green'})
        #     else:
        #         comm_pipe_to_gui.send({'comm_status_refresh' : 'red'})

        while True:
            tmp = comm.read_data_over_radio()
            if(tmp != None):
                read_data.append(tmp)
            else:
                break
        
        deserializer.deserialize(read_data)

        while not communicates.empty():
            tmp = communicates.get_nowait()
            comm.send_data_over_radio(tmp['payload'], tmp['type'])

        if(refresh_gui):
            comm_pipe_to_gui.send({'comm_refresh_request' : states})
            refresh_gui = False
            pass
        
        if(comm_pipe_to_gui.poll(0.01)):
            tmp = comm_pipe_to_gui.recv()
            if('EXIT' in tmp['gui_requests']):
                comm_pipe_to_joy.send('EXIT')
                controller_process.join()
                comm.close_radio_connection()
                break

            elif('manual' in tmp['gui_requests']):
                mode = 'man'
            
            elif('auto' in tmp['gui_requests']):
                navi_state = 0
                mode = 'auto'
                values['desired_latitude'] = float(tmp['gui_requests'][1])
                values['desired_longitude'] = float(tmp['gui_requests'][2])
                # print(coords)

        if(comm_pipe_to_joy.poll(0.01)):
            # if(time_ms() - timeout > 5):
                tmp = comm_pipe_to_joy.recv()
                if i < 5:
                    i += 1
                else:
                    i = 0
                    for p in tmp:
                        if(mode == 'man'):
                            comm.send_data_over_radio(p.message, 101)
                            # print(f'{p.message}, {p.message_type}')
                        else:
                            pass
                # timeout = time_ms()
        

run_com()