from ast import While
from multiprocessing import Process, Pipe
from os import kill
from threading import Thread, Semaphore
from turtle import update
import PySimpleGUI as sg

kill_all_threads = False

sg.theme('light blue 5')

class CruiseManager:
    def main(this, sem : Semaphore):
        global kill_all_threads
        while True:
            sem.acquire()
            if(kill_all_threads):
                break
            print("acquired sem in CruiseManager")

class DiagManager:
    def main(this, sem : Semaphore):
        global kill_all_threads
        while True:
            sem.acquire()
            if(kill_all_threads):
                break
            print("Acquired sem in DiagManager")

class ModeManager:
    def main(this, sem : Semaphore):
        global kill_all_threads 
        while True:
            sem.acquire()
            if(kill_all_threads):
                break
            print("Acquired sem in ModeManager")

def get_text(txt : str, key : str):
    return sg.Text(txt, key=key)

def change_text(wnd : sg.Window, key : str, txt : str):
    wnd[key].Update(text=txt)

def get_combo(items : list, size : tuple, key : str):
    return sg.Combo(items, size=size, key=key, readonly=True)

def update_combo_content(wnd : sg.Window, items : list, key : str):
    wnd[key].Update(values=items)

def get_radio(txt : str, key : str, checked : bool):
    return sg.Radio(txt, key, checked)

def get_button(txt : str, key : str):
    return sg.Button(txt, key=key)


class UserInterface:
    update_cruise_data = Semaphore(1)
    update_diag_data = Semaphore(1)
    update_mode = Semaphore(1)

    layout = dict()

    def run(this, pipe_to_comm, args):
        global kill_all_threads

        this.layout['init'] = [[get_text('Choose the radio port:', key='Header_text')],
          [get_combo(args[0], (15, 1), 'radio_sel')],
          [sg.Combo(args[1], key='joystick_sel1', readonly=True ,size=(15, 1))],
          [sg.Radio("Manual operation", 'operation_type', True), sg.Radio("Automatic operation", 'operation_type')],
          [sg.Button('Refresh'), sg.OK()],
          [sg.Image('./lrt_logo.png'), sg.Image('./weii_ang.png')]          
        ]


        this.wnd = sg.Window('Operating station rev. 0.1.', this.layout['init'], element_justification='c')

        this.mode_mgr = ModeManager()
        this.cruise_mgr = CruiseManager()
        this.diag_mgr = DiagManager()

        mode_mgr_thread = Thread(target=this.mode_mgr.main, args=(this.update_mode,))
        cruise_mgr_thread = Thread(target=this.cruise_mgr.main, args=(this.update_cruise_data,))
        diag_mgr_thread = Thread(target=this.diag_mgr.main, args=(this.update_diag_data,))

        for sem in [this.update_cruise_data, this.update_diag_data, this.update_mode]:
            sem.acquire()

        mode_mgr_thread.start()
        cruise_mgr_thread.start()
        diag_mgr_thread.start()

        while True:
            event, values = this.wnd.read()
            print(event)
            
            if event in ('Quit', sg.WIN_CLOSED):
                break
            elif event == 'Refresh':
                pipe_to_comm.send([['get_ports']])
                tmp = pipe_to_comm.recv()
                this.wnd['radio_sel'].Update(values=tmp[0])
                this.wnd['joystick_sel1'].Update(values=tmp[1])
            elif event == 'OK':
                for sem in [this.update_cruise_data, this.update_diag_data, this.update_mode]:
                    sem.release()
                dev = values['radio_sel']
                joy = values['joystick_sel1']
                pipe_to_comm.send([{'connect_radio': dev, 'connect_joystick' : joy}])
                tmp = pipe_to_comm.recv()
                if('radio_ok' in tmp):
                    sg.Popup(f'Connected with {dev}', keep_on_top=True)
                if('radio_nok' in tmp):
                    sg.Popup(f'Could not connect to {dev}', keep_on_top=True)

        for sem in [this.update_cruise_data, this.update_diag_data, this.update_mode]:
            sem.release()
        kill_all_threads = True
        mode_mgr_thread.join()
        cruise_mgr_thread.join()
        diag_mgr_thread.join()
        pipe_to_comm.send([['exit']])
        this.wnd.close()
