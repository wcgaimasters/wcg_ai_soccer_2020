#!/usr/bin/env python3

import base64
import numpy as np
import cv2
import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../common')
try:
    from participant import Participant
except ImportError as err:
    print('general_image-fetch: \'participant\' module cannot be imported:', err)
    raise

class ImageFetch(Participant):
    def init(self, info):
        self.cameraResolution = info['resolution']
        self.ImageBuffer = np.zeros((self.cameraResolution[1], self.cameraResolution[0], 3), dtype=np.uint8)

        self.set_default_formation()
        
    def update(self, frame):
        for subimage in frame.subimages:
            x = subimage[0]
            y = subimage[1]
            w = subimage[2]
            h = subimage[3]
            decoded = np.fromstring(base64.b64decode(subimage[4]), dtype=np.uint8)  # convert byte array to numpy array
            image = decoded.reshape((h, w, 4))
            for j in range(h):
                for k in range(w):
                    self.ImageBuffer[j + y, k + x, 0] = image[j, k, 0]  # red channel
                    self.ImageBuffer[j + y, k + x, 1] = image[j, k, 1]  # green channel
                    self.ImageBuffer[j + y, k + x, 2] = image[j, k, 2]  # blue channel
        # Display the image
        cv2.imshow("image", self.ImageBuffer / 255.0)
        cv2.waitKey(1)

if __name__ == '__main__':
    player = ImageFetch()
    player.run()
