#!/usr/bin/env python3

from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Cryptodome.Hash import SHA512, SHA256, SHA1
from Cryptodome.Signature import pss
from Crypto import Random

import base64

class SecurityRSA:
    def generate_keypair(self, keysize:int = 2048) -> tuple:

        """Generate public and private keypair and return them.

        Returns:
            public_key (str), private_key (str)
        """

        key = RSA.generate(keysize)
        self.private_key = key.export_key()

        self.public_key = key.publickey().exportKey()

        return self.public_key, self.private_key


    @staticmethod
    def generate_keypair_write( 
            private_key_filepath: str="private.pem", 
            public_key_filepath: str="public.pem", keysize: int=2048) -> tuple:

        """Generate public and private keypair and write them.
        
        Args:
            public_key_filepath (str): Absolute filepath to where the public key should be written and stored.
            If None, would be stored in the current dir. Files should end with the .pem.


            private_key_filepath (str): Absolute filepath to where the private key should be written and stored.
            If None, would be stored in the current dir. Files should end with the .pem.

        Returns:
            public_key (str), private_key (str)
        """

        securityRSA = SecurityRSA()
        public_key, private_key = securityRSA.generate_keypair()

        file_out = open(private_key_filepath, "wb")
        file_out.write(private_key)
        file_out.close()

        file_out = open(public_key_filepath, "wb")
        file_out.write(public_key)
        file_out.close()

        return public_key, private_key

    @staticmethod
    def encrypt_with_key(data: str, public_key: str, mgf1ParameterSpec: str='sha1', 
            hashingAlgorithm: str='sha256') -> bytes:
        """Encrypt with public key stored in ..public.pem.

        Args:
            data (str): Base64 plain input.
            public_key (str): Base64 public key, possibly in PEM format.
        """

        mgf1ParameterSpec = SHA256 if not mgf1ParameterSpec == 'sha1' else SHA1
        hashingAlgorithm = SHA256 if not hashingAlgorithm == 'sha1' else SHA1

        public_key = PKCS1_OAEP.new(
                key=RSA.importKey(public_key), 
                hashAlgo=hashingAlgorithm.new(), mgfunc=lambda x,y: pss.MGF1(x,y, mgf1ParameterSpec))

        data = bytes(data, 'utf-8')
        encrypted_text = public_key.encrypt(data)

        return encrypted_text
    

    @staticmethod
    def decrypt(data: str, 
            private_key_filepath: str="private.pem", 
            mgf1ParameterSpec: str='sha1',
            hashingAlgorithm: str='sha256') -> bytes:
        """Decrypt with own private key stored in ..private.pem.

        Args:
            data (str): Base64 encrypted input.
            private_key_filepath (str): path to private key (private.pem) on system.
        """

        with open(private_key_filepath) as fd:
            private_key = RSA.import_key(fd.read())

        mgf1ParameterSpec = SHA256 if not mgf1ParameterSpec == 'sha1' else SHA1
        hashingAlgorithm = SHA256 if not hashingAlgorithm == 'sha1' else SHA1

        try:
            private_key = PKCS1_OAEP.new(
                    key=private_key, 
                    hashAlgo=hashingAlgorithm.new(), mgfunc=lambda x,y: pss.MGF1(x,y, mgf1ParameterSpec))

            data = base64.b64decode(data)
            decrypted_text = private_key.decrypt(data)

        except Exception as error:
            raise error
        
        else:
            return decrypted_text


    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt with own private key stored in ..private.pem.

        Args:
            data (str): Base64 encrypted input.
        """

        private_key = PKCS1_OAEP.new(
                key=RSA.importKey(self.private_key), 
                hashAlgo=SHA256.new(), mgfunc=lambda x,y: pss.MGF1(x,y, SHA1))

        decrypted_text = private_key.decrypt(data)

        return decrypted_text

    def _encrypt(self, data: str) -> bytes:
        """Decrypt with own private key stored in ..private.pem.

        Args:
            data (str): Base64 encrypted input.
        """

        public_key = PKCS1_OAEP.new(
                key=RSA.importKey(self.public_key), 
                hashAlgo=SHA256.new(), mgfunc=lambda x,y: pss.MGF1(x,y, SHA1))

        data = bytes(data, 'utf-8')
        encrypted_text = public_key.encrypt(data)

        return encrypted_text

    @staticmethod
    def sign(message: str, signature: str, public_key: str) -> bool:
        """
        """
        key = RSA.importKey(public_key)

        h = SHA512.new(message)

        verifier = pss.new(key)

        try:
            return verifier.verify(h, signature)
        except (ValueError, TypeError) as error:
            raise error


