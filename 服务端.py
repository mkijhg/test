import socket
import json
import threading
import os
from datetime import datetime
from rich import print

"""
版本号：1.5.0
2024/12/9
2025/8/10
待实现功能：
0. 用户退出播报（完成）
1. 进入聊天室时广播，{username} 进入了聊天室。（完成）
2. 同一账号不能同时登录。(完成)
3. 不同客户端登录同一账号时可以选择将前一个账号顶下去。被顶的账号自动断联并返回消息。
4. 消息历史记录：保存聊天室的消息记录到聊天记录.txt中，检测到客户端用户登录后自动输出10条历史消息，输入history可浏览全部消息。（完成）
5. 用户列表
6. 添加发送消息时间(完成)
7. 实现窗口化，做成应用
8. 状态编码：{type: '', message: '', timestamp: ''},设置type为返回类型（类似错误代码）10-99（完成）
9. 实现真实服务端场景，客户端只有消息接口，能发送消息
"""

"""
状态编码
服务端
发送消息
10：账号登陆成功
11：该账号已登录
12：账号或密码错误
20：用户名合法且唯一
21：用户不能命名为{系统}
22：用户名已存在
30：成功注册
31：账号已存在

广播消息
90：系统广播用户退出消息
80：广播用户消息
70：系统广播用户进入信息

客户端
10：申请登录
11：发送用户名进行验证
20：申请注册
30：聊天信息
"""

print(
    """
       _____ _             _     _____                       
      / ____| |           | |   |  __ \                      
     | |    | |__   __ _ _| |_  | |__) |___   ___  _ __ ___  
     | |    | '_ \ / _` |_   _| |  _  // _ \ / _ \| '_ ` _ \ 
     | |____| | | | (_| | | |_  | | \ \ (_) | (_) | | | | | |
      \_____|_| |_|\__,_|  \__| |_|  \_\___/ \___/|_| |_| |_|                             
    """
)


