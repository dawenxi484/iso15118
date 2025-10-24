import asyncio
import logging
import socket
from ipaddress import IPv6Address
from random import randint
from typing import Tuple, Union

import netifaces
import psutil

from iso15118.shared.exceptions import (
    InvalidInterfaceError,
    MACAddressNotFound,
    NoLinkLocalAddressError,
)

logger = logging.getLogger(__name__)

SDP_MULTICAST_GROUP = "FF02::1"
SDP_SERVER_PORT = 15118


def _get_link_local_addr(nic: str) -> Union[IPv6Address, None]:
    """
    Provides the IPv6 link-local address for the network interface card
    (NIC) address list provided.

    Args:
        nic_addr_list   A list of tuples per network interface card (NIC),
                        each containing e.g. address family and IP address.
                        More info:
                            https://psutil.readthedocs.io/en/latest/#psutil.net_if_addrs

    Returns:
        The IPv6 link-local address from the given list of NIC
        addresses, if exists

    Raises:
        NoLinkLocalAddressError if no IPv6 link-local address can be found
    """
    nics_with_addresses = psutil.net_if_addrs()
    nic_addr_list = nics_with_addresses[nic]
    for nic_addr in nic_addr_list:
        addr_family = nic_addr[0]
        # Remove any interface after the IP address with .split('%')[0] to
        # make sure we only get hex characters for IPv6Address(address)
        address = nic_addr[1].split("%")[0]

        if addr_family == socket.AF_INET6 and IPv6Address(address).is_link_local:
            return IPv6Address(address)

    raise NoLinkLocalAddressError(
        f"No link-local address was found for interface {nic}"
    )


async def _get_full_ipv6_address(host: str, port: int) -> Tuple[str, int, int, int]:
    """
    loop.getaddrinfo returns a list of tuples containing
    [(address_family, socktype, proto, canonname, socket_address)].
    As we need an IPv6 address, we can filter out all IPv4 addresses
    with getaddrinfo by specifying the family type with AF_INET6
    (instead of AF_INET). Additionally, filtering the socket type for
    TCP (by looking for socket.SOCK_STREAM) will yield just one list entry.

    In this case we will get one entry that will look like
    [ (<AddressFamily.AF_INET6: 30>, <SocketKind.SOCK_STREAM: 1>, 6, '',
    ('fe80::4fd:9dc8:b138:3bcc', 65334, 0, 5)) ]
    Check https://docs.python.org/3/library/asyncio-eventloop.html?highlight=getaddrinfo#asyncio.loop.getaddrinfo # noqa: E501
    loop.getaddrinfo is the async version of socket.getaddrinfo
    Check https://docs.python.org/3/library/socket.html#socket.getaddrinfo

    Socket_address is equal to e.g. ('fe80::4fd:9dc8:b138:3bcc', 65334, 0, 5)

    Breaking this address down, we have
    'fe80::4fd:9dc8:b138:3bcc' - IPv6 base address (host)
    65334 - the port
    0 - flowinfo
    5 - scope_id

    We need the entire socket address in order to bind it to the desired
    interface.

    For more info regarding IPv6 Addresses, check:
    https://www.notion.so/switchev/IPV6-Wiki-8c8179f74e5b4c4fb6fd6b980e58932e


    Args:
        host:   Must contain the interface associated with the ipaddress,
                e.g. 'fe80::4fd:9dc8:b138:3bcc%en0' where en0 is the
                interface
        port:   Is the port to bind the socket to

    Returns:
        A socket_address tuple (IPv6 base address, port, flowinfo, scope_ip),
        where the tuple entries are of type Tuple[str, int, int, int]
    """
    loop = asyncio.get_running_loop()

    addr_info_list = await loop.getaddrinfo(
        host, port, family=socket.AF_INET6, type=socket.SOCK_STREAM
    )
    # We only need the socket_address here
    _, _, _, _, socket_address = addr_info_list[0]
    return socket_address  # type: ignore[return-value]


def validate_nic(nic: str) -> None:
    """
    Checks if the Network Interface Card (NIC) provided exists on the system
    and contains a link-local address

    Args:
        nic (str): The network interface card identifier

    Raises:
        InterfaceNotFoundError if the specified interface could not be found
        or if no IPv6 link-local address could be found
    """
    try:
        _get_link_local_addr(nic)
    except KeyError as exc:
        raise InvalidInterfaceError(
            f"No interface {nic} with this name was found"
        ) from exc
    except NoLinkLocalAddressError as exc:
        raise InvalidInterfaceError(
            f"Interface {nic} has no link-local address " f"associated with it"
        ) from exc


