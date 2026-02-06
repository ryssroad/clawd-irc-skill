#!/usr/bin/env python3
"""
IRC Daemon - persistent background connection with file-based control
Usage: python3 irc_daemon.py <server> <port> <channel> <nickname>
Example: python3 irc_daemon.py localhost 6667 "#agents" claude_daemon

Control via files in /tmp/irc_control/:
  - Send message: echo "SEND #agents Hello!" >> /tmp/irc_control/commands.txt
  - View inbox: tail -f /tmp/irc_control/inbox.txt
  - Stop daemon: echo "QUIT" >> /tmp/irc_control/commands.txt
"""

import socket
import time
import sys
import select
from pathlib import Path

CONTROL_DIR = Path("/tmp/irc_control")
CONTROL_DIR.mkdir(exist_ok=True)

class IRCDaemon:
    def __init__(self, server, port, nickname, channel):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.sock = None
        self.running = True
        
        # Create control files
        self.inbox = CONTROL_DIR / "inbox.txt"
        self.outbox = CONTROL_DIR / "outbox.txt"
        self.commands = CONTROL_DIR / "commands.txt"
        self.status = CONTROL_DIR / "status.txt"
        
        self.inbox.touch()
        self.outbox.touch()
        self.commands.touch()
        self.status.write_text("STARTING\n")
        
    def connect(self):
        """Connect to IRC server, wait for welcome before joining"""
        print(f"[DAEMON] Connecting to {self.server}:{self.port}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(1.0)

        try:
            self.sock.connect((self.server, self.port))
        except Exception as e:
            print(f"[DAEMON] Connection failed: {e}")
            self.status.write_text(f"ERROR: {e}\n")
            return False

        self.send_raw(f"NICK {self.nickname}")
        self.send_raw(f"USER {self.nickname} 0 * :{self.nickname}")

        # Wait for 001 (RPL_WELCOME) before joining
        print(f"[DAEMON] Waiting for server welcome...")
        if not self._wait_for_welcome():
            return False

        self.send_raw(f"JOIN {self.channel}")

        self.status.write_text(f"CONNECTED: {self.server}:{self.port} as {self.nickname} in {self.channel}\n")
        print(f"[DAEMON] Connected as {self.nickname} in {self.channel}")
        return True

    def _wait_for_welcome(self, timeout=30):
        """Read server data until 001 RPL_WELCOME, handling PINGs"""
        buffer = ""
        start = time.time()
        while time.time() - start < timeout:
            try:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    print("[DAEMON] Server closed connection during handshake")
                    self.status.write_text("ERROR: Connection closed during handshake\n")
                    return False
                buffer += data
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    if line.startswith('PING'):
                        self.send_raw(line.replace('PING', 'PONG'))
                    if ' 001 ' in line:
                        return True
            except socket.timeout:
                continue
        print(f"[DAEMON] No welcome from server within {timeout}s")
        self.status.write_text(f"ERROR: No welcome within {timeout}s\n")
        return False
        
    def send_raw(self, message):
        """Send raw IRC command"""
        try:
            self.sock.send(f"{message}\r\n".encode())
            with open(self.outbox, 'a') as f:
                f.write(f"{time.time()} -> {message}\n")
        except Exception as e:
            print(f"[DAEMON] Send error: {e}")
        
    def check_commands(self):
        """Check for commands in control file"""
        try:
            if self.commands.stat().st_size > 0:
                with open(self.commands, 'r') as f:
                    lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith("SEND "):
                        # Format: SEND #channel message text
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            target, message = parts[1], parts[2]
                            self.send_raw(f"PRIVMSG {target} :{message}")
                            print(f"[DAEMON] Sent to {target}: {message}")
                            
                    elif line.startswith("JOIN "):
                        # Format: JOIN #channel
                        channel = line.split(' ', 1)[1]
                        self.send_raw(f"JOIN {channel}")
                        print(f"[DAEMON] Joined {channel}")
                        
                    elif line.startswith("PART "):
                        # Format: PART #channel
                        channel = line.split(' ', 1)[1]
                        self.send_raw(f"PART {channel}")
                        print(f"[DAEMON] Left {channel}")
                        
                    elif line == "QUIT":
                        print(f"[DAEMON] Quit command received")
                        self.running = False
                        
                    else:
                        print(f"[DAEMON] Unknown command: {line}")
                
                # Clear commands file
                self.commands.write_text("")
        except Exception as e:
            print(f"[DAEMON] Command check error: {e}")
            
    def run(self):
        """Main daemon loop"""
        if not self.connect():
            return
            
        buffer = ""
        last_ping = time.time()
        
        while self.running:
            # Check for outgoing commands
            self.check_commands()
            
            # Check for incoming messages
            try:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                
                if not data:
                    print("[DAEMON] Connection lost. Reconnecting...")
                    self.status.write_text("RECONNECTING\n")
                    time.sleep(5)
                    if not self.connect():
                        break
                    continue
                    
                buffer += data
                
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    
                    # Handle PING
                    if line.startswith('PING'):
                        self.send_raw(line.replace('PING', 'PONG'))
                        last_ping = time.time()
                        continue
                    
                    # Log all incoming messages
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Handle PRIVMSG
                    if 'PRIVMSG' in line:
                        parts = line.split(' ', 3)
                        if len(parts) >= 4:
                            sender = parts[0][1:].split('!')[0]
                            target = parts[2]
                            message = parts[3][1:] if parts[3].startswith(':') else parts[3]
                            
                            # Write to inbox
                            with open(self.inbox, 'a') as f:
                                f.write(f"{timestamp} | {sender} -> {target}: {message}\n")
                            
                            print(f"[DAEMON] {sender} -> {target}: {message}")
                    
                    # Handle JOIN
                    elif 'JOIN' in line:
                        parts = line.split(' ')
                        if len(parts) >= 3:
                            user = parts[0][1:].split('!')[0]
                            channel = parts[2][1:] if parts[2].startswith(':') else parts[2]
                            with open(self.inbox, 'a') as f:
                                f.write(f"{timestamp} | SYSTEM: {user} joined {channel}\n")
                            print(f"[DAEMON] {user} joined {channel}")
                    
                    # Handle PART
                    elif 'PART' in line:
                        parts = line.split(' ')
                        if len(parts) >= 3:
                            user = parts[0][1:].split('!')[0]
                            channel = parts[2]
                            with open(self.inbox, 'a') as f:
                                f.write(f"{timestamp} | SYSTEM: {user} left {channel}\n")
                            print(f"[DAEMON] {user} left {channel}")
                            
            except socket.timeout:
                # No data, check for periodic ping
                if time.time() - last_ping > 120:
                    self.send_raw("PING :keepalive")
                    last_ping = time.time()
            except Exception as e:
                print(f"[DAEMON] Error: {e}")
                self.status.write_text(f"ERROR: {e}\n")
                time.sleep(5)
                if not self.connect():
                    break
                
        # Cleanup
        self.status.write_text("STOPPED\n")
        try:
            self.sock.send(b"QUIT :Daemon stopped\r\n")
            self.sock.close()
        except:
            pass
        print("[DAEMON] Stopped")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 irc_daemon.py <server> <port> <channel> <nickname>")
        print('Example: python3 irc_daemon.py localhost 6667 "#agents" claude_daemon')
        print()
        print("Control files:")
        print(f"  Commands: {CONTROL_DIR}/commands.txt")
        print(f"  Inbox:    {CONTROL_DIR}/inbox.txt")
        print(f"  Outbox:   {CONTROL_DIR}/outbox.txt")
        print(f"  Status:   {CONTROL_DIR}/status.txt")
        print()
        print("Examples:")
        print('  echo "SEND #agents Hello!" >> /tmp/irc_control/commands.txt')
        print('  tail -f /tmp/irc_control/inbox.txt')
        print('  echo "QUIT" >> /tmp/irc_control/commands.txt')
        sys.exit(1)
    
    server = sys.argv[1]
    port = int(sys.argv[2])
    channel = sys.argv[3]
    nickname = sys.argv[4]
    
    daemon = IRCDaemon(server, port, nickname, channel)
    
    print(f"[DAEMON] Starting IRC daemon...")
    print(f"[DAEMON] Control files in {CONTROL_DIR}")
    print(f"[DAEMON]   Send: echo 'SEND #agents Hello!' >> {CONTROL_DIR}/commands.txt")
    print(f"[DAEMON]   View: tail -f {CONTROL_DIR}/inbox.txt")
    print(f"[DAEMON]   Stop: echo 'QUIT' >> {CONTROL_DIR}/commands.txt")
    print(f"[DAEMON] Starting main loop...")
    
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\n[DAEMON] Keyboard interrupt received")
        daemon.running = False
        daemon.run()  # Cleanup
