import time
from itertools import takewhile
import operator
from collections import OrderedDict
from abc import abstractmethod, ABC

BSEP_ST = b'||||'

import base64,json
def xprint(*xx):
    raise Exception('\n'.join(str(x) for x in xx)) 

import logging
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__file__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
log=logger.info

class IStorage(ABC):
    """
    Local storage for this node.
    IStorage implementations of get must return the same type as put in by set
    """

    @abstractmethod
    def __setitem__(self, key, value):
        """
        Set a key to the given value.
        """

    @abstractmethod
    def __getitem__(self, key):
        """
        Get the given key.  If item doesn't exist, raises C{KeyError}
        """

    @abstractmethod
    def get(self, key, default=None):
        """
        Get given key.  If not found, return default.
        """

    @abstractmethod
    def iter_older_than(self, seconds_old):
        """
        Return the an iterator over (key, value) tuples for items older
        than the given secondsOld.
        """

    @abstractmethod
    def __iter__(self):
        """
        Get the iterator for this storage, should yield tuple of (key, value)
        """


# class ForgetfulStorage(IStorage):
#     def __init__(self, ttl=604800):
#         """
#         By default, max age is a week.
#         """
#         self.data = OrderedDict()
#         self.ttl = ttl

#     def __setitem__(self, key, value):
#         if key in self.data:
#             del self.data[key]
#         self.data[key] = (time.monotonic(), value)
#         self.cull()

#     def cull(self):
#         for _, _ in self.iter_older_than(self.ttl):
#             self.data.popitem(last=False)

#     def get(self, key, default=None):
#         self.cull()
#         if key in self.data:
#             return self[key]
#         return default

#     def __getitem__(self, key):
#         self.cull()
#         return self.data[key][1]

#     def __repr__(self):
#         self.cull()
#         return repr(self.data)

#     def iter_older_than(self, seconds_old):
#         min_birthday = time.monotonic() - seconds_old
#         zipped = self._triple_iter()
#         matches = takewhile(lambda r: min_birthday >= r[1], zipped)
#         return list(map(operator.itemgetter(0, 2), matches))

#     def _triple_iter(self):
#         ikeys = self.data.keys()
#         ibirthday = map(operator.itemgetter(0), self.data.values())
#         ivalues = map(operator.itemgetter(1), self.data.values())
#         return zip(ikeys, ibirthday, ivalues)

#     def __iter__(self):
#         self.cull()
#         ikeys = self.data.keys()
#         ivalues = map(operator.itemgetter(1), self.data.values())
#         return zip(ikeys, ivalues)



import pickle
class HalfForgetfulStorage(IStorage):
    def __init__(self, fn='dbm.pickle', ttl=604800, log=None):
        """
        By default, max age is a week.
        """
        self.data = OrderedDict()
        self.fn = fn
        self.ttl = ttl

    def dump(self):
        with open(self.fn,'wb') as of:
            pickle.dump(self.data, of)

    def __setitem__(self, key, value):
        self.set(key,value)

    def keys(self): return self.data.keys()
    def items(self): return self.data.items()
    def values(self): return self.data.values()

    def set(self,key,value):
        log(f'HFS.set({key}) -> {value}')

        # store
        if key in self.data:
            del self.data[key]
        self.data[key] = (time.monotonic(), value)

        # save and prune
        self.dump()
        self.cull()

    def keys(self):
        return self.data.keys()

    def cull(self):
        for _, _ in self.iter_older_than(self.ttl):
            self.data.popitem(last=False)

    def get(self, key, default=None, incl_time=False):
        #self.cull()
        log(f'HFS.get({key}) -> ?')
        try:
            val=self.data[key]
            if not incl_time: val=val[1]
            log(f'HFS.get({key}) -> {val}')
            return val
        except (KeyError,IndexError) as e:
            pass
        
        return default

    def __getitem__(self, key):
        #self.cull()
        return self.get(key)

    def __repr__(self):
        #self.cull()
        return repr(self.data)

    def iter_older_than(self, seconds_old):
        min_birthday = time.monotonic() - seconds_old
        zipped = self._triple_iter()
        matches = takewhile(lambda r: min_birthday >= r[1], zipped)
        return list(map(operator.itemgetter(0, 2), matches))

    def _triple_iter(self):
        ikeys = self.data.keys()
        ibirthday = map(operator.itemgetter(0), self.data.values())
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ibirthday, ivalues)

    def __iter__(self):
        self.cull()
        ikeys = self.data.keys()
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ivalues)






# class HalfForgetfulStorage(ForgetfulStorage):
#     def __init__(self, fn='dbm', ttl=604800, log=print):
#         """
#         By default, max age is a week.
#         """
#         self.fn=fn
#         self.log=log
        
#         import pickledb
#         # self.data = pickledb.load(self.fn,False)
        
#         import dbm
#         self.data = dbm.open(self.fn,flag='cs')
        
#         # import shelve
#         # self.data = shelve.open(self.fn, flag='cs')
#         # from kivy.storage.jsonstore import JsonStore
#         # self.
        
        
#         self.ttl = ttl

#         self.log('have %s keys' % len(self))


#     def keys(self):
#         # return self.data.getall()
#         return self.data.keys()

#     def __len__(self):
#         return len(self.keys())

#     def __setitem__(self, key, value):
#         self.set(key,value)

#     def set(self, key,value):# try:
#         #self.log(f'key: {key},\nvalue:{value}')
#         #if type(value)==list and len(value)==2:
#         #    time,val_b = value
#         #    value = str(time).encode() + BSEP_ST + val_b
#         #self.log('newdat =',value)
        
#         self.data[key]=value
#         # return True

#     def get(self, key, default=None):
#         # print(f'??!?\n{key}\n{self.data[key]}')
#         # return self.data[key][1]
#         # (skip time part of tuple)
#         # val=self.data[key] if key in self.data else None
#         # self.log('VALLLL',val)
#         # if val is None: return None

#         # time_b,val_b = val.split(BSEP_ST)
#         # rval = (float(time_b.decode()), val_b)
#         # self.log('rvalll',rval)
#         # return rval
#         return self.data.get(key,None)
        
#     def __getitem__(self, key):
#         return self.get(key)
        
#         #return data_list
