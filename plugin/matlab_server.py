#!/usr/bin/env python3

"""
Optimized Matlab Server for Vim
This script launches Matlab and sets up a TCP server to communicate with Vim.
"""

import socketserver
import os
import random
import signal
import string
import sys
import threading
import time
from sys import stdin
import queue
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='matlab_server.log',
    filemode='a'
)
logger = logging.getLogger('matlab_server')

# Try to use pexpect for better interaction with Matlab
try:
    import pexpect
    use_pexpect = True
except ImportError:
    use_pexpect = False
    from subprocess import Popen, PIPE

hide_until_newline = False
auto_restart = True
server = None

# Cola de comandos para optimizar el envío de múltiples comandos
command_queue = queue.Queue()


class Matlab:
    """Handles the Matlab process and communication."""
    def __init__(self):
        self.launch_process()
        self.command_lock = threading.Lock()  # Lock para sincronizar acceso
        # Iniciar el procesador de comandos
        self._start_command_processor()

    def _start_command_processor(self):
        """Inicia un hilo para procesar comandos de la cola."""
        def process_commands():
            while True:
                try:
                    command = command_queue.get(timeout=0.5)
                    with self.command_lock:
                        self._execute_command(command)
                    command_queue.task_done()
                except queue.Empty:
                    time.sleep(0.01)  # Pequeña pausa cuando no hay comandos
                except Exception as ex:
                    logger.error(f"Error processing command: {ex}")
                    time.sleep(0.1)  # Pausa en caso de error
        
        # Iniciar hilo
        cmd_thread = threading.Thread(target=process_commands)
        cmd_thread.daemon = True
        cmd_thread.start()

    def launch_process(self):
        """Start the Matlab process."""
        self.kill()
        if use_pexpect:
            self.proc = pexpect.spawn("matlab", ["-nosplash", "-nodesktop"])
        else:
            self.proc = Popen(["matlab", "-nosplash", "-nodesktop"], stdin=PIPE,
                             close_fds=True, preexec_fn=os.setsid)
        return self.proc

    def cancel(self):
        """Send interrupt signal to Matlab."""
        os.kill(self.proc.pid, signal.SIGINT)

    def kill(self):
        """Kill the Matlab process."""
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except:
            pass

    def run_code(self, code, run_timer=True):
        """Encolar código para ejecutar en Matlab."""
        # Preparar el comando
        command = self._prepare_command(code, run_timer)
        # Encolar el comando
        command_queue.put(command)
        logger.info(f"Enqueued code: {code[:100]}...")

    def run_cell(self, cell_code):
        """Run a Matlab cell block."""
        # Eliminar los marcadores de celda %% si están presentes
        if cell_code.startswith('%%'):
            cell_code = cell_code[2:].lstrip()
        
        # Ejecutar como código normal pero sin timer para celdas
        self.run_code(cell_code, run_timer=False)
        logger.info(f"Running cell: {cell_code[:100]}...")

    def run_file(self, filepath):
        """Run a complete MATLAB file."""
        # Strip any quotes that might be around the path
        filepath = filepath.strip("'\"")
        
        # Create the MATLAB command to run the file
        code = f"run('{filepath}');"
        
        # Run the command without timing for files
        self.run_code(code, run_timer=False)
        logger.info(f"Running MATLAB file: {filepath}")

    def _prepare_command(self, code, run_timer=True):
        """Prepara el comando para enviar a Matlab."""
        if run_timer:
            rand_var = ''.join(random.choice(string.ascii_uppercase) for _ in range(12))
            command = ("{randvar}=tic;{code},try,toc({randvar}),catch,end"
                      ",clear('{randvar}');\n").format(randvar=rand_var,
                                                    code=code.strip())
        else:
            command = "{}\n".format(code.strip())

        # The maximum number of characters allowed on a single line in Matlab's CLI is 4096.
        delim = ' ...\n'
        line_size = 4095 - len(delim)
        command = delim.join([command[i:i+line_size] for i in range(0, len(command), line_size)])
        
        return command

    def _execute_command(self, command):
        """Ejecuta el comando preparado en Matlab."""
        global hide_until_newline
        num_retry = 0
        
        while num_retry < 3:
            try:
                if use_pexpect:
                    hide_until_newline = True
                    self.proc.send(command)
                else:
                    # Convertir a bytes antes de escribir
                    self.proc.stdin.write(command.encode('utf-8'))
                    self.proc.stdin.flush()
                break
            except Exception as ex:
                logger.error(f"Error sending command to Matlab: {ex}")
                self.launch_process()
                num_retry += 1
                time.sleep(0.2)  # Reducido tiempo de espera


