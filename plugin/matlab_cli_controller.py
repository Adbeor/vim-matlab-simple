"""
Corrected Matlab CLI Controller for Vim
This module provides a robust interface to interact with Matlab via a TCP socket.
"""

import socket
import time
import os
import logging
import threading
import queue
import re

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='matlab_controller.log',
    filemode='a'
)
logger = logging.getLogger('matlab_controller')

# Cola para enviar comandos
command_queue = queue.Queue()


class MatlabCliController:
    """Controller for interacting with Matlab through TCP."""
    def __init__(self):
        self.host, self.port = "localhost", 43889
        self.sock = None
        self.connected = False
        self.connect_lock = threading.Lock()
        self.connect_to_server()
        
        # Iniciar un hilo para procesar comandos
        self._start_command_processor()

    def _start_command_processor(self):
        """Inicia un hilo para procesar comandos de la cola."""
        def process_commands():
            while True:
                try:
                    command, args = command_queue.get(timeout=0.5)
                    if command == 'run_code':
                        self._send_code(args)
                    elif command == 'run_file':
                        self._send_run_file(args)
                    elif command == 'run_cell':
                        self._send_cell(args)
                    elif command == 'ctrl_c':
                        self._send_ctrl_c()
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

    def connect_to_server(self):
        """Connect to the Matlab server."""
        with self.connect_lock:
            if self.connected:
                return True
                
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.sock.connect((self.host, self.port))
                self.connected = True
                logger.info("Connected to Matlab server")
                print("Connected to Matlab server")
                return True
            except socket.error as e:
                self.connected = False
                logger.error(f"Failed to connect to Matlab server: {e}")
                print(f"Failed to connect to Matlab server: {e}")
                print("Make sure the server is running with: python matlab_server.py")
                return False

    def run_code(self, lines):
        """Send code to be executed in Matlab."""
        if isinstance(lines, list):
            code = '; '.join(lines)
        else:
            code = str(lines)
        
        # Encolar el comando
        command_queue.put(('run_code', code))
        logger.info(f"Enqueued code: {code[:50]}...")

    def _send_code(self, code):
        """Envía código a MATLAB (método interno)."""
        num_retry = 0
        while num_retry < 3:
            try:
                if not self.connected and not self.connect_to_server():
                    num_retry += 1
                    time.sleep(0.2)
                    continue
                
                # Asegurar que termina con salto de línea
                if not code.endswith("\n"):
                    code += "\n"
                
                self.sock.sendall(code.encode('utf-8'))
                logger.info(f"Sent to Matlab: {code[:50]}...")
                break
            except Exception as ex:
                logger.error(f"Error sending code to Matlab: {ex}")
                self.connected = False
                if not self.connect_to_server():
                    time.sleep(0.2)
                num_retry += 1

    def run_cell(self, cell_content):
        """Run a Matlab cell (code block starting with %%)."""
        # CORRECCIÓN: Procesar adecuadamente el contenido de la celda
        lines = cell_content.split('\n')
        
        # Filtrar líneas vacías y comentarios de celda
        cleaned_lines = []
        for line in lines:
            # Omitir líneas de celda %%
            if line.strip() and not re.match(r'^\s*%%', line):
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            logger.warning("Cell is empty after removing comments")
            print("Cell is empty after removing comments")
            return
        
        # Unir las líneas procesadas y enviar como contenido de celda
        code = '\n'.join(cleaned_lines)
        command_queue.put(('run_cell', code))
        logger.info(f"Enqueued cell: {code[:50]}...")

    def _send_cell(self, cell_content):
        """Envía una celda de código a MATLAB (método interno)."""
        # CORRECCIÓN: Asegurar que se envía correctamente el contenido de la celda
        # El servidor debe recibir un mensaje identificable como celda
        command = f"run_cell:{cell_content}"
        num_retry = 0
        while num_retry < 3:
            try:
                if not self.connected and not self.connect_to_server():
                    num_retry += 1
                    time.sleep(0.2)
                    continue
                
                # Asegurar que termina con salto de línea
                if not command.endswith("\n"):
                    command += "\n"
                    
                self.sock.sendall(command.encode('utf-8'))
                logger.info(f"Sent cell to Matlab: {cell_content[:50]}...")
                break
            except Exception as ex:
                logger.error(f"Error sending cell to Matlab: {ex}")
                self.connected = False
                if not self.connect_to_server():
                    time.sleep(0.2)
                num_retry += 1

    def run_file(self, filepath):
        """Run a complete MATLAB file."""
        # CORRECCIÓN: Validar que el archivo existe antes de enviarlo
        filepath = os.path.abspath(filepath)  # Convertir a ruta absoluta
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            print(f"Error: File not found: {filepath}")
            return
            
        command_queue.put(('run_file', filepath))
        logger.info(f"Enqueued run file: {filepath}")

    def _send_run_file(self, filepath):
        """Envía comando para ejecutar archivo (método interno)."""
        # CORRECCIÓN: Asegurar que se envía correctamente la ruta del archivo
        command = f"run_file:{filepath}"
        
        num_retry = 0
        while num_retry < 3:
            try:
                if not self.connected and not self.connect_to_server():
                    num_retry += 1
                    time.sleep(0.2)
                    continue
                
                # Asegurar que termina con salto de línea
                if not command.endswith("\n"):
                    command += "\n"
                    
                self.sock.sendall(command.encode('utf-8'))
                logger.info(f"Sent run file command to Matlab: {filepath}")
                break
            except Exception as ex:
                logger.error(f"Error sending run file command to Matlab: {ex}")
                self.connected = False
                if not self.connect_to_server():
                    time.sleep(0.2)
                num_retry += 1

    def setup_matlab_path(self, path=None):
        """Add path to Matlab's path."""
        if path is None:
            # Use current directory as default
            path = os.path.abspath(os.path.dirname(__file__))
            
        self.run_code([f"addpath('{path}');"])
        logger.info(f"Added to Matlab path: {path}")

    def open_in_matlab_editor(self, path):
        """Open a file in Matlab editor."""
        self.run_code([f"edit '{path}';"])

    def help_command(self, name):
        """Get help for a Matlab function/variable."""
        self.run_code([f"help {name};"])

    def send_ctrl_c(self):
        """Send cancel command to Matlab."""
        command_queue.put(('ctrl_c', None))
        logger.info("Enqueued cancel command")

    def _send_ctrl_c(self):
        """Envía comando de cancelación (método interno)."""
        try:
            if not self.connected and not self.connect_to_server():
                logger.error("Cannot send Ctrl+C: not connected")
                return
                
            self.sock.sendall(b"cancel\n")
            logger.info("Cancel command sent to Matlab")
        except Exception as ex:
            logger.error(f"Error sending cancel command: {ex}")
            self.connected = False
        
    def close(self):
        """Close the connection to Matlab server."""
        try:
            if self.sock:
                self.sock.close()
                self.connected = False
                logger.info("Connection to Matlab server closed")
        except Exception as ex:
            logger.error(f"Error closing connection: {ex}")


# Example usage
if __name__ == "__main__":
    controller = MatlabCliController()
    try:
        # Run a simple Matlab command
        controller.run_code(["disp('Hello from Matlab!');"])
        # Wait for a bit to see the output
        time.sleep(1)
    finally:
        controller.close()
