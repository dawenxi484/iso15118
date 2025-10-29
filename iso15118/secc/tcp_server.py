import socket
import threading


class TCPServer:
    def __init__(self, host='172.16.4.178', port=8888):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False

    def start(self):
        """启动TCP服务器"""
        try:
            # 创建TCP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置地址重用，防止"Address already in use"错误
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 绑定地址和端口
            self.socket.bind((self.host, self.port))
            # 开始监听，最大连接数为5
            self.socket.listen(5)

            self.running = True
            print(f"TCP服务器已启动，监听 {self.host}:{self.port}")
            print("等待客户端连接...")

            while self.running:
                try:
                    # 接受客户端连接
                    client_socket, client_address = self.socket.accept()
                    print(f"\n新的客户端连接来自: {client_address}")

                    # 为每个客户端创建新线程处理
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except socket.error as e:
                    if self.running:
                        print(f"接受连接时出错: {e}")

        except Exception as e:
            print(f"启动服务器时出错: {e}")
        finally:
            self.stop()

    def handle_client(self, client_socket, client_address):
        """处理单个客户端连接"""
        try:
            while self.running:
                # 接收数据，缓冲区大小为1024字节
                data = client_socket.recv(1024)
                if not data:
                    # 没有数据表示客户端已断开连接
                    print(f"\n客户端 {client_address} 已断开连接")
                    break

                # 打印接收到的数据
                try:
                    # 尝试解码为UTF-8文本
                    decoded_data = data.decode('utf-8').strip()
                    print(f"来自 {client_address} 的数据: {decoded_data}")
                except UnicodeDecodeError:
                    # 如果是二进制数据，以十六进制显示
                    hex_data = data.hex()
                    print(f"来自 {client_address} 的二进制数据 (hex): {hex_data}")

        except socket.error as e:
            print(f"与客户端 {client_address} 通信时出错: {e}")
        finally:
            client_socket.close()

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("TCP服务器已停止")


if __name__ == "__main__":
    # 创建并启动服务器
    server = TCPServer('172.16.4.178', 8888)  # 监听所有网络接口

    try:
        server.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭服务器...")
        server.stop()