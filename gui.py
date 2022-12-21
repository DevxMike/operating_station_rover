from multiprocessing import Process, Pipe
from threading import Thread, Semaphore
from turtle import home
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

home_coords = {
    'longitude' : 0.0,
    'latitude'  : 0.0
}

class UserInterface:
    layout = dict()

    devices_connected = False

    def run(this, pipe_to_comm, args):
        global home_coords

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
          [sg.Button('Set home', key='save_coords'), sg.Button('Emergency Stop', key='stop_rover')],
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
            
            if('save_coords' in event):
                home_coords['longitude'] = float(this.table_values['longitude'])
                home_coords['latitude'] = float(this.table_values['latitude'])

            if('stop_rover' in event):
                pipe_to_comm.send({'gui_requests' : ['auto', home_coords['latitude'], home_coords['longitude']]})
                this.wnd['in_latitude'].update(disabled = False)
                this.wnd['in_longitude'].update(disabled = False)
                this.wnd['auto'].update(value = True)
                this.wnd['in_latitude'].update(value = home_coords['latitude'])
                this.wnd['in_longitude'].update(value = home_coords['longitude'])


            if(pipe_to_comm.poll(0.005)):
                tmp = pipe_to_comm.recv()
                if('comm_refresh_request' in tmp):
                    diag = tmp['comm_refresh_request']['diag']
                    GPS = tmp['comm_refresh_request']['GPS']
                    IMU = tmp['comm_refresh_request']['IMU']
                    try:
                        diag = ''.join([chr(x) for x in diag])
                        GPS = ''.join([chr(x) for x in GPS])
                        IMU = ''.join([chr(x) for x in IMU])

                        diag = diag.split(',')
                        GPS = GPS.split(',')
                        IMU = IMU.split(',')
                        
                        this.table_values['latitude'] = float(GPS[1][5:len(GPS[1])])
                        this.table_values['longitude'] = float(GPS[0][4:len(GPS[0])])
                        this.table_values['yaw'] = float(IMU[0][2:len(IMU[0])])
                        this.table_values['pitch'] = float(IMU[1][2:len(IMU[1])])
                        this.table_values['roll'] = float(IMU[2][2:len(IMU[2])])
                        this.table_values['AUTO'] = diag[0][len(diag[0]) - 1]
                        this.table_values['IMU_OK'] = diag[1][len(diag[1]) - 1]
                        this.table_values['GPS_OK'] = diag[2][len(diag[2]) - 1]
                        this.table_values['USB_OK'] = diag[3][len(diag[3]) - 1]
                        this.table_values['PWR_OK'] = diag[4][len(diag[4]) - 3]

                        this.wnd['param_table'].update(values=[[[k], [v]] for k, v in this.table_values.items()])
                        print(f'{diag} {IMU} {GPS}')
                    except:
                        pass
        
        this.wnd.close()

# UserInterface().run(None, None)