class Server:
    host = '127.0.0.1'
    port = 8081
    user_data_file = r'E:\python_Projects\聊天室\用户数据.txt'
    chat_history_file = r'E:\python_Projects\聊天室\聊天记录.txt'  # 定义聊天记录路径

    def __init__(self):
        """
        初始化服务器，创建服务器 socket，设置客户端和账号数据存储结构。
        """
        self.server_sock = self.create_server()
        self.clients = {}  # 已连接客户端和用户名的映射
        self.accounts = {}  # 已注册账号和客户端的映射

    @staticmethod
    def create_server():
        """
        创建服务器并绑定指定的 IP 地址和端口号，开始监听客户端连接。

        Returns:
            server_sock: 创建并返回一个已绑定的服务器 socket 对象。
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((Server.host, Server.port))
        server_sock.listen(20)
        print("服务端启动，等待连接...")
        return server_sock

    def handle_client(self, client_sock, client_addr):
        """
        处理与客户端的连接，接收客户端发送的消息并做出相应处理。

        Args:
            client_sock: 客户端 socket 对象，用于接收和发送消息。
            client_addr: 客户端地址信息，用于输出调试信息。
        """
        print(f"客户端 {client_addr} 已连接")
        while True:
            try:
                data = self.recv_message(client_sock)
                if data:
                    self.handle_request(client_sock, data)
                else:
                    break
            except ConnectionResetError:
                # 客户端断开连接，输出用户名退出信息
                username = self.clients.get(client_sock)
                response = {'type': 90, 'message': username}
                self.broadcast_message(client_sock, response)
                self.clients.pop(client_sock, None)
                self.logout(client_sock)
                break

    def handle_request(self, client_sock, data):
        """
        处理客户端发送的请求数据，根据不同的请求类型调用相应的方法。

        Args:
            client_sock: 客户端 socket 对象。
            data: 客户端发送的数据（JSON 格式）。
        """
        try:
            data = json.loads(data)
            if data['type'] == 10:  # 登录
                self.login(client_sock, data)
            elif data['type'] == 20:  # 注册
                self.register(client_sock, data)
            elif data['type'] == 30:  # 聊天信息
                if data['message'] == 'history':  # 查看全部历史消息
                    history = self.get_chat_history()
                    for message in history:
                        self.send_message(client_sock, message)
                    return
                message = {'type': 80, 'message': {'username': data['username'], 'message': data['message']}}
                self.broadcast_message(client_sock, message)
                self.save_chat_history(message)  # 保存聊天记录

            elif data['type'] == 11:  # 验证用户名是否重复
                if self.check_username(client_sock, data):
                    # 发送最近的 10 条历史消息
                    history = self.get_chat_history(last_n=10)
                    for message in history:
                        self.send_message(client_sock, message)
        except Exception as e:
            print(f"处理请求时发生错误: {e}")

    def check_account(self, data):
        """
        检查账号是否已存在，如果已存在则返回错误信息。

        Args:
            data: 包含用户名的请求数据。

        Returns:
            bool: 如果账号已存在返回 False，否则返回 True。
        """
        client_account = data['message']['account']
        for account in self.accounts.values():
            if account == client_account:
                return False  # 如果账号已存在，返回 False
        return True  # 如果账号不存在，返回 True

    def check_username(self, client_sock, data):
        """
        检查用户名是否已存在，如果已存在则返回错误信息。

        Args:
            client_sock: 客户端 socket 对象。
            data: 包含用户名的请求数据。
        """
        client_username = data['username']
        if client_username == '系统':
            response = {'type': 21, 'message': '用户不能命名为{系统}！'}
            self.send_message(client_sock, response)
            return False
        for username in self.clients.values():
            if username == client_username:
                response = {'type': 22, 'message': '用户名已存在'}
                self.send_message(client_sock, response)
                return False

        response = {'type': 20, 'username': client_username}
        self.send_message(client_sock, response)
        # 将用户名和客户端 socket 映射
        self.clients[client_sock] = client_username
        broad_response = {'type': 70,  'message': client_username}
        self.broadcast_message(client_sock, broad_response)
        return True

    def login(self, client_sock, data):
        """
        处理客户端的登录请求，验证账号和密码是否正确。

        Args:
            client_sock: 客户端 socket 对象。
            data: 包含账号和密码的登录请求数据。
        """
        account = data['message']['account']
        password = data['message']['password']

        # 读取用户数据文件，检查用户是否存在且密码是否正确
        user_data = self.read_user_data()
        if account in user_data and user_data[account] == password:
            if self.check_account(data):
                self.accounts[client_sock] = account
                response = {'type': 10}
            else:
                response = {'type': 11, 'message': '账号已登录'}
        else:
            response = {'type': 12, 'message': '账号或密码错误'}
        self.send_message(client_sock, response)

    def register(self, client_sock, data):
        """
        处理客户端的注册请求，检查账号是否存在，若不存在则注册新用户。

        Args:
            client_sock: 客户端 socket 对象。
            data: 包含账号和密码的注册请求数据。
        """
        account = data['message']['account']
        password = data['message']['password']

        # 读取用户数据文件，检查是否已存在该用户名
        user_data = self.read_user_data()
        if account in user_data:
            response = {'type': 31, 'message': '账号已存在'}
        else:
            # 如果用户名不存在，注册新用户
            user_data[account] = password
            self.save_user_data(user_data)
            response = {'type': 30}

        # 返回注册结果给客户端
        self.send_message(client_sock, response)

    def logout(self, client_sock):
        """
        处理客户端的注销请求，移除账号与客户端的映射。
        """
        if client_sock in self.accounts:
            del self.accounts[client_sock]

    def read_user_data(self):
        """
        读取存储用户数据的文件，若文件不存在则初始化为空字典。

        Returns:
            user_data: 存储用户信息的字典。
        """
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, 'r', encoding='utf-8') as file:
                user_data = json.load(file)
        else:
            # 文件不存在，初始化为空字典
            user_data = {}
            self.save_user_data(user_data)
        return user_data

    def save_user_data(self, user_data):
        """
        保存用户数据到指定的文件中。

        Args:
            user_data: 包含用户信息的字典。
        """
        with open(self.user_data_file, 'w', encoding='utf-8') as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)

    def send_message(self, client_sock, message):
        """

        向客户端发送消息，并附加时间戳。

        Args:
            client_sock: 客户端 socket 对象。
            message: 需要发送的消息（字典格式）。
        """
        try:
            if message['type'] != 60:
                # 获取当前时间
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message['timestamp'] = timestamp  # 在消息中添加时间戳
            client_sock.send((json.dumps(message) + '\n').encode('utf-8'))
        except socket.error as e:
            print(f"发送消息时发生错误: {e}")
            client_sock.close()
            self.clients.pop(client_sock, None)
            self.logout(client_sock)

    @staticmethod
    def recv_message(client_sock):
        """
        接收客户端发送的消息。

        Args:
            client_sock: 客户端 socket 对象。

        Returns:
            data: 接收到的消息（字符串格式）。
        """
        data = client_sock.recv(1024)
        if not data:
            return None
        return data.decode('utf-8')

    def broadcast_message(self, sender_sock, data):
        """
        广播聊天信息给所有客户端，但不包括发送消息的客户端。

        Args:
            sender_sock: 发送消息的客户端 socket 对象。
            data: 发送的消息数据（字典格式）。
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['timestamp'] = timestamp  # 在消息中添加时间戳
        if data['type'] == 80:
            print(f"用户{data['message']['username']} ({data['timestamp']}): {data['message']['message']}")
        elif data['type'] == 70:
            print(f"系统消息: 用户{data['message']}进入了聊天室")
        elif data['type'] == 90:
            print(f"系统消息: 用户{data['message']}退出了聊天室")
        for client in self.clients:
            if client != sender_sock:
                self.send_message(client, data)


    def save_chat_history(self, message):
        """将消息保存到聊天记录文件中"""
        with open(self.chat_history_file, 'a', encoding='utf-8') as file:
            file.write(json.dumps(message) + '\n')  # 保存消息到文件中

    def get_chat_history(self, last_n=None):
        """
        读取聊天记录文件，返回最后 n 条消息。
        Args:
            last_n: 如果指定，返回最后 n 条记录；如果为 None，返回全部记录。
        Returns:
            list: 聊天记录列表。
        """
        if not os.path.exists(self.chat_history_file):
            return []  # 如果文件不存在，返回空列表
        messages = []
        with open(self.chat_history_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()  # 读取所有行
            lines_to_process = lines[-last_n:] if last_n else lines
            for line in lines_to_process:
                message = json.loads(line.strip())  # 解析行
                message['type'] = 60  # 设置消息类型
                messages.append(message)  # 添加到消息列表
            return messages

    def run(self):
        """
        启动服务器，等待客户端连接，并为每个客户端创建一个线程来处理请求。
        """
        while True:
            client_sock, client_addr = self.server_sock.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(client_sock, client_addr))
            client_thread.start()


if __name__ == "__main__":
    server = Server()
    server.run()
