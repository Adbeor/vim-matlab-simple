"""
Simplified Matlab CLI Controller for Vim
This module provides a simple interface to interact with Matlab via a TCP socket.
"""

import socket
import time
import os
from threading import Timer


class MatlabCliController:
    """Controller for interacting with Matlab through TCP."""
    def __init__(self):
        self.host, self.port = "localhost", 43889
        self.connect_to_server()

    def connect_to_server(self):
        """Connect to the Matlab server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            print("Connected to Matlab server")
        except socket.error as e:
            print(f"Failed to connect to Matlab server: {e}")
            print("Make sure the server is running with: python matlab_server.py")  # Corregido el nombre del archivo
            raise

    def run_code(self, lines):
        """Send code to be executed in Matlab."""
        code = ','.join(lines)

        num_retry = 0
        while num_retry < 3:
            try:
                self.sock.sendall((code + "\n").encode('utf-8'))
                print(f"Sent to Matlab: {code}")
                break
            except Exception as ex:
                print(f"Error sending code to Matlab: {ex}")
                self.connect_to_server()
                num_retry += 1
                time.sleep(1)

    def run_file(self, filepath):
        """Run a complete MATLAB file."""
        filepath = os.path.abspath(filepath)  # Convertir a ruta absoluta
        command = f"run_file:{filepath}"
        
        num_retry = 0
        while num_retry < 3:
            try:
                self.sock.sendall((command + "\n").encode('utf-8'))
                print(f"Sent run file command to Matlab: {filepath}")
                break
            except Exception as ex:
                print(f"Error sending run file command to Matlab: {ex}")
                self.connect_to_server()
                num_retry += 1
                time.sleep(1)

    def setup_matlab_path(self, path=None):
        """Add path to Matlab's path."""
        if path is None:
            # Use current directory as default
            path = os.path.abspath(os.path.dirname(__file__))
            
        self.run_code([f"addpath('{path}');"])
        print(f"Added to Matlab path: {path}")

    def open_in_matlab_editor(self, path):
        """Open a file in Matlab editor."""
        self.run_code([f"edit '{path}';"])

    def help_command(self, name):
        """Get help for a Matlab function/variable."""
        self.run_code([f"help {name};"])

    def send_ctrl_c(self):
        """Send cancel command to Matlab."""
        self.sock.sendall(b"cancel\n")
        print("Cancel command sent to Matlab")
        
    def close(self):
        """Close the connection to Matlab server."""
        try:
            self.sock.close()
            print("Connection to Matlab server closed")
        except:
            pass


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