async def get_link_local_full_addr(port: int, nic: str) -> Tuple[str, int, int, int]:
    """
    Provides the full IPv6 link-local address for the network interface card
    (NIC) specified. The full address contains the entire socket address, for example,

    ('fe80::4fd:9dc8:b138:3bcc', 65334, 0, 5)
    where:

    'fe80::4fd:9dc8:b138:3bcc' - is the IPv6 base address (host)
    65334 - port
    0 - flowinfo
    5 - scope_id

    Note:
        psutil.net_if_addrs() returns a dict, whose keys are the NIC names installed
        on the system and the values are a list of named tuples for each address
        assigned to the NIC.
        More info: https://psutil.readthedocs.io/en/latest/#psutil.net_if_addrs

    Args:
        port:   The port used for the IPv6 link-local address
        nic:    The Network Interface Card

    Returns:
        An IPv6 link-local address tuple (in the form of
        (IPv6 base address, port, flowinfo, scope_ip), where the tuple entries
        are of type Tuple[str, int, int, int])
    """
    ip_address = _get_link_local_addr(nic)

    nic_address = str(ip_address) + f"%{nic}"
    socket_address = await _get_full_ipv6_address(nic_address, port)
    return socket_address


def get_tcp_port() -> int:
    """
    A port number in the range of Dynamic Ports (49152-65535) as defined in
    IETF RFC 6335 are allowed for TCP.
    """
    return randint(49152, 65535)


def get_nic_mac_address(nic: str) -> str:
    """
    This method returns the MAC Addess of a specific NIC or the first one
    associated with an IPv6 link-local address.
    Args:
        nic (str): The Network Interface Card

    Returns:
        A MAC address in the format '8c:85:90:a3:96:e3' (str)

    """
    nics_with_addresses = psutil.net_if_addrs()
    nic_addr_list = nics_with_addresses[nic]
    for addr in nic_addr_list:
        if addr.family == psutil.AF_LINK:
            return addr.address
    raise MACAddressNotFound(f"MAC not found for NIC {nic}")


def get_ipv6_link_local_by_index(interface_index: int) -> str:
    """
    通过已知的接口索引获取IPv6链接本地地址

    Args:
        interface_index: 已知的网络接口索引

    Returns:
        IPv6链接本地地址字符串，如果找不到则返回None
    """
    try:
        # 获取所有网络接口
        interfaces = netifaces.interfaces()

        for iface in interfaces:
            # 获取接口的地址信息
            addrs = netifaces.ifaddresses(iface)

            # 检查是否有IPv6地址
            if netifaces.AF_INET6 in addrs:
                for addr_info in addrs[netifaces.AF_INET6]:
                    addr = addr_info['addr']

                    # 检查是否是链接本地地址
                    if addr.lower().startswith('fe80:'):
                        # 检查区域标识是否匹配我们的接口索引
                        if f'%{interface_index}' in addr:
                            return addr

                        # 如果没有区域标识或者区域标识不匹配，检查是否可以通过其他方式匹配
                        # 在某些情况下，Windows可能使用GUID而不是索引
                        # 我们可以尝试获取接口的GUID并检查是否匹配
                        try:
                            # 尝试获取接口的GUID
                            iface_guid = iface
                            # 在Windows上，netifaces的接口标识通常是GUID
                            # 我们可以尝试通过其他方法验证这个GUID是否对应我们的接口索引
                            if _is_guid_matching_index(iface_guid, interface_index):
                                # 如果匹配，返回这个地址（可能需要添加区域标识）
                                if '%' not in addr:
                                    addr = f"{addr}%{interface_index}"
                                return addr
                        except:
                            # 如果GUID匹配检查失败，继续下一个地址
                            continue

        # 如果没有找到匹配的地址，返回None
        return None

    except Exception as e:
        print(f"获取IPv6链接本地地址时出错: {e}")
        return None


def _is_guid_matching_index(guid: str, interface_index: int) -> bool:
    """
    检查GUID是否与接口索引匹配
    这是一个辅助函数，实际实现可能需要更复杂的方法
    """
    try:
        # 方法1: 使用netsh命令验证
        import subprocess
        import re

        result = subprocess.run(
            ["netsh", "interface", "ipv6", "show", "interfaces"],
            capture_output=True, text=True, check=True
        )

        # 在输出中查找匹配的索引和GUID
        current_index = None
        for line in result.stdout.split('\n'):
            # 查找接口索引
            if 'Idx' in line:
                match = re.search(r'Idx\s+:\s+(\d+)', line)
                if match:
                    current_index = int(match.group(1))

            # 查找GUID
            if current_index == interface_index and guid in line:
                return True

        return False

    except Exception:
        # 如果验证失败，返回False
        return False


def get_mac_by_index_netifaces(interface_index):
    """使用psutil通过接口索引获取MAC地址"""
    try:
        # 获取所有网络接口地址信息
        net_addrs = psutil.net_if_addrs()

        for interface_name, addresses in net_addrs.items():
            # 获取接口统计信息，其中包含接口索引
            stats = psutil.net_if_stats()
            if interface_name in stats:
                # 检查索引是否匹配
                if stats[interface_name].index == interface_index:
                    # 查找MAC地址
                    for addr in addresses:
                        if addr.family == psutil.AF_LINK:  # MAC地址
                            return addr.address
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None


def get_mac_by_interface(interface_name):
    """获取指定网络接口的MAC地址"""
    try:
        net_if_addrs = psutil.net_if_addrs()
        if interface_name in net_if_addrs:
            for addr in net_if_addrs[interface_name]:
                if addr.family == psutil.AF_LINK:
                    return addr.address
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None




