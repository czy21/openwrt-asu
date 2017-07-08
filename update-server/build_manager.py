import socket
from image import Image
import threading
from imagebuilder import ImageBuilder
import logging
import time
from database import Database
from config import Config
import os

class BuildManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.imagebuilder_threads = []
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.last_build_id = self.database.get_last_build_id()
        if not self.last_build_id:
            self.last_build_id = 1

    def get_last_build_id(self):
        return self.last_build_id

    def run(self):
        self.database.reset_build_requests()
        
        while True:
            imagebuilder_request = self.database.get_imagebuilder_request()
            if imagebuilder_request:
                self.log.debug("setting up imagebuilder")
                distro, release, target, subtarget = imagebuilder_request
                imagebuilder = ImageBuilder(distro, release, target, subtarget)
                imagebuilder.start()
                self.imagebuilder_threads.append(imagebuilder)

            build_job_request = self.database.get_build_job()
            if not build_job_request:
                time.sleep(5)
            else:
                self.log.debug("found build job")
                self.last_build_id = build_job_request[0]
                image = Image(*build_job_request[2:9])
                self.log.debug(image.as_array())
                if not image.run():
                    self.log.warn("build failed for %s", image.name)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    bm = BuildManager()
    bm.start()

    socket_name = "/tmp/build_manager_last_build_id"
    if os.path.exists(socket_name):
        os.remove(socket_name)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_name)
    server.listen()

    while True:
        print("wait for connection - last_build_id: {}".format(bm.get_last_build_id()))
        connection, client_address = server.accept()
        try:
            connection.send(str(bm.get_last_build_id()).encode())
        finally:
            connection.close()