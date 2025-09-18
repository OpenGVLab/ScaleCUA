import json
import socket
import time
import os
from typing import Any, Dict, List, Optional, Union
from contextlib import AbstractContextManager


class QMPConnection(AbstractContextManager):
    """Manages QMP socket connection lifecycle"""

    def __init__(self, host: str, qmp_port: int):
        self.host = host
        self.qmp_port = qmp_port
        self.sock = None

    def __enter__(self):
        """Establish connection to QMP and perform handshake"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # Add timeout for connection attempts
            self.sock.connect((self.host, self.qmp_port))

            # Read greeting
            greeting = self._read_response()
            if not greeting or "QMP" not in greeting:
                raise ConnectionError("Invalid QMP greeting received")

            # Execute capabilities negotiation
            response = self._send_command("qmp_capabilities")
            if "error" in response:
                raise ConnectionError(
                    f"QMP capabilities negotiation failed: {response['error']}"
                )

            return self

        except (socket.error, ConnectionError) as e:
            if self.sock:
                self.sock.close()
                self.sock = None
            raise ConnectionError(f"Failed to connect to QMP: {str(e)}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up socket connection"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def _send_command(
        self, command: str, arguments: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Send QMP command and return response

        Args:
            command: QMP command name
            arguments: Optional dict of command arguments

        Returns:
            Dict containing command response
        """
        if self.sock is None:
            raise ConnectionError("Not connected to QMP")

        cmd = {"execute": command}
        if arguments:
            cmd["arguments"] = arguments

        try:
            self.sock.send(json.dumps(cmd).encode("utf-8") + b"\n")
            return self._read_response()
        except socket.error as e:
            self.sock.close()
            self.sock = None
            raise ConnectionError(f"Failed to send command: {str(e)}")

    def _read_response(self) -> Dict[str, Any]:
        """Read and parse response from QMP socket

        Returns:
            Dict containing parsed JSON response
        """
        if self.sock is None:
            raise ConnectionError("Not connected to QMP")

        try:
            # Read data in chunks to handle partial messages
            chunks = []
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Connection closed by QEMU")
                chunks.append(chunk)

                # Try to decode all received data
                data = b"".join(chunks)
                try:
                    # First try to decode as latin-1 to handle control chars
                    decoded = data.decode("latin-1")
                    # Check if we have a complete JSON message
                    if decoded.strip().endswith("}"):
                        break
                except UnicodeError:
                    continue

            # Process the response
            messages = [
                json.loads(msg)
                for msg in decoded.split("\n")
                if msg.strip() and msg.strip() != ""
            ]

            # Return last non-event message
            for msg in reversed(messages):
                if "event" not in msg:
                    return msg
            return messages[-1]  # If only events, return last message

        except socket.timeout:
            raise ConnectionError("Timeout while reading QMP response")
        except socket.error as e:
            raise ConnectionError(f"Socket error while reading response: {str(e)}")
        except json.JSONDecodeError as e:
            raise ConnectionError(f"Invalid JSON in QMP response: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Error reading QMP response: {str(e)}")


class VMController:
    def __init__(self, cache_dir: str, host: str = "localhost", qmp_port: int = 7200):
        """Initialize QMP controller for QEMU VM

        Args:
            host: Hostname where QEMU is running
            qmp_port: Port number for QMP interface
        """
        self.host = host
        self.qmp_port = qmp_port
        self.cache_dir = cache_dir

    def take_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """Save VM state to a named snapshot"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("savevm", {"name": name})
            return response.get("return", None) if response else None

    def load_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """Restore VM state from a named snapshot"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("loadvm", {"name": name})
            return response.get("return", None) if response else None

    def list_snapshots(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of available snapshots"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("query-snapshots")
            return response.get("return", None) if response else None

    def take_screenshot(self) -> Optional[bytes]:
        """Capture screen to file and return the image data"""
        filepath = "/tmp/screenshot.png"
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command(
                "screendump",
                {
                    "filename": filepath,
                    "format": "png" if filepath.endswith(".png") else "ppm",
                },
            )

            if not response or "return" not in response:
                return None

            try:
                with open(filepath, "rb") as f:
                    image_data = f.read()
                return image_data
            except (IOError, OSError):
                return None

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get VM status"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("query-status")
            return response.get("return", None) if response else None

    def stop(self) -> Optional[Dict[str, Any]]:
        """Pause VM"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("stop")
            return response.get("return", None) if response else None

    def continue_vm(self) -> Optional[Dict[str, Any]]:
        """Resume VM"""
        with QMPConnection(self.host, self.qmp_port) as conn:
            response = conn._send_command("cont")
            return response.get("return", None) if response else None
