"""
Thx to mmarquezs for his python 3 implementation of the jdownloader-api-handler.
source :https://github.com/mmarquezs/My.Jdownloader-API-Python-Library

This is a slightly modified python 2 version!
"""
import hashlib
import hmac
import requests
import json
import time
import urllib
import binascii
import base64
from Crypto.Cipher import AES

BS=16
pad = lambda s: s + ((BS - len(s) % BS) * chr(BS - len(s) % BS)).encode()
unpad = lambda s : s[0:-ord(s[-1])]

class jddevice(object):
    """
    Class that represents a JD device and it's functions
    
    """
    def __init__(self,jd,deviceDict):
        """ This functions initializates the device instance.
        It uses the provided dictionary to create the device.

        :param deviceDict: Device dictionary
        
        """
        self.name=deviceDict["name"]
        self.dId=deviceDict["id"]
        self.dType=deviceDict["type"]
        self.jd=jd

    def action(self, action=False,httpaction = "POST",params=False,postparams=False):
        """
        Execute any action in the device using the postparams and params.
        
        All the info of which params are required and what are they default value, type,etc 
        can be found in the MY.Jdownloader API Specifications ( https://goo.gl/pkJ9d1 ).


        :param params: Params in the url, in a list of tuples. Example: /example?param1=ex&param2=ex2 [("param1","ex"),("param2","ex2")]
        :param postparams: List of Params that are send in the post. 

        
        """
        if not action:
            return False
        actionurl=self.__actionUrl()
        if not actionurl:
            return False
        if postparams:
            post=[]
            for postparam in postparams:
                if type(postparam)==type({}):
                    keys=list(postparam.keys())
                    data="{"
                    for param in keys:
                        if type(postparam[param])==bool:
                            data+='\\"'+param+'\\" : '+str(postparam[param]).lower()+','
                        elif type(postparam[param])==str:
                            data+='\\"'+param+'\\" : \\"'+postparam[param]+'\\",'
                        else:
                            data+='\\"'+param+'\\" : '+str(postparam[param])+','
                    data=data[:-1]+"}"
                else:
                    data=postparam
                post+=[data]
            if not params:
                text=self.jd.call(actionurl,httpaction,rid=False,postparams=post,action=action)
            else:
                text=self.jd.call(actionurl,httpaction,rid=False,params=params,postparams=post,action=action)
        else:
            text=self.jd.call(actionurl,httpaction,rid=False,action=action,params=params)
        if not text:
            return False
        return text
    
    def addLinks(self, params=[{"autostart" : False,"links" : "","packageName" : "","extractPassword" : "","priority" : "DEFAULT","downloadPassword" : "","destinationFolder" : ""}]):
        resp=self.action("/linkgrabberv2/addLinks",postparams=params)
        self.jd.updateRid()
        return resp

    def getLinks(self, params = [{"bytesTotal":False, "comment":False, "status":False, "enabled":False, "maxResults":-1, "startAt": 0, "packageUUIDs":"", "host":False, "url":False, "availability":False, "variantIcon":False, "variantName":False, "variantID":False, "variants":False, "priority":False}]):
        resp = self.action("/linkgrabberv2/queryLinks", postparams=params)
        self.jd.updateRid()
        return resp

    def getPackageCount(self):
        resp = self.action(action = "/linkgrabberv2/getPackageCount")
        self.jd.updateRid()
        return resp

    def getPackages(self, params = [{"bytesTotal":False,"comment":False,"status":False,"enabled":False,"maxResults":-1,"startAt":0,"packageUUIDs":"","childCount":False,"hosts":False,"saveTo":False,"availableOfflineCount":False,"availableOnlineCount":False,"availableTempUnknownCount":False,"availableUnknownCount":False}]):
        resp = self.action("/linkgrabberv2/queryPackages", postparams=params)
        self.jd.updateRid()
        return resp

    def removeLinks(self, links = []):
        print("start") #todo remove it
        resp = self.action("/linkgrabberv2/removeLinks", httpaction = "GET", params = links)
        self.jd.updateRid()
        return resp
        
    def __actionUrl(self):
        if not self.jd.sessiontoken:
            return False
        return "/t_"+self.jd.sessiontoken+"_"+self.dId


