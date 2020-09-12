"""
Storage for both keys and data
"""
import os,sys; sys.path.append(os.path.abspath(os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')),'..')))
from komrade import *
from simplekv.fs import FilesystemStore
from simplekv.memory.redisstore import RedisStore
import redis
import hashlib,os
import zlib



LOG_GET_SET = True



class Crypt(Logger):
    def __init__(self,name=None,fn=None,cell=None,init_d=None,use_secret=CRYPT_USE_SECRET,path_secret=PATH_CRYPT_SECRET):
        if not name and fn: name=os.path.basename(fn).replace('.','_')

        if use_secret and path_secret:
            if not os.path.exists(path_secret):
                self.secret = get_random_binary_id()
                from komrade.backend.keymaker import make_key_discreet
                self.log('shhh! creating secret:',make_key_discreet(self.secret))
                with open(path_secret,'wb') as of:
                    of.write(self.secret)
            else:
                with open(path_secret,'rb') as f:
                    self.secret = f.read()
        else:
            self.secret = b''

        self.name,self.fn,self.cell = name,fn,cell
        self.store = FilesystemStore(self.fn)
        if init_d:
            for k,v in init_d.items():
                try:
                    self.store.put(k,v)
                except OSError as e:
                    self.log('!!',e)
                    self.log('!! key ->',k)
                    self.log('!! val ->',v)
                    raise KomradeException()
                    

    def log(self,*x):
        if LOG_GET_SET:
            super().log(*x)
        
    def hash(self,binary_data):
        return hasher(binary_data,self.secret)
        # return b64encode(hashlib.sha256(binary_data + self.secret).hexdigest().encode()).decode()
        # return zlib.adler32(binary_data)

    def force_binary(self,k_b):
        if k_b is None: return None
        if type(k_b)==str: k_b=k_b.encode()
        if type(k_b)!=bytes: k_b=k_b.decode()
        return k_b

    def package_key(self,k,prefix=''):
        if not k: return b''
        k_b = self.force_binary(k)
        k_b2 = self.force_binary(prefix) + k_b
        return k_b2

    def package_val(self,k):
        k_b = self.force_binary(k)
        if self.cell is not None:
            k_b = self.cell.encrypt(k_b)
        if not isBase64(k_b): k_b = b64encode(k_b)
        return k_b

    def unpackage_val(self,k_b):
        try:
            if self.cell is not None:
                k_b = self.cell.decrypt(k_b)
        except ThemisError as e:
            self.log('error decrypting!',e,k_b)
            return
        if isBase64(k_b): k_b = b64decode(k_b)
        return k_b

    def has(self,k,prefix=''):
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        try:
            v=self.store.get(k_b_hash)
            return True
        except KeyError:
            return False


    def set(self,k,v,prefix=''):
        if self.has(k,prefix=prefix):
            self.log("I'm afraid I can't let you do that, overwrite someone's data!")
            return (False,None,None)
        
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        v_b=self.package_val(v)
        self.log(f'''
Crypt.set(
    prefix = {prefix},
    
    k = {k},
    
    k_b = {k_b},
    
    k_hash = {k_b_hash},
    
    val={v_b}
)')
        ''')
        # store
        self.store.put(k_b_hash,v_b)
        return (True,k_b_hash,v_b)

    def exists(self,k,prefix=''):
        return self.has(k,prefix=prefix)

    def key2hash(self,k,prefix=''):
        return self.hash(
            self.package_key(
                prefix + k
            )
        )

    def get(self,k,prefix=''):
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        try:
            v=self.store.get(k_b_hash)
        except KeyError:
            return None
        v_b=self.unpackage_val(v)
        return v_b


class KeyCrypt(Crypt):
    def __init__(self):
        return super().__init__(name=PATH_CRYPT_CA_KEYS.replace('.','_'))


class DataCrypt(Crypt):
    def __init__(self):
        return super().__init__(name=PATH_CRYPT_CA_DATA.replace('.','_'))


from collections import defaultdict
class CryptMemory(Crypt):
    def __init__(self):
        self.data = defaultdict(None) 
        self.crypt = defaultdict(None)
        self.cell = None
    
    def set(self,k,v,prefix=''):
        k_b=self.package_key(k,prefix=prefix)
        v_b=self.package_val(v)
        self.data[k]=v_b
        self.crypt[k_b]=v_b
    


if __name__=='__main__':
    crypt = Crypt('testt')

    print(crypt.set('hellothere',b'ryan'))

    # print(crypt.get(b'hello there'))