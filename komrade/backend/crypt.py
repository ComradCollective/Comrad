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



LOG_GET_SET = 0





class Crypt(Logger):
    def __init__(self,name=None,fn=None,cell=None,init_d=None,use_secret=CRYPT_USE_SECRET,path_secret=PATH_CRYPT_SECRET,encrypt_values=True,path_encrypt_key=PATH_CRYPT_SECRET_KEY):
        if not name and fn: name=os.path.basename(fn).replace('.','_')
        self.name,self.fn,self.cell=name,fn,cell
        self.encryptor_key = None


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

        self.encrypt_values = encrypt_values
        
        if encrypt_values:
            from komrade.backend.keymaker import make_key_discreet_str
            from komrade.backend.keymaker import KomradeSymmetricKeyWithoutPassphrase


            if self.cell:
                pass
            elif path_encrypt_key:
                if not os.path.exists(path_encrypt_key):
                    self.encryptor_key = KomradeSymmetricKeyWithoutPassphrase()
                    with open(path_encrypt_key,'wb') as of:
                        of.write(self.encryptor_key.data)
                        self.log(f'shhh! creating secret at {path_encrypt_key}:',make_key_discreet_str(self.encryptor_key.data_b64_s))
                else:
                    with open(path_encrypt_key,'rb') as f:
                        self.encryptor_key = KomradeSymmetricKeyWithoutPassphrase(
                            key=f.read()
                        )
            else:
                self.log('cannot encrypt values!')
        else:
            self.encryptor_key=None

        if self.encryptor_key and not self.cell: self.cell = self.encryptor_key.cell
        

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
        # if self.cell is not None:
            # k_b = self.cell.encrypt(k_b)
        # if not isBase64(k_b): k_b = b64encode(k_b)
        return k_b

    def unpackage_val(self,k_b):
        # from komrade import ThemisError
        # try:
            # if self.cell is not None:
                # k_b = self.cell.decrypt(k_b)
        # except ThemisError as e:
            # self.log('error decrypting!',e,k_b)
            # return
        # if isBase64(k_b): k_b = b64decode(k_b)
        return k_b

    def has(self,k,prefix=''):
        return bool(self.get(k,prefix=prefix))


    def set(self,k,v,prefix='',override=False):
        if self.has(k,prefix=prefix) and not override:
            #self.log(f"I'm afraid I can't let you do that, overwrite someone's data!\n\nat {prefix}{k} = {v}")
            return False #(False,None,None)
        
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        v_b=self.package_val(v)
        if not override:
            self.log(f'''Crypt.set(\n\t{k_b}\n\n\t{k_b_hash}\n\n\t{v_b}\n)''')
        # store
        # stop
        self.store.put(k_b_hash,v_b)
        #return (True,k_b_hash,v_b)
        # self.log('now keys are:',list(self.store.iter_keys()))
        return True

    def exists(self,k,prefix=''):
        return self.has(k,prefix=prefix)

    def key2hash(self,k,prefix=''):
        return self.hash(
            self.package_key(
                prefix + k
            )
        )

    def delete(self,k,prefix=''):
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        r=self.store.delete(k_b_hash)
        return r
        

    def get(self,k,prefix=''):
        k_b=self.package_key(k,prefix=prefix)
        k_b_hash = self.hash(k_b)
        try:
            v=self.store.get(k_b_hash)
        except KeyError:
            return None
        v_b=self.unpackage_val(v)
        # self.log(f'Crypt.get(\n\t{prefix}{k}\n\n\t{v_b}')
        return v_b


class KeyCrypt(Crypt):
    def __init__(self):
        return super().__init__(name=PATH_CRYPT_CA_KEYS.replace('.','_'))


class DataCrypt(Crypt):
    def __init__(self):
        return super().__init__(name=PATH_CRYPT_CA_DATA.replace('.','_'))



class CryptList(Crypt):  # like inbox
    def __init__(self,
            crypt,
            keyname,
            prefix='',
            encryptor_func=lambda x: x,
            decryptor_func=lambda x: x):
        
        self.crypt=crypt
        self.keyname=keyname
        self.prefix=prefix
        self.encryptor_func=encryptor_func
        self.decryptor_func=decryptor_func
    
    @property
    def val_b_encr(self):
        return self.crypt.get(
            self.keyname,
            prefix=self.prefix
        )
    
    @property
    def val_b(self):
        val_b_encr=self.val_b_encr
        if not val_b_encr: return None
        return self.decryptor_func(val_b_encr)
    
    @property
    def values(self):
        try:
            val_b=self.val_b
        except ThemisError:
            self.log(f'!! DECRYPTION FAILURE: {e}')
            return []
        if not val_b: return []
        return pickle.loads(val_b)

    def prepend(self,x_l):
        return self.append(x,insert=0)

    def append(self,x_l,insert=None):
        if type(x_l)!=list: x_l=[x_l]
        val_l = self.values
        x_l = [x for x in x_l if not x in set(val_l)]
        # print('val_l =',val_l)
        for x in x_l:
            if insert is not None:
                val_l.insert(insert,x)
            else:
                val_l.append(x)
            # print('val_l2 =',val_l)
        
        return self.set(val_l)

    def set(self,val_l):
        val_b = pickle.dumps(val_l)
        val_b_encr = self.encryptor_func(val_b)
        return self.crypt.set(
            self.keyname,
            val_b_encr,
            prefix=self.prefix,
            override=True
        )

    def remove(self,l):
        if type(l)!=list: l=[l]
        lset=set(l)
        values = [x for x in self.values if x not in lset]
        return self.set(values)



if __name__=='__main__':
    crypt = Crypt('testt')

    from komrade import KomradeSymmetricKeyWithPassphrase
    key = KomradeSymmetricKeyWithPassphrase()


    crypt_list = CryptList(
        crypt=crypt,
        keyname='MyInbox2',
        prefix='inbox',
        encryptor_func=key.encrypt,
        decryptor_func=key.decrypt
    )

    print(crypt_list.values)

    print(crypt_list.remove('cool thing 0'))

    # print(crypt_list.append('cool thing 1'))
    
    print(crypt_list.prepend('cool thing 0'))

    print(crypt_list.values)