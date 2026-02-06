#!/usr/bin/env python3
"""
Interactive IRC bot - monitors channel and responds to messages
Usage: python3 interactive_bot.py <server> <port> <channel> <nickname>
Example: python3 interactive_bot.py localhost 6667 "#agents" claude_bot
"""

import socket
import time
import sys
import select

class IRCBot:
    def __init__(self, server, port, nickname, channel):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.sock = None
        
    def connect(self):
        """Connect to IRC server, wait for welcome before joining"""
        print(f"[IRC] Connecting to {self.server}:{self.port}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server, self.port))

        # IRC handshake
        self.send_raw(f"NICK {self.nickname}")
        self.send_raw(f"USER {self.nickname} 0 * :{self.nickname}")

        # Wait for 001 (RPL_WELCOME) before joining
        print(f"[IRC] Waiting for server welcome...")
        self._wait_for_welcome()

        # Join channel
        self.send_raw(f"JOIN {self.channel}")
        print(f"[IRC] Connected as {self.nickname}")
        print(f"[IRC] Joined {self.channel}")
        print("[IRC] Listening for messages... (Ctrl+C to quit)")
        print("-" * 60)

    def _wait_for_welcome(self, timeout=30):
        """Read server data until 001 RPL_WELCOME, handling PINGs"""
        buffer = ""
        start = time.time()
        while time.time() - start < timeout:
            ready = select.select([self.sock], [], [], 1.0)
            if ready[0]:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    raise ConnectionError("Server closed connection during handshake")
                buffer += data
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    if line.startswith('PING'):
                        self.send_raw(line.replace('PING', 'PONG'))
                    if ' 001 ' in line:
                        return
        raise TimeoutError(f"No welcome from server within {timeout}s")
        
    def send_raw(self, message):
        """Send raw IRC command"""
        self.sock.send(f"{message}\r\n".encode())
        
    def send_message(self, target, message):
        """Send message to channel or user"""
        self.send_raw(f"PRIVMSG {target} :{message}")
        print(f"[SENT] -> {target}: {message}")
        
    def listen(self, callback=None):
        """Listen for IRC messages"""
        buffer = ""
        
        while True:
            # Check if socket has data (non-blocking)
            ready = select.select([self.sock], [], [], 1.0)
            if ready[0]:
                try:
                    data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                    if not data:
                        print("[IRC] Connection lost. Reconnecting...")
                        time.sleep(5)
                        self.connect()
                        continue
                        
                    buffer += data
                    
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        self.handle_line(line, callback)
                except Exception as e:
                    print(f"[ERROR] {e}")
                    time.sleep(5)
                    self.connect()
                    
    def handle_line(self, line, callback):
        """Handle incoming IRC line"""
        # Respond to PING
        if line.startswith('PING'):
            pong = line.replace('PING', 'PONG')
            self.send_raw(pong)
            return
            
        # Parse messages
        if 'PRIVMSG' in line:
            # Format: :nick!user@host PRIVMSG #channel :message
            parts = line.split(' ', 3)
            if len(parts) >= 4:
                sender = parts[0][1:].split('!')[0]
                target = parts[2]
                message = parts[3][1:] if parts[3].startswith(':') else parts[3]
                
                print(f"[RECV] {sender} -> {target}: {message}")
                
                if callback:
                    callback(sender, target, message)
        
        # Show join/part messages
        elif 'JOIN' in line:
            parts = line.split(' ')
            if len(parts) >= 3:
                user = parts[0][1:].split('!')[0]
                channel = parts[2][1:] if parts[2].startswith(':') else parts[2]
                print(f"[INFO] {user} joined {channel}")
                
        elif 'PART' in line:
            parts = line.split(' ')
            if len(parts) >= 3:
                user = parts[0][1:].split('!')[0]
                channel = parts[2]
                print(f"[INFO] {user} left {channel}")
                    
    def quit(self):
        """Disconnect from IRC"""
        print("\n[IRC] Disconnecting...")
        self.send_raw("QUIT :Goodbye")
        self.sock.close()

def on_message(bot, sender, target, message):
    """Example message handler"""
    # Ignore own messages
    if sender == bot.nickname:
        return
        
    # Respond to mentions
    if bot.nickname.lower() in message.lower():
        bot.send_message(target, f"Hello {sender}! You mentioned me.")
    
    # Respond to commands
    if message.startswith("!hello"):
        bot.send_message(target, f"Hello {sender}!")
    
    elif message.startswith("!time"):
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(target, f"Current time: {now}")
    
    elif message.startswith("!help"):
        bot.send_message(target, "Available commands: !hello, !time, !help")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 interactive_bot.py <server> <port> <channel> <nickname>")
        print('Example: python3 interactive_bot.py localhost 6667 "#agents" claude_bot')
        sys.exit(1)
    
    server = sys.argv[1]
    port = int(sys.argv[2])
    channel = sys.argv[3]
    nickname = sys.argv[4]
    
    bot = IRCBot(server, port, nickname, channel)
    bot.connect()
    
    # Send initial message
    bot.send_message(channel, f"{nickname} is now online! Try mentioning me or use !help")
    
    # Listen for messages with callback
    try:
        bot.listen(callback=lambda s, t, m: on_message(bot, s, t, m))
    except KeyboardInterrupt:
        bot.quit()
