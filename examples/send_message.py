#!/usr/bin/env python3
"""
Simple IRC message sender - connects, sends one message, disconnects
Usage: python3 send_message.py <server> <port> <channel> <nickname> <message>
Example: python3 send_message.py localhost 6667 "#agents" claude "Hello!"
"""

import socket
import select
import sys

def wait_for_welcome(sock, timeout=30):
    """Read from server until we get 001 (RPL_WELCOME), handling PINGs"""
    buffer = ""
    import time
    start = time.time()
    while time.time() - start < timeout:
        ready = select.select([sock], [], [], 1.0)
        if ready[0]:
            data = sock.recv(4096).decode('utf-8', errors='ignore')
            if not data:
                raise ConnectionError("Server closed connection")
            buffer += data
            while '\r\n' in buffer:
                line, buffer = buffer.split('\r\n', 1)
                if line.startswith('PING'):
                    sock.send(f"{line.replace('PING', 'PONG')}\r\n".encode())
                # 001 = RPL_WELCOME — registration complete
                if ' 001 ' in line:
                    return True
    raise TimeoutError(f"No welcome from server within {timeout}s")

def send_irc_message(server, port, channel, nickname, message):
    """Send a single message to IRC channel and disconnect"""
    print(f"[IRC] Connecting to {server}:{port}...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server, port))

    print(f"[IRC] Authenticating as {nickname}...")
    sock.send(f"NICK {nickname}\r\n".encode())
    sock.send(f"USER {nickname} 0 * :{nickname}\r\n".encode())

    print(f"[IRC] Waiting for server welcome...")
    wait_for_welcome(sock)

    print(f"[IRC] Joining {channel}...")
    sock.send(f"JOIN {channel}\r\n".encode())
    # Drain JOIN response
    ready = select.select([sock], [], [], 3.0)
    if ready[0]:
        sock.recv(4096)

    print(f"[IRC] Sending message: {message}")
    sock.send(f"PRIVMSG {channel} :{message}\r\n".encode())
    # Brief pause to let server process
    ready = select.select([sock], [], [], 1.0)
    if ready[0]:
        sock.recv(4096)

    print(f"[IRC] Disconnecting...")
    sock.send(b"QUIT :Goodbye\r\n")
    sock.close()

    print(f"[IRC] Done!")

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python3 send_message.py <server> <port> <channel> <nickname> <message>")
        print('Example: python3 send_message.py localhost 6667 "#agents" claude "Hello from Claude!"')
        sys.exit(1)
    
    server = sys.argv[1]
    port = int(sys.argv[2])
    channel = sys.argv[3]
    nickname = sys.argv[4]
    message = " ".join(sys.argv[5:])
    
    send_irc_message(server, port, channel, nickname, message)
