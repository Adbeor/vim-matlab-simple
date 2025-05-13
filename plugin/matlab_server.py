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
        try:
            if use_pexpect:
                self.proc = pexpect.spawn("matlab", ["-nosplash", "-nodesktop"])
            else:
                self.proc = Popen(["matlab", "-nosplash", "-nodesktop"], stdin=PIPE,
                                close_fds=True, preexec_fn=os.setsid)
            logger.info("Matlab process started successfully")
            return self.proc
        except Exception as ex:
            logger.error(f"Error launching Matlab process: {ex}")
            print_flush(f"Error launching Matlab: {ex}")
            return None

    def cancel(self):
        """Send interrupt signal to Matlab."""
        try:
            os.kill(self.proc.pid, signal.SIGINT)
            logger.info("Interrupt signal sent to Matlab")
        except Exception as ex:
            logger.error(f"Error sending interrupt to Matlab: {ex}")

    def kill(self):
        """Kill the Matlab process."""
        try:
            if hasattr(self, 'proc') and self.proc:
                os.killpg(self.proc.pid, signal.SIGTERM)
                logger.info("Matlab process terminated")
        except Exception as ex:
            # Silently ignore errors when killing non-existent process
            logger.debug(f"Error killing Matlab process: {ex}")

    def run_code(self, code, run_timer=True):
        """Encolar código para ejecutar en Matlab."""
        # Preparar el comando
        command = self._prepare_command(code, run_timer)
        # Encolar el comando
        command_queue.put(command)
        logger.info(f"Enqueued code: {code[:100]}...")

    def run_cell(self, cell_code):
        """Run a Matlab cell block."""
        # Verificar si hay contenido para ejecutar
        if not cell_code or cell_code.strip() == '':
            logger.warning("Empty cell content, nothing to execute")
            return
            
        # Eliminar los marcadores de celda %% si están presentes
        if cell_code.strip().startswith('%%'):
            lines = cell_code.split('\n')
            if lines:
                # Eliminar el marcador %% de la primera línea
                first_line = lines[0].strip()
                if first_line.startswith('%%'):
                    clean_first = first_line[2:].lstrip()
                    if clean_first:
                        lines[0] = clean_first
                    else:
                        lines = lines[1:]
            cell_code = '\n'.join(lines)
        
        # Ejecutar como código normal pero sin timer para celdas
        self.run_code(cell_code, run_timer=False)
        logger.info(f"Running cell: {cell_code[:100]}...")

    def run_file(self, filepath):
        """Run a complete MATLAB file."""
        # Strip any quotes that might be around the path
        filepath = filepath.strip("'\"")
        
        # Verificar que el archivo existe
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            print_flush(f"Error: File not found: {filepath}")
            return
        
        # Create the MATLAB command to run the file
        # Using 'run' instead of direct execution to maintain context
        code = f"run('{filepath}');"
        
        # Run the command without timing for files
        self.run_code(code, run_timer=False)
        logger.info(f"Running MATLAB file: {filepath}")

    def _prepare_command(self, code, run_timer=True):
        """Prepara el comando para enviar a Matlab."""
        # Asegurar que el código no esté vacío
        if not code or code.strip() == '':
            return "\n"  # Devolver una nueva línea para evitar bloqueos
            
        if run_timer:
            # Generar un nombre de variable aleatorio para el temporizador
            rand_var = ''.join(random.choice(string.ascii_uppercase) for _ in range(12))
            command = ("{randvar}=tic;{code},try,toc({randvar}),catch,end"
                      ",clear('{randvar}');\n").format(randvar=rand_var,
                                                    code=code.strip())
        else:
            command = "{}\n".format(code.strip())

        # The maximum number of characters allowed on a single line in Matlab's CLI is 4096.
        delim = ' ...\n'
        line_size = 4095 - len(delim)
        
        # Dividir comandos largos en múltiples líneas
        if len(command) > line_size:
            parts = []
            for i in range(0, len(command), line_size):
                parts.append(command[i:i+line_size])
            command = delim.join(parts)
        
        # Asegurar que el comando termina con nueva línea
        if not command.endswith('\n'):
            command += '\n'
            
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
                    if not command.endswith('\n'):
                        command += '\n'
                    self.proc.stdin.write(command.encode('utf-8'))
                    self.proc.stdin.flush()  # Asegurar que el comando se envía inmediatamente
                logger.info("Command sent to Matlab successfully")
                break
            except Exception as ex:
                logger.error(f"Error sending command to Matlab: {ex}")
                # Si falla el envío, intentar relanzar el proceso
                if num_retry < 2:  # Solo reiniciar si no es el último intento
                    logger.info("Attempting to restart Matlab process...")
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
                    logger.info("Empty message received, ending connection")
                    break
                    
                # Decodificar bytes a string
                try:
                    msg = msg.decode('utf-8').strip()
                except UnicodeDecodeError:
                    logger.error("Error decoding message, invalid UTF-8")
                    continue
                
                # Logging con límite de tamaño para mensajes largos
                log_msg = (msg[:74] + '...') if len(msg) > 74 else msg
                logger.info(f"Received: {log_msg}")
                print_flush(log_msg, end='')

                # Procesar mensaje
                self._process_message(msg)
                
            except ConnectionError as ex:
                logger.error(f"Connection error: {ex}")
                break
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
            # Verificar si el proceso de Matlab está activo
            if use_pexpect:
                exit_status = matlab.proc.exitstatus
                if exit_status is not None:
                    # Proceso terminado
                    if not auto_restart:
                        logger.info("Matlab process terminated and auto-restart disabled")
                        break
                    logger.info("Restarting Matlab process...")
                    print_flush("Restarting...")
                    matlab.launch_process()
                    start_thread(target=forward_input, args=(matlab,))
            else:
                if matlab.proc.poll() is not None:
                    # Proceso terminado
                    if not auto_restart:
                        logger.info("Matlab process terminated and auto-restart disabled")
                        break
                    logger.info("Restarting Matlab process...")
                    print_flush("Restarting...")
                    matlab.launch_process()
                    start_thread(target=forward_input, args=(matlab,))
                    
            time.sleep(0.5)  # Reduced wait time
        except Exception as ex:
            logger.error(f"Error in status monitor: {ex}")
            time.sleep(1)

    # Si salimos del bucle, el servidor debe cerrarse
    global server
    try:
        server.shutdown()
        server.server_close()
        logger.info("Server shutdown")
    except Exception as ex:
        logger.error(f"Error shutting down server: {ex}")


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
                # Leer línea de stdin
                line = stdin.readline()
                if not line:  # EOF
                    logger.info("EOF detected in stdin")
                    break
                
                # Codificar la línea a bytes antes de escribirla
                matlab.proc.stdin.write(line.encode('utf-8'))
                matlab.proc.stdin.flush()  # Asegurar que la entrada se procesa inmediatamente
            except BrokenPipeError:
                logger.error("Broken pipe in forward_input")
                break
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
    try:
        sys.stdout.write(value + end)
        sys.stdout.flush()
    except Exception as ex:
        logger.error(f"Error in print_flush: {ex}")


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
    except OSError as ex:
        if "Address already in use" in str(ex):
            logger.error(f"Port {port} already in use. Is the server already running?")
            print_flush(f"Error: Port {port} already in use. Is the server already running?")
        else:
            logger.error(f"OS error starting server: {ex}")
            print_flush(f"Error starting server: {ex}")
        sys.exit(1)
    except Exception as ex:
        logger.error(f"Error starting server: {ex}")
        print_flush(f"Error starting server: {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
