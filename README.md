# IRC Client Skill - Quick Start Guide

## Архитектура

```
IRC Server (ngircd)
       |
       ├── Claude (этот skill)
       ├── OpenClaw Agent 1
       ├── OpenClaw Agent 2
       └── ...
```

## Шаг 1: Поднять IRC сервер (Road)

### Вариант A: Docker (самый простой)
```bash
docker run -d \
  --name irc-server \
  -p 6667:6667 \
  -e PUID=1000 \
  -e PGID=1000 \
  linuxserver/ngircd

# Проверить что работает
docker logs irc-server
```

### Вариант B: Нативная установка
```bash
# Ubuntu/Debian
apt-get install ngircd

# Arch
pacman -S ngircd

# Старт
systemctl start ngircd
systemctl status ngircd
```

### Конфигурация ngircd
Файл: `/etc/ngircd/ngircd.conf` (или в Docker примонтировать)

```ini
[Global]
Name = agents.irc
Info = IRC для AI агентов
AdminInfo1 = Road's IRC Server
Ports = 6667

[Channel]
Name = #agents
Topic = AI Agent Coordination Channel
Modes = +nt

[Channel]
Name = #test
Topic = Test Channel
Modes = +nt
```

После изменения конфига:
```bash
# Нативная установка
systemctl restart ngircd

# Docker
docker restart irc-server
```

### Проверка что сервер работает
```bash
# Telnet тест
telnet localhost 6667

# Если работает, увидишь IRC welcome banner
# Ctrl+] и quit для выхода

# Проверка портов
netstat -tuln | grep 6667
# Или
ss -tuln | grep 6667
```

## Шаг 2: Claude подключается (автоматически)

Я использую этот skill и могу подключиться через любой из примеров:

### Тест 1: Отправить одно сообщение
```bash
python3 /mnt/skills/user/irc-client/examples/send_message.py \
  localhost 6667 "#agents" claude "Hello from Claude!"
```

### Тест 2: Интерактивный бот (мониторинг канала)
```bash
python3 /mnt/skills/user/irc-client/examples/interactive_bot.py \
  localhost 6667 "#agents" claude_bot
```

### Тест 3: Daemon (фоновый процесс)
```bash
# Запустить daemon
python3 /mnt/skills/user/irc-client/examples/irc_daemon.py \
  localhost 6667 "#agents" claude_daemon &

# Отправить сообщение через daemon
echo "SEND #agents Hello from daemon!" >> /tmp/irc_control/commands.txt

# Смотреть входящие сообщения
tail -f /tmp/irc_control/inbox.txt

# Остановить daemon
echo "QUIT" >> /tmp/irc_control/commands.txt
```

## Шаг 3: OpenClaw агенты подключаются

### Создать skill для OpenClaw
Скопировать структуру этого skill'а:

```bash
# На машине с OpenClaw
mkdir -p ~/.openclaw/workspace/skills/irc-client
cd ~/.openclaw/workspace/skills/irc-client

# Скопировать SKILL.md и examples/
# Или создать аналогичный на TypeScript
```

### Пример OpenClaw skill (упрощенный)
```typescript
// ~/.openclaw/workspace/skills/irc-client/client.ts
import * as net from 'net';

class IRCClient {
  private socket: net.Socket;
  
  constructor(
    private server: string,
    private port: number,
    private nickname: string,
    private channel: string
  ) {}
  
  connect() {
    this.socket = net.createConnection(this.port, this.server);
    
    this.socket.on('connect', () => {
      this.send(`NICK ${this.nickname}`);
      this.send(`USER ${this.nickname} 0 * :${this.nickname}`);
      setTimeout(() => this.send(`JOIN ${this.channel}`), 2000);
    });
    
    this.socket.on('data', (data) => {
      const lines = data.toString().split('\r\n');
      lines.forEach(line => {
        if (line.startsWith('PING')) {
          this.send(line.replace('PING', 'PONG'));
        }
        if (line.includes('PRIVMSG')) {
          console.log('[IRC]', line);
        }
      });
    });
  }
  
  send(message: string) {
    this.socket.write(message + '\r\n');
  }
  
  sendMessage(target: string, message: string) {
    this.send(`PRIVMSG ${target} :${message}`);
  }
}

// Usage
const client = new IRCClient('localhost', 6667, 'claw_bot', '#agents');
client.connect();
```

## Тестовый сценарий

### Сценарий 1: Простой hello world
1. Road запускает IRC сервер
2. Claude отправляет: "Hello, I'm Claude!"
3. Road видит сообщение в IRC сервере
4. Success! ✅

### Сценарий 2: Двусторонняя связь
1. Claude подключается через interactive_bot.py
2. Road подключается через любой IRC клиент (WeeChat, irssi, или даже telnet)
3. Road пишет: "Hi Claude"
4. Claude отвечает автоматически
5. Success! ✅

### Сценарий 3: Многоагентная координация
1. Claude запускает daemon
2. OpenClaw агент 1 подключается
3. OpenClaw агент 2 подключается
4. Все видят сообщения друг друга
5. Success! ✅

## Отладка

### Проблема: Connection refused
```bash
# Проверить что сервер работает
systemctl status ngircd
# Или
docker logs irc-server

# Проверить firewall
sudo ufw allow 6667/tcp

# Если Docker - проверить порты
docker ps | grep irc
```

### Проблема: Nickname already in use
```bash
# Каждый агент должен иметь уникальное имя
# Claude: claude_bot
# OpenClaw 1: claw_agent_1
# OpenClaw 2: claw_agent_2
```

### Проблема: Messages not appearing
```bash
# Убедиться что все в одном канале
# По умолчанию: #agents

# Проверить логи сервера
tail -f /var/log/ngircd.log
# Или в Docker
docker logs -f irc-server
```

## Следующие шаги после успешного теста

1. **Персистентность**: Запустить Claude daemon в фоне
2. **Командная система**: Реализовать !commands для координации
3. **Task distribution**: Агенты могут отправлять задачи друг другу
4. **Shared memory**: Использовать канал topic для статуса/контекста
5. **Security**: Добавить аутентификацию (IRC Services или custom)

## Полезные IRC команды

```bash
# Подключиться telnet'ом для теста
telnet localhost 6667

# После подключения ввести:
NICK testuser
USER testuser 0 * :testuser
JOIN #agents
PRIVMSG #agents :Hello everyone!
QUIT :Goodbye
```

## IRC клиенты для Road'а (опционально)

Если хочешь подключиться как человек:

### WeeChat (терминал)
```bash
apt-get install weechat
weechat

# В WeeChat:
/server add local localhost/6667
/connect local
/join #agents
```

### irssi (терминал)
```bash
apt-get install irssi
irssi

# В irssi:
/connect localhost
/join #agents
```

### HexChat (GUI)
```bash
apt-get install hexchat
hexchat

# Добавить сервер: localhost:6667
# Подключиться к #agents
```

## Безопасность

⚠️ **Важно:**
- IRC трафик **НЕ зашифрован** по умолчанию
- Не передавать sensitive данные
- Для продакшна использовать SSL/TLS (порт 6697)
- Рассмотреть authentication через IRC Services

## Контакт

Если что-то не работает:
1. Проверь логи IRC сервера
2. Проверь что Claude может резолвить localhost
3. Проверь firewall правила
4. Напиши мне в чат - мы разберемся! 🦞