class myjdapi(object):
    """
    Main class for connecting to JD API.

    """
    
    def __init__(self,email=None,password=None,appkey="testJD"):
        """ This functions initializates the myjdapi object.
        If email and password are given it will also connect try 
        with that account.
        If it fails to connect it won't provide any error,
        you can check if it worked by checking if sessiontoken 
        is not an empty string.
        
        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        
        """
        self.rid=int(time.time())
        self.api_url = "http://api.jdownloader.org"
        self.appkey = appkey
        self.apiVer = 1
        self.__devices = []
        self.loginSecret = False
        self.deviceSecret = False
        self.sessiontoken = False
        self.regaintoken = False
        self.serverEncryptionToken = False
        self.deviceEncryptionToken = False

        if email!=None and password!=None:
            self.connect(email,password)
            # Make an exception or something if it fails? Or simply ignore the error?

    def __secretcreate(self,email,password,domain):
        """Calculates the loginSecret and deviceSecret

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :param domain: The domain , if is for Server (loginSecret) or Device (deviceSecret) 
        :return: secret hash

        """
        h = hashlib.sha256()
        h.update(email.lower().encode('utf-8')+password.encode('utf-8')+domain.lower().encode('utf-8'))
        secret=h.digest()
        return secret

    def __updateEncryptionTokens(self):
        """ 
        Updates the serverEncryptionToken and deviceEncryptionToken

        """
        if not self.serverEncryptionToken:
            oldtoken=self.loginSecret
        else:
            oldtoken=self.serverEncryptionToken            
        h = hashlib.sha256()
        h.update(oldtoken+bytearray.fromhex(self.sessiontoken))
        self.serverEncryptionToken=h.digest()
        h = hashlib.sha256()
        h.update(self.deviceSecret+bytearray.fromhex(self.sessiontoken))
        self.deviceEncryptionToken=h.digest()

    def __signaturecreate(self,key,data):
        """
        Calculates the signature for the data given a key.

        :param key: 
        :param data:

        """
        h = hmac.new(key,data.encode('utf-8'),hashlib.sha256)
        signature=h.hexdigest()
        return signature

    def __decrypt(self,secretServer,data):
        """
        Decrypts the data from the server using the provided token

        :param secretServer: 
        :param data:

        """
        iv=secretServer[:len(secretServer)//2]        
        key=secretServer[len(secretServer)//2:]
        decryptor = AES.new(key,AES.MODE_CBC,iv)
        decrypted_data = unpad(decryptor.decrypt(base64.b64decode(data)))
        return decrypted_data

    def __encrypt(self,secretServer,data):
        """
        Encrypts the data from the server using the provided token

        :param secretServer: 
        :param data:

        """
        data=pad(data.encode('utf-8'))
        iv=secretServer[:len(secretServer)//2]        
        key=secretServer[len(secretServer)//2:]
        encryptor = AES.new(key,AES.MODE_CBC,iv)
        encrypted_data = base64.b64encode(encryptor.encrypt(data))
        return encrypted_data.decode('utf-8')
    
    def updateRid(self):
        """
        Adds 1 to rid
        """
        self.rid=int(time.time())
        #self.rid=self.rid+1

    def connect(self,email,password):
        """Establish connection to api

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :returns: boolean -- True if succesful, False if there was any error.

        """
        self.loginSecret=self.__secretcreate(email,password,"server")
        self.deviceSecret=self.__secretcreate(email,password,"device")
        text=self.call("/my/connect","GET",rid=True,params=[("email",email),("appkey",self.appkey)])
        if not text:
            return False
        self.updateRid()
        self.sessiontoken=text["sessiontoken"]
        self.regaintoken=text["regaintoken"]
        self.__updateEncryptionTokens()
        return True

    def reconnect(self):
        """
        Restablish connection to api.

        :returns: boolean -- True if succesful, False if there was any error.

        """
        if not self.sessiontoken:
            return False
        text=self.call("/my/reconnect","GET",rid=True,params=[("sessiontoken",self.sessiontoken),("regaintoken",self.regaintoken)])
        if not text:
            return False
        self.updateRid()
        self.sessiontoken=text["sessiontoken"]
        self.regaintoken=text["regaintoken"]
        self.__updateEncryptionTokens()
        return True

    def disconnect(self):
        """
        Disconnects from  api

        :returns: boolean -- True if succesful, False if there was any error.

        """
        if not self.sessiontoken:
            return False
        text=self.call("/my/disconnect","GET",rid=True,params=[("sessiontoken",self.sessiontoken)])
        if not text:
            return False
        self.updateRid()
        self.loginSecret = ""
        self.deviceSecret = ""
        self.sessiontoken = ""
        self.regaintoken = ""
        self.serverEncryptionToken = False
        self.deviceEncryptionToken = False
        return True

    def getDevices(self):
        """
        Gets available devices. Use listDevices() to get the devices list. 

        :returns: boolean -- True if succesful, False if there was any error.

        """
        if not self.sessiontoken:
            return False
        text=self.call("/my/listdevices","GET",rid=True,params=[("sessiontoken",self.sessiontoken)])
        if not text:
            return False
        self.updateRid()
        self.__devices=text["list"]
        return True

    def listDevices(self):
        """
        Returns available devices. Use getDevices() to update the devices list. 

        Each device in the list is a dictionary like this example:
        
        { 
            'name': 'Device',

            'id': 'af9d03a21ddb917492dc1af8a6427f11',

            'type': 'jd'

        }

        :returns: list -- list of devices.

        """
        return self.__devices

    def getDevice(self,deviceid=False,name=False):
        """
        Returns a jddevice instance of the device
        
        :param deviceid:
        
        """
        if deviceid:
            for device in self.__devices:
                if device["id"]==deviceid:
                    return jddevice(self,device)
        elif name:
            for device in self.__devices:
                if device["name"]==name:
                    return jddevice(self,device)
        return False

    def call(self,url,httpaction="GET",rid=True,params=False,postparams=False,action=False):
        if not action:
            if (params):
                call=url
                for index,param in enumerate(params):
                    if index==0:
                        if type(param) == type(""):
                            call+="?"+str((param))
                        else:
                            call+="?"+param[0]+"="+urllib.quote_plus(param[1])
                    else:
                        if type(param) == type(""):
                            call+="&"+str((param))
                        else:
                            call+="&"+param[0]+"="+urllib.quote_plus(param[1])
                        # Todo : Add an exception if the param is loginSecret so it doesn't get url encoded.
                if rid:
                    call+="&rid="+str(self.rid)
                if not self.serverEncryptionToken:
                    call+="&signature="+str(self.__signaturecreate(self.loginSecret,call))
                else:
                    call+="&signature="+str(self.__signaturecreate(self.serverEncryptionToken,call))
            if (postparams):
                pass
        
        else:
            call=url+action
            if (params):
                
                for index,param in enumerate(params):
                    if index==0:
                        if type(param) == type(""):
                            call+="?"+str((param))
                        else:
                            call+="?"+param[0]+"="+urllib.quote_plus(param[1])
                    else:
                        if type(param) == type(""):
                            call+="&"+str((param))
                        else:
                            call+="&"+param[0]+"="+urllib.quote_plus(param[1])
                        # Todo : Add an exception if the param is loginSecret so it doesn't get url encoded.
                if rid:
                    call+="&rid="+str(self.rid)

                if not self.serverEncryptionToken:
                    call+="&signature="+str(self.__signaturecreate(self.loginSecret,call))
                else:
                    call+="&signature="+str(self.__signaturecreate(self.serverEncryptionToken,call))
            if (postparams):
                data='{"url":"'+action+'","params":["'
                for index,param in enumerate(postparams):
                    if index != len(postparams)-1:
                        data+=param+'","'
                    else:
                        data+=param+'"],'
            else:
                data='{"url":"'+action+'",'
            data+='"rid":'+str(self.rid)+',"apiVer":1}'
            encrypteddata=self.__encrypt(self.deviceEncryptionToken,data);

        url=self.api_url+call
        if httpaction=="GET":
            encryptedresp=requests.get(url)
        elif httpaction=="POST":
            encryptedresp=requests.post(url,headers={"Content-Type": "application/aesjson-jd; charset=utf-8"},data=encrypteddata)
        if encryptedresp.status_code != 200:
            return False
        if not action:
            if not self.serverEncryptionToken:
                response=self.__decrypt(self.loginSecret,encryptedresp.text) 
            else:
                response=self.__decrypt(self.serverEncryptionToken,encryptedresp.text)
        else:
            response=self.__decrypt(self.deviceEncryptionToken,encryptedresp.text)
        jsondata=json.loads(response.decode('utf-8'))
        if jsondata['rid']!=self.rid:
            return False
        return jsondata