import socket
import json
import sys
import threading
from datetime import datetime
from rich import print
"""
版本号：1.5.0

状态编码
客户端
10：申请登录
11：发送用户名进行验证
20：申请注册
30：聊天信息
"""


class Client:
    host = '127.0.0.1'  # 服务器地址
    port = 8081  # 服务器端口

    def __init__(self):
        """初始化客户端，建立连接并准备接收消息"""
        self.client_sock = self.connect()  # 建立连接
        self.username = None  # 用户名初始化为空
        self.is_closing = False  # 标志连接是否关闭
        self.receive_thread = None  # 保存接收线程的引用

    @staticmethod
    def connect():
        """建立与服务器的连接"""
        try:
            # 创建socket对象，使用IPv4协议和TCP协议
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect((Client.host, Client.port))  # 连接到服务器
            return client_sock
        except ConnectionRefusedError:
            print("连接失败，服务器未启动。")
            sys.exit(1)

    def login(self):
        """处理用户登录功能"""
        while True:
            account = input('请输入账号：')  # 获取用户账号
            if not account:
                print("账号不能为空！")
                continue
            password = input('请输入密码：')  # 获取用户密码
            if not password:
                print("密码不能为空！")
                continue
            # 构造登录请求数据，type = 10 表示登录请求
            login_data = {'type': 10, 'message': {'account': account, 'password': password}}
            self.send_message(login_data)  # 发送登录请求到服务器
            self.authentication()  # 进行认证
            break  # 登录成功后跳出循环

    def register(self):
        """处理用户注册功能"""
        account = input('请输入账号：')  # 获取用户注册账号
        password = input('请输入密码：')  # 获取用户注册密码

        # 构造注册请求数据，type = 20 表示注册请求
        register_data = {'type': 20, 'message': {'account': account, 'password': password}}
        self.send_message(register_data)  # 发送注册请求到服务器

        # 获取服务器的注册结果
        data = self.recv_message()[0]
        if data and data.get('type') == 30:  # 注册成功
            print('注册成功！请登录。')
            self.login()  # 注册成功后直接进行登录
        else:
            print(data.get('message', '未知错误'))  # 输出错误信息
            self.register()  # 如果注册失败，重新尝试注册

    def authentication(self):
        """处理认证结果，验证用户登录状态"""
        # 获取认证数据
        data = self.recv_message()[0]
        if data:
            if data['type'] == 10:  # 登录成功
                print('登录成功！')
                while True:
                    self.username = input('请输入您的用户名：')  # 获取用户名
                    if not self.username:
                        print("用户名不能为空！")
                        continue  # 如果用户名为空，继续循环直到输入有效用户名
                    self.send_message({'type': 11, 'username': self.username})  # 发送用户名到服务器
                    data = self.recv_message()[0]
                    if data['type'] == 22:  # 如果用户名已存在
                        print('用户名已存在，请重新输入。')
                    elif data['type'] == 21:
                        print('用户不能命名为{系统}！')
                    else:
                        break  # 用户名有效，跳出循环
                self.chat()  # 进入聊天功能
            elif data['type'] == 12:  # 登录失败
                print(f"账号或密码错误")
                self.login()  # 重新尝试登录
            elif data['type'] == 11:
                print(f"该账号已登录")
                self.login()
                # 进入选择，是否顶号
            else:
                print('未知的返回类型')  # 未知的返回类型
        else:
            print('未收到有效的响应')  # 未收到有效的响应

    def send_message(self, data):
        """将数据发送到服务器，并附加时间戳"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 获取当前时间并格式化
            data['timestamp'] = timestamp  # 在消息中添加时间戳
            # 将字典数据转化为JSON字符串并发送
            self.client_sock.send(json.dumps(data).encode('utf-8'))
        except socket.error as e:
            print(f'发送数据时发生错误: {e}')  # 捕获并输出发送数据时的错误

    def recv_message(self):
        """接收服务器的消息并解析JSON"""
        data = self.client_sock.recv(1024)  # 接收数据
        messages = []
        if data:
            data = data.decode('utf-8')  # 解码数据
            data_list = data.strip().split("\n")  # 按换行符分割数据
            for item in data_list:
                try:
                    # 返回解析后的 JSON 数据
                    messages.append(json.loads(item))
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}, 数据: {item}")
        return messages

    def chat(self):
        """进入聊天界面，处理消息发送与接收"""

        # 创建一个线程来监听服务器发来的消息
        self.receive_thread = threading.Thread(target=self.receive_messages)  # 新建线程监听消息
        self.receive_thread.daemon = True  # 设置为守护线程
        self.receive_thread.start()
        print("命令\n退出：exit\n查看历史消息:history\n")

        while True:
            message = input()
            if message.lower() == 'exit':  # 退出聊天
                print("退出聊天")
                self.is_closing = True
                self.client_sock.close()
                break
            elif message.lower() == 'history':  # 查看历史消息
                self.send_message({'type': 30, 'username': self.username, 'message': 'history'})
            else:
                message_data = {'type': 30, 'username': self.username, 'message': message}
                self.send_message(message_data)

        # 确保接收线程能够退出
        self.receive_thread.join()

    def receive_messages(self):
        while not self.is_closing:
            try:
                for data in self.recv_message():
                    if data.get('type') == 80:  # 普通聊天消息
                        print(f"用户{data['message']['username']}({data['timestamp']}): {data['message']['message']}")
                    elif data.get('type') == 70:  # 用户进入
                        print(f"系统消息({data['timestamp']}): 用户{data['message']}进入了聊天室")
                    elif data.get('type') == 90:  # 用户退出
                        print(f"系统消息({data['timestamp']}): 用户{data['message']}退出了聊天室")
                    elif data.get('type') == 20:  # 自己进入聊天室
                        username_len = len(self.username)  # 获取用户名的长度，用于格式化输出
                        print('-' * (username_len + 4))  # 打印分隔线
                        print(f"| {self.username} |  进入了聊天室")  # 显示用户进入聊天室的信息
                        print('-' * (username_len + 4))
                    elif data.get('type') == 60:  # 历史消息
                        print(
                            f"[历史消息] 用户{data['message']['username']}({data['timestamp']}): {data['message']['message']}")
            except socket.error as e:
                if self.is_closing:
                    break
                print(f'接收数据时发生错误: {e}')
                break
            except Exception as e:
                print(f'发生未知错误: {e}')
                break

    def start(self):
        """启动客户端并选择操作"""
        while True:
            # 提供选择登录、注册或退出的操作
            action = input('请选择操作: 1. 登录 2. 注册 3. 退出: ')

            if action == '1':
                self.login()  # 登录
                break
            elif action == '2':
                self.register()  # 注册
                break
            elif action == '3':
                print('退出程序')
                self.client_sock.close()  # 关闭连接
                break
            else:
                print('无效的选项，请重新选择。')  # 输入无效选项时，提示重新选择


if __name__ == "__main__":
    client = Client()  # 创建客户端实例
    client.start()  # 启动客户端
