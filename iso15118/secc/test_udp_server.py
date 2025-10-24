# 配置日志
import logging
import socket
import struct
import threading

from iso15118.shared.network import SDP_SERVER_PORT, SDP_MULTICAST_GROUP

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SyncUDPServer:
    def __init__(self, interface_index: int = 14):
        self.interface_index = interface_index
        self.socket = None
        self.running = False

    def start_server(self):
        """启动同步UDP服务器"""
        try:
            # 创建IPv6 UDP socket
            self.socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

            # 设置socket选项
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 绑定到所有IPv6地址和指定端口
            self.socket.bind(("", SDP_SERVER_PORT))

            # 配置多播
            self._setup_multicast()

            self.running = True
            logger.info(f"同步UDP服务器已启动，监听端口 {SDP_SERVER_PORT}")

            # 开始接收循环
            self._receive_loop()

        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            raise

    def _setup_multicast(self):
        """配置多播选项"""
        try:
            # 加入多播组
            multicast_group_bin = socket.inet_pton(socket.AF_INET6, SDP_MULTICAST_GROUP)
            mreq = multicast_group_bin + struct.pack("@I", self.interface_index)

            # 尝试不同的多播加入常量
            try:
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6,
                    socket.IPV6_JOIN_GROUP,
                    mreq
                )
                logger.info("使用IPV6_JOIN_GROUP加入多播组")
            except AttributeError:
                IPV6_ADD_MEMBERSHIP = 12  # Windows标准值
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6,
                    IPV6_ADD_MEMBERSHIP,
                    mreq
                )
                logger.info("使用IPV6_ADD_MEMBERSHIP加入多播组")

            # 设置多播接口
            self.socket.setsockopt(
                socket.IPPROTO_IPV6,
                socket.IPV6_MULTICAST_IF,
                struct.pack("@I", self.interface_index)
            )

            # 设置多播环回
            self.socket.setsockopt(
                socket.IPPROTO_IPV6,
                socket.IPV6_MULTICAST_LOOP,
                1
            )

            logger.info("多播配置完成")

        except Exception as e:
            logger.error(f"多播配置失败: {e}")

    def _receive_loop(self):
        """接收循环"""
        logger.info("开始接收数据...")
        while self.running:
            try:
                # 设置超时以便可以检查running标志
                self.socket.settimeout(1.0)

                data, addr = self.socket.recvfrom(65536)
                self._handle_datagram(data, addr)

            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"接收数据错误: {e}")

    def _handle_datagram(self, data: bytes, addr: tuple):
        """处理接收到的数据报"""
        logger.info(f"收到来自 {addr} 的数据:")
        logger.info(f"  数据长度: {len(data)} 字节")
        logger.info(f"  数据(十六进制): {data.hex()}")

        try:
            # 尝试解码为UTF-8文本
            text = data.decode('utf-8')
            logger.info(f"  数据(文本): {text}")
        except UnicodeDecodeError:
            logger.info("  数据包含非文本内容")

        # 发送响应
        self._send_response(data, addr)

    def _send_response(self, data: bytes, addr: tuple):
        """发送响应"""
        try:
            response = b"SDP_RESPONSE_FROM_SYNC_SERVER"
            self.socket.sendto(response, addr)
            logger.info(f"已向 {addr} 发送响应")
        except Exception as e:
            logger.error(f"发送响应失败: {e}")

    def stop_server(self):
        """停止服务器"""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("同步UDP服务器已停止")


def run_udp_server():
    server = SyncUDPServer(interface_index=14)

    try:
        # 在后台线程中运行服务器
        server_thread = threading.Thread(target=server.start_server)
        server_thread.daemon = True
        server_thread.start()

        print("服务器运行中，按Enter键停止...")
        input()  # 等待用户输入

    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        server.stop_server()
