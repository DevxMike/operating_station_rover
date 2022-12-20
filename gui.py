from multiprocessing import Process, Pipe
from threading import Thread, Semaphore
import PySimpleGUI as sg

kill_all_threads = False

sg.theme('light blue 5')

def LEDIndicator(key=None, radius=30):
    return sg.Graph(canvas_size=(radius, radius),
             graph_bottom_left=(-radius, -radius),
             graph_top_right=(radius, radius),
             pad=(0, 0), key=key)

def SetLED(window, key, color):
    graph = window[key]
    graph.erase()
    graph.draw_circle((0, 0), 20, fill_color=color, line_color=color)

import time

class UserInterface:
    update_cruise_data = Semaphore(1)
    update_diag_data = Semaphore(1)
    update_mode = Semaphore(1)

    layout = dict()

    devices_connected = False

    def run(this, pipe_to_comm, args):
        global kill_all_threads
        headings = ['vehicle param', 'value']
        this.table_values = {
            'latitude' : 0,
            'longitude': 0,
            'roll'     : 0,
            'yaw'      : 0,
            'pitch'    : 0,
            'AUTO'     : 0,
            'IMU_OK'   : 0,
            'GPS_OK'   : 0,
            'USB_OK'   : 0,
            'PWR_OK'   : 0
        }

        popup_layout = [
          [sg.Text('Choose radio and joystick')],
          [sg.Combo(args[0], size=(15, 1), key='radio_sel')],
          [sg.Combo(args[1], size=(15, 1), key='joystick_sel')],
          [sg.Button('Refresh', key='refresh'), sg.Button('Accept', key='accept'), sg.Button('Exit', key='exit')]
        ]
        # sg.popup(popup_layout, title='Radio and joystick', )
        popup_wnd = sg.Window('Select radio and joystick', popup_layout, element_justification='r')
        
        vals_from_popup = {}

        while True:
            event, values = popup_wnd.read(timeout = 50)
            # print(event)
            # print(values)
                # vals_from_popup.append(values)
            if(pipe_to_comm.poll(0.001)):
                tmp = pipe_to_comm.recv()
                radio = tmp['radio']
                joy = tmp['joystick']
                popup_wnd['radio_sel'].update(values=radio)
                popup_wnd['joystick_sel'].update(values=joy)

            if event in ('Quit', sg.WIN_CLOSED, 'exit'):
                return -1
            elif event == 'accept':
                vals_from_popup = values
                pipe_to_comm.send({'gui_requests' : ['connect'], 'params' : [vals_from_popup['radio_sel'], vals_from_popup['joystick_sel']]})
                break
            elif event == 'refresh':
                pipe_to_comm.send({'gui_requests' : ['refresh']})
                # logic to refresh the list
        
        popup_wnd.close()

        # print(type(vals_from_popup))
        rs = vals_from_popup['radio_sel']
        js = vals_from_popup['joystick_sel']

        this.layout['init'] = [
          [sg.Radio("Manual operation", 'operation_type', default = 'True', key='manual'), sg.Radio("Automatic operation", 'operation_type', key='auto')],
          [sg.Text('latitude'), sg.Input(size=(20, 1), key='in_latitude', disabled=True)],
          [sg.Text('longitude'), sg.Input(size=(20, 1), key='in_longitude', disabled=True)],
          [sg.Button('Submit', key='sub_mode')],
          [sg.Table(values=[[[k], [v]] for k, v in this.table_values.items()], headings=headings, key='param_table', justification='left')],
          [sg.Button('Emergency Stop', key='stop_rover')],
          [sg.Text('Connection status'), LEDIndicator('con_stat', 30)],
          [sg.Text(f'Radio: {rs[0]}')],
          [sg.Text(f'Joystick: {js[0]}')],
          [sg.Image('./lrt_logo.png'), sg.Image('./weii_ang.png')]
        ]

        this.wnd = sg.Window('Operating station rev. 0.1.', this.layout['init'], element_justification='r')

        
        while True:
            event, values = this.wnd.read(timeout = 50)
            print(event)
            # print(event)
            SetLED(this.wnd, 'con_stat', 'red')
            if event in ('Quit', sg.WIN_CLOSED):
                pipe_to_comm.send({'gui_requests' : ['EXIT']})
                break
            if(values['manual'] == True):
                this.wnd['in_latitude'].update(disabled = True)
                this.wnd['in_longitude'].update(disabled = True)
            elif(values['auto'] == True):
                this.wnd['in_latitude'].update(disabled = False)
                this.wnd['in_longitude'].update(disabled = False)
            
            if('sub_mode' in event):
                if(values['manual'] == True):
                    pipe_to_comm.send({'gui_requests' : ['manual']})
                else:
                    pipe_to_comm.send({'gui_requests' : ['auto', values['in_latitude'], values['in_longitude']]})
        
        this.wnd.close()

# UserInterface().run(None, None)