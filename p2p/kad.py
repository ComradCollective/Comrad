###
# Kademlia patches
###

from kademlia.storage import *
from kademlia.network import *
from kademlia.routing import RoutingTable
from rpcudp.protocol import RPCProtocol
import os


PROXY_ADDR = ('0.0.0.0',8368)

class HalfForgetfulStorage(ForgetfulStorage):
    def __init__(self, ttl=604800):
        """
        By default, max age is a week.
        """
        self.fn='sto.dat'
        if not os.path.exists(self.fn):
            self.data={}
        else:
            with open(self.fn,'rb') as f:
                self.data=pickle.load(f)


        #print('>> loaded %s keys' % len(self.data))

        #self.data = pickle.open('sto.dat','rb') #,writeback=True)
        # self.data = self.store.get('OrderedDict',OrderedDict())
        self.ttl = ttl

    def __setitem__(self, key, value):
        self.data[key] = (time.monotonic(), value)
        self.write()

    def set(key,value):
        self[key]=value

    def write(self):
        with open(self.fn,'wb') as f:
            pickle.dump(self.data, f)

    def get(self, key, default=None):
        # self.cull()
        print('looking for key: ', key)
        if key in self.data:
            print('found it!')
            return self[key]
        return default

    def __getitem__(self, key):
        return self.data[key][1]





"""UDP proxy server."""

import asyncio


class ProxyDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, remote_address=PROXY_ADDR):
        self.remote_address = remote_address
        self.remotes_d = {}
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes_d:
            self.remotes_d[addr].transport.sendto(data)
            return
        loop = asyncio.get_event_loop()
        self.remotes_d[addr] = RemoteDatagramProtocol(self, addr, data)
        coro = loop.create_datagram_endpoint(
            lambda: self.remotes_d[addr], remote_addr=self.remote_address)
        asyncio.ensure_future(coro)


class RemoteDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, proxy, addr, data):
        print('RemoteDP got:',proxy,addr,data)
        self.proxy = proxy
        self.addr = addr
        self.data = data
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.data)

    def datagram_received(self, data, _):
        self.proxy.transport.sendto(data, self.addr)

    def connection_lost(self, exc):
        self.proxy.remotes.pop(self.attr)


async def start_datagram_proxy(protocol_class, bind, port, remote_host, remote_port):
    loop = asyncio.get_event_loop()
    protocol = protocol_class((remote_host, remote_port))
    return await loop.create_datagram_endpoint(
        lambda: protocol, local_addr=(bind, port))


def main(bind='0.0.0.0', port=8888,
        remote_host='0.0.0.0', remote_port=9999):
    loop = asyncio.get_event_loop()
    print("Starting datagram proxy...")
    coro = start_datagram_proxy(bind, port, remote_host, remote_port)
    transport, _ = loop.run_until_complete(coro)
    print("Datagram proxy is running...")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    print("Closing transport...")
    transport.close()
    loop.close()


if __name__ == '__main__':
    main()

log = logging.getLogger('kademlia')  # pylint: disable=invalid-name



class KadProtocol(KademliaProtocol):
    # remote_address = PROXY_ADDR
    # REMOTES_D={}

    def __init__(self, source_node, storage, ksize):
        RPCProtocol.__init__(self,wait_timeout=5)
        self.router = RoutingTable(self, ksize, source_node)
        self.storage = storage
        self.source_node = source_node

    # def datagram_received(self, data, addr):
    #     #if not hasattr(self,'remotes_d'): self.remotes_d={}
    #     # print('\n\n!?!?!?',self.REMOTES_D, type(self.REMOTES_D))
    #     # if addr in self.REMOTES_D:
    #     #     self.REMOTES_D[addr].transport.sendto(data)
    #     #     return
    #     loop = asyncio.get_event_loop()
    #     # self.REMOTES_D[addr] = RemoteDatagramProtocol(self, addr, data)
    #     RDP = RemoteDatagramProtocol(self, addr, data)
    #     coro = loop.create_datagram_endpoint(lambda: RDP, remote_addr=self.remote_address)
    #     asyncio.ensure_future(coro)

    def handle_call_response(self, result, node):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if not result[0]:
            log.warning("no response from %s, ?removing from router", node)
            # self.router.remove_contact(node)
            return result

        log.info("got successful response from %s", node)
        self.welcome_if_new(node)
        return result


class KadServer(Server):
    protocol_class = KadProtocol # KadProtocol #KademliaProtocol


    async def set_digest(self, dkey, value):
        """
        Set the given SHA1 digest key (bytes) to the given value in the
        network.
        """
        node = Node(dkey)

        nearest = self.protocol.router.find_neighbors(node)
        if not nearest:
            log.warning("There are no known neighbors to set key %s",
                        dkey.hex())
            return False

        spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                 self.ksize, self.alpha)
        nodes = await spider.find()
        log.info("setting '%s' on %s", dkey.hex(), list(map(str, nodes)))

        # if this node is close too, then store here as well
        neighbs=[n.distance_to(node) for n in nodes]
        biggest = max(neighbs) if neighbs else 0
        if self.node.distance_to(node) < biggest:
            self.storage[dkey] = value
        results = [self.protocol.call_store(n, dkey, value) for n in nodes]
        # return true only if at least one store call succeeded
        return any(await asyncio.gather(*results))