class TCPHandler(socketserver.StreamRequestHandler):
    """Handle TCP connections from Vim."""
    def handle(self):
        logger.info(f"New connection: {self.client_address}")
        print_flush(f"New connection: {self.client_address}")

        while True:
            try:
                msg = self.rfile.readline()
                if not msg:
                    break
                msg = msg.decode('utf-8').strip()  # Decodificar bytes a string
                
                # Logging con límite de tamaño para mensajes largos
                log_msg = (msg[:74] + '...') if len(msg) > 74 else msg
                logger.info(f"Received: {log_msg}")
                print_flush(log_msg, end='')

                # Procesar mensaje
                self._process_message(msg)
                
            except Exception as ex:
                logger.error(f"Error handling message: {ex}")
        
        logger.info(f'Connection closed: {self.client_address}')
        print_flush(f'Connection closed: {self.client_address}')

    def _process_message(self, msg):
        """Procesa el mensaje recibido."""
        options = {
            'kill': self.server.matlab.kill,
            'cancel': self.server.matlab.cancel,
        }
        
        # Verificar tipo de comando
        if msg.startswith('run_file:'):
            filepath = msg[9:]  # Extraer la ruta del archivo después de 'run_file:'
            self.server.matlab.run_file(filepath)
        elif msg.startswith('run_cell:'):
            cell_code = msg[9:]  # Extraer código después de 'run_cell:'
            self.server.matlab.run_cell(cell_code)
        elif msg in options:
            options[msg]()
        else:
            self.server.matlab.run_code(msg)


def status_monitor_thread(matlab):
    """Monitor Matlab process and restart if needed."""
    while True:
        try:
            matlab.proc.wait()
            if not auto_restart:
                break
            logger.info("Restarting Matlab process...")
            print_flush("Restarting...")
            matlab.launch_process()
            start_thread(target=forward_input, args=(matlab,))
            time.sleep(0.5)  # Reduced wait time
        except Exception as ex:
            logger.error(f"Error in status monitor: {ex}")
            time.sleep(1)

    global server
    server.shutdown()
    server.server_close()
    logger.info("Server shutdown")


def output_filter(output_string):
    """
    Filter output from Matlab to hide commands.
    Used with pexpect to filter the output.
    """
    global hide_until_newline
    if hide_until_newline:
        if '\n' in output_string:
            hide_until_newline = False
            return output_string[output_string.find('\n'):]
        else:
            return ''
    else:
        return output_string


def input_filter(input_string):
    """Filter input to detect control sequences."""
    # Detect C-\
    if input_string == '\x1c':
        logger.info("Terminating server")
        print_flush('Terminating')
        global auto_restart
        auto_restart = False
    return input_string


def forward_input(matlab):
    """Forward stdin to Matlab's stdin."""
    if use_pexpect:
        matlab.proc.interact(input_filter=input_filter, output_filter=output_filter)
    else:
        while True:
            try:
                # Codificar la línea a bytes antes de escribirla
                line = stdin.readline()
                matlab.proc.stdin.write(line.encode('utf-8'))
            except Exception as ex:
                logger.error(f"Error in forward_input: {ex}")
                time.sleep(0.2)


def start_thread(target=None, args=()):
    """Start a daemon thread."""
    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    thread.start()
    return thread


def print_flush(value, end='\n'):
    """Print and flush stdout."""
    if use_pexpect:
        value += '\b' * len(value)
    sys.stdout.write(value + end)
    sys.stdout.flush()


def main():
    """Main function to start the server."""
    host, port = "localhost", 43889
    socketserver.TCPServer.allow_reuse_address = True

    global server
    logger.info(f"Starting server on {host}:{port}")
    
    try:
        server = socketserver.TCPServer((host, port), TCPHandler)
        server.matlab = Matlab()

        start_thread(target=forward_input, args=(server.matlab,))
        start_thread(target=status_monitor_thread, args=(server.matlab,))

        print_flush(f"Started server: {(host, port)}")
        server.serve_forever()
    except Exception as ex:
        logger.error(f"Error starting server: {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
