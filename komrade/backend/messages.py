import os,sys; sys.path.append(os.path.abspath(os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')),'..')))
from komrade import *
from komrade.backend import *

def is_valid_msg_d(msg_d):
    if not type(msg_d)==dict: return False
    to_name=msg_d.get('_to_name')
    to_pub=msg_d.get('_to_pub')
    from_name=msg_d.get('_from_name')
    from_pub=msg_d.get('_from_pub')
    msg=msg_d.get('_msg')
    if to_name and to_pub and from_name and from_pub and msg: return True
    return False


class Message(Logger):
    def __init__(self,msg_d,from_whom=None,to_whom=None,messenger=None,embedded_msg=None,is_encrypted=False):
        # check input
        if not is_valid_msg_d(msg_d):
            raise KomradeException('This is not a valid msg_d:',msg_d)
        # set fields
        self.msg_d=msg_d
        self.to_name=msg_d.get('_to_name')
        self.to_pubkey=msg_d.get('_to_pub')
        self.from_name=msg_d.get('_from_name')
        self.from_pubkey=msg_d.get('_from_pub')
        self.msg=msg_d.get('_msg')
        self.embedded_msg=embedded_msg  # only if this message has an embedded one
        self._route=msg_d.get(ROUTE_KEYNAME)
        self._from_whom=from_whom
        self._to_whom=to_whom
        self.messenger=None
        self._is_encrypted=None
        # get operators straight away?
        if not self._from_whom or not self._to_whom:
            self.get_whoms()

    @property
    def data(self):
        md={}
        msg_d=self.msg_d
        while msg_d:
            for k,v in msg_d.items(): md[k]=v
            msg_d = msg_d.get('_msg',{})
            if type(msg_d)!=dict: msg_d=None
        if '_msg' in md and type(md['_msg']) == dict:
            del md['_msg']
        del md[ROUTE_KEYNAME]
        return md

    def mark_return_to_sender(self):
        self._from_whom,self._to_whom = self._to_whom,self._from_whom
        self.msg_d['_from_pub'],self.msg_d['_to_pub'] = self.msg_d['_to_pub'],self.msg_d['_from_pub'],
        self.msg_d['_from_name'],self.msg_d['_to_name'] = self.msg_d['_to_name'],self.msg_d['_from_name'],

    def __repr__(self):
        msg_d_str=dict_format(self.msg_d,tab=6)
        return f"""
    
    <MSG>
        self.from_whom={self.from_whom}
        self.to_whom={self.to_whom}
        self.msg_d={msg_d_str}
    </MSG>

        """


    def get_whom(self,name):
        if name == OPERATOR_NAME:
            return TheOperator()
        if name == TELEPHONE_NAME:
            return TheTelephone()
        from komrade.backend.Caller import Caller
        return Caller(name)

    @property
    def from_whom(self):
        if not self._from_whom:
            self._from_whom,self._to_whom = self.get_from_whoms()
        return self._from_whom

    @property
    def to_whom(self):
        if not self._to_whom:
            self._from_whom,self._to_whom = self.get_from_whoms()
        return self._to_whom
    
    ## loading messages
    def get_whoms(self):
        if self._from_whom is not None and self._to_whom is not None:
            return (self._from_whom,self._to_whom) 
        alleged_from_whom = self.get_whom(self.from_name)
        alleged_to_whom = self.get_whom(self.to_name)
        if not self.records_match(alleged_from_whom,alleged_to_whom):
            raise KomradeException('Records of from_whoms on The Operator and the from_whom do not match. Something fishy going on?')
        else:
            self._from_whom = alleged_from_whom
            self._to_whom = alleged_to_whom
        return (self._from_whom,self._to_whom)

    def from_whom_records_match(self,alleged_from_whom,alleged_to_whom):
        alleged_from_whom_name = self.from_name
        alleged_from_whom_pubkey = self.from_pubkey
        alleged_to_whom_name = self.to_name
        alleged_to_whom_pubkey = self.to_pubkey

        # self.log('from_whom names:',alleged_from_whom.name, alleged_from_whom_name)
        # self.log('from_whom pubs:',alleged_from_whom.pubkey, alleged_from_whom_pubkey)
        # self.log('to_whom names:',alleged_to_whom.name, alleged_to_whom_name)
        # self.log('to_whom pubs:',alleged_to_whom.pubkey, alleged_to_whom_pubkey)

        if alleged_to_whom.name != alleged_to_whom_name:
            return False
        if alleged_from_whom.name != alleged_from_whom_name:
            return False
        if alleged_to_whom.pubkey != alleged_to_whom_pubkey:
            return False
        if alleged_from_whom.pubkey != alleged_from_whom_pubkey:
            return False
        return True

    def decrypt(self,recursive=False):
        # 
        if not self.is_encrypted: return
        # get from_whoms
        self.log(f'attempting to decrypt msg',self.msg) # {self.msg} from {from_whom} to {to_whom}')

        # decrypt msg
        decr_msg_b = SMessage(
            self.to_whom.privkey,
            self.from_whom.pubkey
        ).unwrap(self.msg)
        
        self.log('Am I decrypted?',decr_msg_b)
        
        decr_msg = pickle.loads(decr_msg_b)
        self.log('unpickled:',decr_msg)

        self.msg_encr = self.msg
        self.msg = decr_msg
        self.msg_d['_msg'] = decr_msg

        self.log('got decr msg back:',decr_msg)
        
        # now, is the decrypted message itself a message?
        if is_valid_msg_d(decr_msg):
            self.log('this is a valid msg in its own right!',decr_msg)
            # then ... make that, a message object and decrypt it too!
            self.msg = Message(decr_msg)
        
        # for now this should be rolled out individually ,like an onion
        # ring_ring on client -> route_msg on server
        # so we don't need or want to decrypt all at once
        if recursive:
            self.msg.decrypt()

        self.log(f'done decrypting! {self}')
        return decr_msg

    @property
    def is_encrypted(self):
        return type(self.msg) == bytes
        # if self.msg._is_encrypted is not None:
            # return self.msg._is_encrypted
        


    def encrypt(self): # each child message should already be encrypted before coming to its parent message ,recursive=False):
        if self._is_encrypted: return
        # self.log(f'attempting to encrypt msg {self.msg} from {self.from_whom} to {self.to_whom}')
        self.log(f'About to encrypt self.msg! I now look like v1: {self}')
        
        # binarize msg
        msg_b = pickle.dumps(self.msg)
        # self.log('msg_b = ',msg_b)

        # encrypt it!
        msg_encr = SMessage(
            self.from_whom.privkey,
            self.to_whom.pubkey,
        ).wrap(msg_b)

        self.msg_decr = self.msg
        self.msg = msg_encr
        self.msg_d['_msg'] = msg_encr
        self.log(f'Encrypted! I now look like v2: {self}')
        self._is_encrypted = True



    

    ## msg properties
    @property
    def has_embedded_msg(self):
        return type(self.msg) == Message

    @property
    def messages(self):
        # move through msgs recursively
        def _msgs():
            msg=self
            while True:
                yield msg
                if msg.has_embedded_msg:
                    msg=msg.msg
                break
        return list(_msgs())

    @property
    def route(self):
        if type(self.msg)==dict:
            rte=self.msg.get(ROUTE_KEYNAME)
            if rte:
                return rte
        if self.has_embedded_msg:
            return self.msg.route
        return None
        


    


def test_msg():
    phone = TheTelephone()
    op = TheOperator()

    pprint(op.pubkey)
    print('?keychains?')
    pprint(phone.pubkey)
    
    msg={'_route':'forge_new_keys'}


    resp_msp_obj = phone.ring_ring(msg)
    print(resp_msp_obj) 


if __name__ == '__main__':
    test_msg()